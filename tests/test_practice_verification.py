"""Verifier regression tests; all generated timings here are synthetic fixtures."""

import copy
import csv
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import practice_verify as verifier


def synthetic_payload(letter):
    """Create labelled fake data only in a temporary test directory."""
    config = {"workers": [1, 2, 4], "repeats": 3, "quick": False, "start_method": "spawn"}
    if letter == "A":
        config.update(total_chunks=16, chunk_size=2_000_000, serial_pause_seconds=0.40)
        times = {1: 3.20, 2: 1.80, 4: 1.10}
    elif letter == "B":
        config["total_increments"] = 2_000_000
        times = {1: 0.65, 2: 1.10, 4: 2.40}
    else:
        config["total_increments"] = 20_000_000
        # Deliberately miss E4>70%; correctness must still pass.
        times = {1: 1.00, 2: 0.60, 4: 0.40}
    samples = []
    for p in (1, 2, 4):
        for repeat in range(1, 4):
            sample = {"workers": p, "repeat": repeat, "runtime_seconds": times[p]}
            if letter == "A":
                sample.update(chunk_results=[0.25] * 16, total_result=4.0)
            else:
                total = config["total_increments"]
                sample.update(total_count=total, expected_total=total,
                              worker_iterations=verifier.expected_partition(total, p))
                if letter == "C":
                    sample["worker_counts"] = verifier.expected_partition(total, p)
            samples.append(sample)
    return {"schema_version": 1, "experiment": letter,
            "created_at_utc": "2000-01-01T00:00:00+00:00", "config": config,
            "samples": samples, "summary": verifier.independent_summary(samples),
            "notes": ["SYNTHETIC TEST FIXTURE, NOT A MEASUREMENT"]}


def write_payload(directory, payload):
    stem = "experiment_" + payload["experiment"].lower()
    (directory / (stem + ".json")).write_text(json.dumps(payload), encoding="utf-8")
    with (directory / (stem + ".tsv")).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=verifier.SUMMARY_FIELDS, delimiter="\t")
        writer.writeheader()
        writer.writerows(payload["summary"])


def write_fixture(directory):
    profile = {"cpu_model": "SYNTHETIC TEST HOST", "architecture": "test",
               "os": "test", "physical_cores": 4, "logical_threads": 4,
               "python": {"version": "3.test"},
               "timer": {"monotonic": True, "resolution_seconds": 1e-9}}
    (directory / "host_profile.json").write_text(json.dumps(profile), encoding="utf-8")
    for letter in "ABC":
        write_payload(directory, synthetic_payload(letter))


