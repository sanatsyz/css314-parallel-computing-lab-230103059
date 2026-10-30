"""Tiny synthetic metadata fixtures exercise the real unchanged teacher verifier.

These fixtures test orchestration, not this machine's measurements or performance.
"""

import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_teacher


class TeacherRunnerTests(unittest.TestCase):
    def fixture(self, directory, cache_line_bytes=64):
        directory.mkdir(parents=True, exist_ok=True)
        sid = "30103059"
        h = int(hashlib.sha256(sid.encode()).hexdigest()[:8], 16)
        (directory / "salted_params.json").write_text(json.dumps({
            "student_id": sid, "N": 1024 + (h % 9) * 64,
        }))
        (directory / "host_profile.json").write_text(json.dumps({
            "cpu_model": "SYNTHETIC UNIT TEST HOST", "physical_cores": 4,
            "logical_threads": 4, "cache_line_bytes": cache_line_bytes,
        }))
        # Exercise accepted schema aliases without changing any verifier logic.
        (directory / "stride_results.tsv").write_text("Stride\tLatency_ns\n1\t1.0\n8\t2.0\n")
        (directory / "loop_interchange.json").write_text(json.dumps({
            "t_naive": 2.0, "t_interchanged": 1.0, "speedup": 2.0,
        }))
        (directory / "false_sharing_karp_flatt.tsv").write_text(
            "P\te_p_unpadded\te_p_padded\n2\t0.1\t0.05\n4\t0.2\t0.05\n"
        )
        (directory / "scaling_metrics.tsv").write_text("workers\ttime\n1\t1.0\n2\t0.75\n")
        (directory / "roofline_summary.json").write_text(json.dumps({
            "classification": "memory-bound", "ai": 0.3125,
        }))

    def run_fixture(self, directory, *extra):
        with contextlib.redirect_stdout(io.StringIO()):
            return check_teacher.main(["--results-dir", str(directory), *extra])

    def test_128_byte_host_fails_truthfully_and_removes_stale_official_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.fixture(directory, cache_line_bytes=128)
            before = {name: (directory / name).read_bytes() for name in check_teacher.INPUT_FILES}
            (directory / "verification_receipt.sig").write_text("stale success")
            self.assertEqual(self.run_fixture(directory), 1)
            report = json.loads((directory / "teacher_verification.json").read_text())
            self.assertEqual(report["status"], "fail")
            self.assertEqual(report["full_run"]["exit_code"], 1)
            self.assertIn("Expected cache_line_bytes == 64, got 128", report["full_run"]["stdout"])
            self.assertFalse(report["official_receipt_generated"])
            self.assertFalse((directory / "verification_receipt.sig").exists())
            self.assertEqual(before, {name: (directory / name).read_bytes() for name in check_teacher.INPUT_FILES})

    def test_64_byte_fixture_publishes_only_the_actual_teacher_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.fixture(directory)
            self.assertEqual(self.run_fixture(directory), 0)
            report = json.loads((directory / "teacher_verification.json").read_text())
            self.assertEqual(report["full_run"]["status"], "pass")
            self.assertTrue(report["official_receipt_generated"])
            params = json.loads((directory / "salted_params.json").read_text())
            expected_hash = hashlib.sha256(
                f"CS482-PRACTICUM-VERIFIED-{params['student_id']}-{params['N']}-HASH-SOLO-LAB".encode()
            ).hexdigest()
            receipt = (directory / "verification_receipt.sig").read_bytes()
            self.assertEqual(receipt.decode(),
                             f"STUDENT_ID={params['student_id']}\nSALTED_N={params['N']}\nSIGNATURE={expected_hash}\n")
            self.assertEqual(report["receipt_validation"]["receipt_sha256"], hashlib.sha256(receipt).hexdigest())
            self.assertEqual(set(report["inputs_hashes"]), set(check_teacher.INPUT_FILES))
            for name, digest in report["inputs_hashes"].items():
                self.assertEqual(digest, hashlib.sha256((directory / name).read_bytes()).hexdigest())

    def test_modified_teacher_script_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.fixture(directory)
            changed = directory / "changed_teacher.py"
            changed.write_bytes((check_teacher.ROOT / "verify_outputs.py.txt").read_bytes() + b"\n# altered\n")
            with patch.object(check_teacher.subprocess, "run") as execute:
                self.assertEqual(self.run_fixture(directory, "--teacher-script", str(changed)), 2)
            execute.assert_not_called()
            report = json.loads((directory / "teacher_verification.json").read_text())
            self.assertEqual(report["source_integrity"]["status"], "fail")
            self.assertEqual(report["full_run"]["status"], "not_run")
            self.assertEqual(report["milestone_diagnostics"], [])
            self.assertFalse((directory / "verification_receipt.sig").exists())

    def test_individual_diagnostics_do_not_override_failed_full_main(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.fixture(directory, cache_line_bytes=128)
            self.assertNotEqual(self.run_fixture(directory), 0)
            report = json.loads((directory / "teacher_verification.json").read_text())
            diagnostics = report["milestone_diagnostics"]
            self.assertEqual([(item["milestone"], item["status"], item["exit_code"])
                              for item in diagnostics],
                             [("M0", "fail", 1), ("M1", "pass", 0),
                              ("M2", "pass", 0), ("M3", "pass", 0)])
            self.assertTrue(all(item["diagnostic_only"] for item in diagnostics))
            self.assertEqual(report["status"], "fail")
            self.assertFalse(report["official_receipt_generated"])

    def test_reports_are_plain_text_and_custom_output_does_not_change_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "fixtures"
            output = Path(temporary) / "reports"
            self.fixture(directory)
            self.assertEqual(self.run_fixture(directory, "--output-dir", str(output)), 0)
            for name in ("teacher_verification.json", "teacher_verification.log"):
                self.assertNotIn("\x1b", (output / name).read_text())
                self.assertNotIn("\\u001b", (output / name).read_text())
            self.assertTrue((output / "verification_receipt.sig").exists())
            self.assertFalse((directory / "verification_receipt.sig").exists())

    def test_original_uploaded_source_is_compared_before_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.fixture(directory)
            changed = directory / "changed_original.txt"
            changed.write_bytes(b"a different uploaded source")
            with patch.object(check_teacher.subprocess, "run") as execute:
                self.assertEqual(self.run_fixture(directory, "--provided-source", str(changed)), 2)
            execute.assert_not_called()
            self.assertFalse((directory / "verification_receipt.sig").exists())


if __name__ == "__main__":
    unittest.main()
