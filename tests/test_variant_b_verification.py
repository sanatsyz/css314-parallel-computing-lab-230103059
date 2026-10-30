"""Synthetic verifier fixtures only; no timings in these tests are measurements."""

import copy
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify_variant_b as verifier


def synthetic_payload(case):
    config = {"workers": verifier.WORKERS, "repeats": 3, "start_method": "spawn",
              "quick": False, "total_items": verifier.TOTALS[case]}
    times = {
        "a_micro": {1: 10.0, 2: 12.0, 4: 15.0, 8: 20.0},
        "a_coarse": {1: 4.8, 2: 2.5, 4: 1.35, 8: 0.75},
        "b_queue": {1: 1.2, 2: 1.95, 4: 3.8, 8: 7.6},
        # Deliberately miss C performance targets while retaining correct data.
        "c_buffered": {1: 1.0, 2: 0.7, 4: 0.5, 8: 0.4},
    }[case]
    if case.startswith("a_"):
        config["chunk_size"] = 1 if case == "a_micro" else 10_000
    elif case == "c_buffered":
        config["batch_size"] = 10_000
    samples = []
    for p in verifier.WORKERS:
        for repeat in range(1, 4):
            total = config["total_items"]
            sample = {"workers": p, "repeat": repeat, "runtime_seconds": times[p],
                      "total_items": total, "start_method": "spawn", "result_count": total}
            if case.startswith("a_"):
                sample.update(chunk_size=config["chunk_size"], result_sum=17)
            else:
                partition = verifier.expected_partition(total, p)
                result = sum(verifier.pattern_reference(count) for count in partition)
                sample.update(worker_items=partition, result_sum=result, expected_sum=result,
                              worker_exitcodes=[0] * p)
                if case == "b_queue":
                    sample["received_messages"] = total
                else:
                    batch = config["batch_size"]
                    batches = sum((count + batch - 1) // batch for count in partition)
                    sample.update(batch_size=batch, sentinels_received=p,
                                  received_batches=batches, received_messages=batches,
                                  total_received_messages=batches + p)
            samples.append(sample)
    return {"schema_version": 1, "case_id": case, "created_at_utc": "2000-01-01T00:00:00+00:00",
            "config": config, "samples": samples, "summary": verifier.independent_summary(samples),
            "notes": ["SYNTHETIC FIXTURE, NOT MEASURED DATA"]}


def write_payload(directory, payload):
    stem = payload["case_id"]
    (directory / (stem + ".json")).write_text(json.dumps(payload), encoding="utf-8")
    with (directory / (stem + ".tsv")).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=verifier.SUMMARY_FIELDS, delimiter="\t")
        writer.writeheader()
        writer.writerows(payload["summary"])


def write_fixture(directory):
    host = {"cpu_model": "SYNTHETIC HOST", "architecture": "test", "os": "test",
            "physical_cores": 8, "logical_threads": 8, "python": {"version": "3.test"},
            "timer": {"monotonic": True, "resolution_seconds": 1e-9}}
    config = {"student_id": "230103059", "branch": "variant-b-230103059", "workers": verifier.WORKERS,
              "repeats": 3, "start_method": "spawn", "course": "CSS314"}
    (directory / "host_profile.json").write_text(json.dumps(host), encoding="utf-8")
    (directory / "configuration.json").write_text(json.dumps(config), encoding="utf-8")
    for case in verifier.CASES:
        write_payload(directory, synthetic_payload(case))