class PracticeVerificationTests(unittest.TestCase):
    def test_known_formula_corrects_handout_example_arithmetic(self):
        a = synthetic_payload("A")["summary"]
        b = synthetic_payload("B")["summary"]
        self.assertAlmostEqual(a[1]["karp_flatt"], 0.125)
        self.assertAlmostEqual(a[2]["karp_flatt"], 0.125)
        self.assertAlmostEqual(b[1]["karp_flatt"], 2.3846153846153846)
        self.assertAlmostEqual(b[2]["karp_flatt"], 4.589743589743589)
        self.assertIsNone(a[0]["karp_flatt"])

    def test_serial_reference_uses_stated_range(self):
        expected = math.fsum(math.sin(i) * math.cos(i) for i in range(1, 19))
        self.assertEqual(verifier.serial_reference(19), expected)

    def test_correctness_passes_when_performance_condition_does_not(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            write_fixture(directory)
            with mock.patch.object(verifier, "serial_reference", return_value=0.25):
                report = verifier.verify_results(directory, repo_root=directory)
            self.assertEqual(report["correctness_status"], "pass")
            self.assertTrue(report["rubric"]["A"]["meets_numeric_condition"])
            self.assertTrue(report["rubric"]["B"]["meets_numeric_condition"])
            self.assertFalse(report["rubric"]["C"]["meets_numeric_condition"])
            self.assertEqual(report["instructor_signoff"], "pending")
            self.assertFalse(report["official_instructor_checker"])

    def test_tampered_shared_counter_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            payload = synthetic_payload("B")
            payload["samples"][4]["total_count"] -= 1
            write_payload(directory, payload)
            with self.assertRaisesRegex(verifier.VerificationError, "total_count"):
                verifier.verify_experiment(payload, "B", directory)

    def test_tampered_private_worker_count_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            payload = synthetic_payload("C")
            payload["samples"][4]["worker_counts"][0] -= 1
            write_payload(directory, payload)
            with self.assertRaisesRegex(verifier.VerificationError, "worker_counts"):
                verifier.verify_experiment(payload, "C", directory)

    def test_primary_c_rejects_nondefault_workloads(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for total in (2_000, 200_000_000):
                payload = synthetic_payload("C")
                payload["config"]["total_increments"] = total
                with self.subTest(total=total), self.assertRaisesRegex(
                        verifier.VerificationError, "expected 20,000,000 increments"):
                    verifier.verify_experiment(payload, "C", directory)

    def test_supplemental_c_is_checked_without_replacing_primary_rubric(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            write_fixture(directory)
            supplemental_dir = directory / "supplemental_c_200m"
            supplemental_dir.mkdir()
            payload = synthetic_payload("C")
            payload["config"]["total_increments"] = 200_000_000
            for sample in payload["samples"]:
                p = sample["workers"]
                sample.update(total_count=200_000_000, expected_total=200_000_000,
                              worker_iterations=verifier.expected_partition(200_000_000, p),
                              worker_counts=verifier.expected_partition(200_000_000, p),
                              runtime_seconds={1: 4.0, 2: 2.1, 4: 1.1}[p])
            payload["summary"] = verifier.independent_summary(payload["samples"])
            write_payload(supplemental_dir, payload)
            with mock.patch.object(verifier, "serial_reference", return_value=0.25):
                report = verifier.verify_results(directory, repo_root=directory)
            self.assertFalse(report["rubric"]["C"]["meets_numeric_condition"])
            supplemental = report["supplemental"]["C_200m"]
            self.assertEqual(supplemental["status"], "pass")
            self.assertFalse(supplemental["full_handout_parameters"])
            self.assertTrue(supplemental["performance_observation"]["meets_numeric_condition"])
            self.assertEqual(report["checks"]["C"]["summary"][0]["median_seconds"], 1.0)
            payload["samples"][0]["worker_counts"][0] -= 1
            write_payload(supplemental_dir, payload)
            with self.assertRaisesRegex(verifier.VerificationError, "worker_counts"):
                verifier.verify_experiment(payload, "C", supplemental_dir, supplemental=True)

    def test_supplemental_c_requires_exact_200m_workload(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            payload = synthetic_payload("C")
            with self.assertRaisesRegex(verifier.VerificationError, "expected 200,000,000 increments"):
                verifier.verify_experiment(payload, "C", directory, supplemental=True)

    def test_tampered_math_chunk_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            payload = synthetic_payload("A")
            payload["samples"][0]["chunk_results"][0] = 0.0
            write_payload(directory, payload)
            with mock.patch.object(verifier, "serial_reference", return_value=0.25), \
                    self.assertRaisesRegex(verifier.VerificationError, "chunk 0"):
                verifier.verify_experiment(payload, "A", directory)

    def test_tampered_tsv_is_rejected_even_when_json_is_correct(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            payload = synthetic_payload("B")
            write_payload(directory, payload)
            path = directory / "experiment_b.tsv"
            rows = path.read_text().splitlines()
            fields = rows[2].split("\t")
            fields[verifier.SUMMARY_FIELDS.index("speedup")] = "999"
            rows[2] = "\t".join(fields)
            path.write_text("\n".join(rows) + "\n")
            with self.assertRaisesRegex(verifier.VerificationError, "speedup"):
                verifier.verify_experiment(payload, "B", directory)

    def test_nan_runtime_and_duplicate_repeats_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            original = synthetic_payload("B")
            for field, value, message in (("runtime_seconds", math.nan, "finite"),
                                          ("repeat", 2, "duplicate")):
                payload = copy.deepcopy(original)
                payload["samples"][0][field] = value
                write_payload(directory, payload)
                with self.subTest(field=field), self.assertRaisesRegex(verifier.VerificationError, message):
                    verifier.verify_experiment(payload, "B", directory)

    def test_quick_data_cannot_replace_full_default_measurements(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            payload = synthetic_payload("B")
            payload["config"]["quick"] = True
            with self.assertRaisesRegex(verifier.VerificationError, "quick/smoke"):
                verifier.verify_experiment(payload, "B", directory)

    def test_zero_e2_does_not_create_infinite_or_nan_rubric_value(self):
        payloads = {letter: synthetic_payload(letter) for letter in "ABC"}
        payloads["A"]["summary"][1]["karp_flatt"] = 0.0
        observation = verifier.assess_rubric(payloads)["A"]
        self.assertIsNone(observation["e4_over_e2"])
        self.assertFalse(observation["meets_numeric_condition"])

    def test_manifest_binds_sources_and_data_excluding_own_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / "practice_results"
            directory.mkdir()
            (root / "practice_verify.py").write_text("source\n")
            (directory / "experiment_a.json").write_text("saved data\n")
            (directory / "verification.json").write_text("old receipt\n")
            manifest = verifier.file_manifest(root, directory)
            names = {record["path"] for record in manifest}
            self.assertEqual(names, {"practice_verify.py", "practice_results/experiment_a.json"})
            before = next(record["sha256"] for record in manifest
                          if record["path"] == "practice_results/experiment_a.json")
            (directory / "experiment_a.json").write_text("tampered\n")
            after = next(record["sha256"] for record in verifier.file_manifest(root, directory)
                         if record["path"] == "practice_results/experiment_a.json")
            self.assertNotEqual(before, after)

    def test_failed_cli_removes_stale_receipt_and_no_receipt_mode_preserves_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            receipt = directory / "verification.json"
            receipt.write_text("old success\n")
            with mock.patch("sys.stderr"):
                self.assertEqual(verifier.main(["--output-dir", str(directory), "--no-receipt"]), 1)
            self.assertTrue(receipt.exists())
            with mock.patch("sys.stderr"):
                self.assertEqual(verifier.main(["--output-dir", str(directory)]), 1)
            self.assertFalse(receipt.exists())


if __name__ == "__main__":
    unittest.main()
