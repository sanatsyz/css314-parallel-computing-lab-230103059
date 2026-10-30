"""Independent digest, tamper, and stale-receipt checks with temporary data."""

import hashlib
import json
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify_numerics as verifier


class VerifierTests(unittest.TestCase):
    def test_teacher_metric_columns_cannot_swap_literal_and_hardware_padding(self):
        variants = {"unpadded": 8, "padded": 128, "padded_64": 64, "privatized": 8}
        # Baseline and parallel times intentionally differ by padding variant.
        timings = {"unpadded": (2.0, 6.0), "padded": (2.0, 1.0),
                   "padded_64": (2.0, 3.0), "privatized": (2.0, 2.0)}
        groups = {(variant, p): [{"seconds": times[index]}]
                  for variant, times in timings.items() for index, p in enumerate((1, 4))}
        row = {"p": 4, "e_unpadded": 11 / 3, "e_padded": 5 / 3,
               "e_padded_128": 1 / 3, "e_privatized": 1.0,
               "padded_column_variant": "padded_64", "hardware_padded_column_variant": "padded"}
        verifier.check_teacher_metric_aliases(row, groups, variants, 4, "test aliases")
        swapped = {**row, "e_padded": row["e_padded_128"], "e_padded_128": row["e_padded"]}
        with self.assertRaisesRegex(verifier.VerificationError, "e_padded"):
            verifier.check_teacher_metric_aliases(swapped, groups, variants, 4, "test aliases")
        p1 = {**row, "p": 1, **{name: None for name in
              ("e_unpadded", "e_padded", "e_padded_128", "e_privatized")}}
        verifier.check_teacher_metric_aliases(p1, groups, variants, 1, "P=1 aliases")

    def test_instructor_script_preserves_uploaded_source_exactly(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual((root / "verify_outputs.py").read_bytes(),
                         (root / "verify_outputs.py.txt").read_bytes())

    def test_local_receipt_is_separate_from_instructor_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            instructor_receipt = directory / "verification_receipt.sig"
            instructor_bytes = b"STUDENT_ID=30103059\nSIGNATURE=teacher-result\n"
            instructor_receipt.write_bytes(instructor_bytes)
            local_receipt = directory / "local_verification_receipt.json"
            local_receipt.write_text("stale local success")
            # Missing inputs force a failed local run without invoking benchmarks.
            self.assertEqual(verifier.main(["--output-dir", str(directory)]), 1)
            self.assertFalse(local_receipt.exists())
            self.assertEqual(instructor_receipt.read_bytes(), instructor_bytes)
            with mock.patch.object(verifier, "verify_m0", return_value=({}, {}, {"status": "pass"})), \
                    mock.patch.object(verifier, "verify_m1", return_value={"status": "pass"}), \
                    mock.patch.object(verifier, "verify_m2", return_value={"status": "pass"}), \
                    mock.patch.object(verifier, "verify_m3", return_value={"status": "pass"}):
                self.assertEqual(verifier.main(["--output-dir", str(directory)]), 0)
            receipt = json.loads(local_receipt.read_text())
            self.assertFalse(receipt["cryptographically_signed"])
            self.assertTrue(receipt["instructor_verifier_available"])
            self.assertEqual(instructor_receipt.read_bytes(), instructor_bytes)

    def test_no_receipt_mode_preserves_existing_receipts_on_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            names = ("local_verification_receipt.json", "verification_receipt.sig")
            for name in names:
                (directory / name).write_bytes(b"existing receipt\n")
            self.assertEqual(verifier.main(["--output-dir", str(directory), "--no-receipt"]), 1)
            for name in names:
                self.assertEqual((directory / name).read_bytes(), b"existing receipt\n")

    def test_manifest_hashes_both_verifiers_and_only_excludes_local_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / "results"
            directory.mkdir()
            source_names = ("verify_numerics.py", "verify_outputs.py", "verify_outputs.py.txt", "check_teacher.py")
            for name in source_names:
                (root / name).write_text(f"source: {name}\n")
            (directory / "local_verification_receipt.json").write_text("local")
            instructor_receipt = directory / "verification_receipt.sig"
            instructor_receipt.write_text("teacher")
            manifest = verifier.file_manifest(root, directory)
            paths = {record["path"] for record in manifest}
            self.assertTrue(set(source_names).issubset(paths))
            self.assertIn("results/verification_receipt.sig", paths)
            self.assertNotIn("results/local_verification_receipt.json", paths)
            verifier.verify_file_manifest(manifest, root)
            instructor_receipt.write_text("tampered")
            with self.assertRaisesRegex(verifier.VerificationError, "verification_receipt.sig"):
                verifier.verify_file_manifest(manifest, root)

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
            receipt = directory / "local_verification_receipt.json"
            receipt.write_text("stale success")
            self.assertEqual(verifier.main(["--output-dir", str(directory)]), 1)
            self.assertFalse(receipt.exists())


if __name__ == "__main__":
    unittest.main()