class VariantBVerificationTests(unittest.TestCase):
    def test_independent_collatz_oracle_matches_naive_small_range(self):
        def naive(value):
            steps = 0
            while value > 1:
                value = value // 2 if value % 2 == 0 else 3 * value + 1
                steps += 1
            return steps
        for total in (0, 1, 2, 19, 101, 300):
            with self.subTest(total=total):
                self.assertEqual(verifier.collatz_reference(total), sum(naive(n) for n in range(1, total + 1)))

    def test_pattern_oracle_includes_each_worker_reset_and_tail(self):
        for count in range(25):
            self.assertEqual(verifier.pattern_reference(count), sum(i % 7 for i in range(count)))
        self.assertEqual(verifier.expected_partition(13, 8), [2, 2, 2, 2, 2, 1, 1, 1])

    def test_known_formula_corrects_handout_examples(self):
        a = synthetic_payload("a_coarse")["summary"]
        b = synthetic_payload("b_queue")["summary"]
        self.assertAlmostEqual(a[1]["karp_flatt"], 1 / 24)
        self.assertAlmostEqual(a[3]["karp_flatt"], 1 / 28)
        self.assertAlmostEqual(b[1]["karp_flatt"], 2.25)
        self.assertAlmostEqual(b[3]["karp_flatt"], 7.095238095238095)
        self.assertIsNone(a[0]["karp_flatt"])

    def test_correctness_and_empirical_target_are_separate(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            write_fixture(directory)
            with mock.patch.object(verifier, "collatz_reference", return_value=17):
                report = verifier.verify_results(directory, repo_root=directory)
            self.assertEqual(report["correctness_status"], "pass")
            self.assertTrue(report["rubric"]["A"]["meets_numeric_condition"])
            self.assertTrue(report["rubric"]["B"]["meets_numeric_condition"])
            self.assertFalse(report["rubric"]["C"]["meets_numeric_condition"])
            self.assertEqual(report["instructor_signoff"], "pending")
            self.assertFalse(report["official_instructor_checker"])

    def test_same_p_throughput_gain_accounts_for_different_totals(self):
        checks = {case: synthetic_payload(case) for case in verifier.CASES}
        c = verifier.assess_rubric(checks)["C"]
        self.assertAlmostEqual(c["throughput_gain_over_unbuffered"]["8"], 475.0)
        self.assertFalse(c["meets_numeric_condition"])
        self.assertFalse(c["task_e8_below_004"])

    def test_each_full_case_rejects_altered_workload(self):
        with tempfile.TemporaryDirectory() as temporary:
            for case in verifier.CASES:
                payload = synthetic_payload(case)
                payload["config"]["total_items"] -= 1
                with self.subTest(case=case), self.assertRaisesRegex(verifier.VerificationError, "total_items"):
                    verifier.verify_case(payload, case, Path(temporary))

    def test_quick_data_cannot_substitute_for_default_work(self):
        payload = synthetic_payload("b_queue")
        payload["config"]["quick"] = True
        with self.assertRaisesRegex(verifier.VerificationError, "quick/smoke"):
            verifier.verify_case(payload, "b_queue", Path("unused"))

    def test_tampered_collatz_checksum_is_rejected(self):
        payload = synthetic_payload("a_micro")
        payload["samples"][0]["result_sum"] -= 1
        with mock.patch.object(verifier, "collatz_reference", return_value=17), \
                self.assertRaisesRegex(verifier.VerificationError, "result_sum"):
            verifier.verify_case(payload, "a_micro", Path("unused"))

    def test_wrong_queue_checksum_partition_or_message_count_is_rejected(self):
        for field, value in (("result_sum", 0), ("worker_items", [400_000, 0]), ("received_messages", 0)):
            payload = synthetic_payload("b_queue")
            payload["samples"][0][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(verifier.VerificationError, field):
                verifier.verify_case(payload, "b_queue", Path("unused"))

    def test_buffered_batch_and_sentinel_counts_are_independently_checked(self):
        for field in ("batch_size", "received_batches", "received_messages", "sentinels_received", "total_received_messages"):
            payload = synthetic_payload("c_buffered")
            payload["samples"][0][field] += 1
            with self.subTest(field=field), self.assertRaisesRegex(verifier.VerificationError, field):
                verifier.verify_case(payload, "c_buffered", Path("unused"))

    def test_failed_worker_exitcode_is_rejected_even_if_totals_match(self):
        payload = synthetic_payload("b_queue")
        payload["samples"][0]["worker_exitcodes"] = [1]
        with self.assertRaisesRegex(verifier.VerificationError, "worker_exitcodes"):
            verifier.verify_case(payload, "b_queue", Path("unused"))

    def test_nan_nonpositive_times_duplicate_repeats_and_boolean_counts_fail(self):
        for field, value, message in (("runtime_seconds", math.nan, "finite"),
                                      ("runtime_seconds", 0, "positive"),
                                      ("repeat", 2, "duplicate"), ("result_count", True, "result_count")):
            payload = synthetic_payload("b_queue")
            payload["samples"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaisesRegex(verifier.VerificationError, message):
                verifier.verify_case(payload, "b_queue", Path("unused"))

    def test_tsv_is_checked_independently_of_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            payload = synthetic_payload("b_queue")
            write_payload(directory, payload)
            path = directory / "b_queue.tsv"
            rows = path.read_text().splitlines()
            fields = rows[2].split("\t")
            fields[verifier.SUMMARY_FIELDS.index("speedup")] = "999"
            rows[2] = "\t".join(fields)
            path.write_text("\n".join(rows) + "\n")
            with self.assertRaisesRegex(verifier.VerificationError, "speedup"):
                verifier.verify_case(payload, "b_queue", directory)

    def test_configuration_retains_full_student_id_and_exact_branch(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            write_fixture(directory)
            config = json.loads((directory / "configuration.json").read_text())
            config["student_id"] = "30103059"
            (directory / "configuration.json").write_text(json.dumps(config))
            with self.assertRaisesRegex(verifier.VerificationError, "student_id"):
                verifier.verify_results(directory, repo_root=directory)

    def test_manifest_records_hashes_and_excludes_only_own_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / "variant_b_results"
            directory.mkdir()
            (root / "verify_variant_b.py").write_text("source\n")
            data = directory / "b_queue.json"
            data.write_text("data\n")
            (directory / "verification.json").write_text("old receipt\n")
            manifest = verifier.file_manifest(root, directory)
            self.assertEqual({item["path"] for item in manifest}, {"verify_variant_b.py", "variant_b_results/b_queue.json"})
            self.assertEqual(next(item["sha256"] for item in manifest if item["path"].endswith("b_queue.json")),
                             hashlib.sha256(data.read_bytes()).hexdigest())

    def test_failed_cli_removes_stale_success_but_readonly_mode_preserves_it(self):
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
