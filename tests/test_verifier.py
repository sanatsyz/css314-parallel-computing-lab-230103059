"""Independent digest, tamper, and stale-receipt checks with temporary data."""

import hashlib
import json
import copy
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify_outputs as verifier


class VerifierTests(unittest.TestCase):
    def test_published_m4_bandwidth_is_distinct_from_unavailable_telemetry(self):
        profile = {"cpu_model": "Apple M4", "peak_memory_bandwidth_bytes_per_second": None,
                   "peak_float64_flops_per_second": None}
        roof = {"peak_memory_bandwidth_bytes_per_second": 120_000_000_000,
                "peak_memory_bandwidth_source": "https://support.apple.com/en-au/122209",
                "peak_memory_bandwidth_scope": "Apple's documented 120 GB/s unified-memory bandwidth upper bound; shared by the chip, not measured sustained CPU bandwidth for this kernel",
                "peak_float64_flops_per_second": None}
        self.assertEqual(verifier.validated_roofline_peaks(profile, roof), (120_000_000_000, None))
        for field, value in (("peak_memory_bandwidth_bytes_per_second", 121_000_000_000),
                             ("peak_memory_bandwidth_source", "https://example.com/claimed-peak"),
                             ("peak_memory_bandwidth_scope", "measured sustained CPU bandwidth"),
                             ("peak_float64_flops_per_second", 1_000_000_000_000)):
            changed = copy.deepcopy(roof)
            changed[field] = value
            with self.subTest(field=field), self.assertRaises(verifier.VerificationError):
                verifier.validated_roofline_peaks(profile, changed)
        unknown = {**profile, "cpu_model": "Unknown processor"}
        with self.assertRaises(verifier.VerificationError):
            verifier.validated_roofline_peaks(unknown, roof)

    def test_digest_rounds_and_binds_student_shape_and_values(self):
        values = np.array([[1.12345611, -0.0], [3.0, 4.0]])
        digest = verifier.rounded_salted_digest(values, "30103059")
        same = values.copy()
        same[0, 0] = 1.12345612
        same[0, 1] = 0.0
        self.assertEqual(digest, verifier.rounded_salted_digest(same, "30103059"))
        self.assertNotEqual(digest, verifier.rounded_salted_digest(values, "12345678"))
        self.assertNotEqual(digest, verifier.rounded_salted_digest(values.reshape(4), "30103059"))
        same[1, 1] += 0.000001
        self.assertNotEqual(digest, verifier.rounded_salted_digest(same, "30103059"))
        with self.assertRaises(verifier.VerificationError):
            verifier.rounded_salted_digest(np.array([np.nan]), "30103059")

    def test_file_sha_detects_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "data.txt"
            path.write_bytes(b"measured\n")
            manifest = [{"path": "data.txt", "bytes": path.stat().st_size,
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}]
            verifier.verify_file_manifest(manifest, root)
            path.write_bytes(b"modified\n")
            with self.assertRaisesRegex(verifier.VerificationError, "file changed"):
                verifier.verify_file_manifest(manifest, root)

    def test_m0_rejects_salt_tamper_and_failure_removes_old_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            params = {"student_id": "30103059", "N": 1536, "buffer_elements": 16_777_216, "seed": 91405}
            (directory / "salted_params.json").write_text(json.dumps(params))
            profile = {"physical_cores": 10, "logical_threads": 10, "cache_line_bytes": 128,
                       "cpu_model": "Test host", "architecture": "test", "os": "test",
                       "timer": {"monotonic": True, "resolution_seconds": 1e-9}}
            (directory / "host_profile.json").write_text(json.dumps(profile))
            verifier.verify_m0(directory)
            params["seed"] += 1
            (directory / "salted_params.json").write_text(json.dumps(params))
            with self.assertRaisesRegex(verifier.VerificationError, "salted parameters"):
                verifier.verify_m0(directory)
            receipt = directory / "verification_receipt.sig"
            receipt.write_text("stale success")
            self.assertEqual(verifier.main(["--output-dir", str(directory)]), 1)
            self.assertFalse(receipt.exists())


if __name__ == "__main__":
    unittest.main()
