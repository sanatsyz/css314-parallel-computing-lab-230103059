"""Verifier compatibility must preserve timing units and padding semantics."""

import copy
from pathlib import Path
import statistics
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dense_kernel import add_teacher_timing_aliases
from false_sharing import aggregate_trials
from scaling_study import add_teacher_roofline_aliases
from stride_bench import benchmark as stride_benchmark


class TeacherSchemaTests(unittest.TestCase):
    def test_stride_aliases_use_accessed_elements_including_uneven_tail(self):
        rows, raw = stride_benchmark(elements=259, warmups=1, repeats=3)
        for row, run in zip(rows, raw["runs"]):
            with self.subTest(stride=row["stride_elements"]):
                actual_accesses = len(range(0, 259, row["stride_elements"]))
                expected = statistics.median(run["time_ns"]) / actual_accesses
                self.assertEqual(row["stride"], row["stride_elements"])
                self.assertEqual(row["latency_ns"], expected)
                self.assertEqual(row["ns_per_element"], expected)

    def test_dense_aliases_convert_nanoseconds_to_seconds_without_changing_data(self):
        original = {"median_time_ns": {"ijk": 2_345_678_901, "ikj": 123_456_789},
                    "time_ns": {"ijk": [2_345_678_900, 2_345_678_901, 2_345_678_905],
                                "ikj": [123_456_780, 123_456_789, 123_456_799]}}
        before = copy.deepcopy(original)
        result = add_teacher_timing_aliases(original)
        self.assertEqual(original, before)
        self.assertEqual(result["naive_time_s"], 2.345678901)
        self.assertEqual(result["interchanged_time_s"], 0.123456789)
        self.assertAlmostEqual(result["naive_time_s"] / result["interchanged_time_s"],
                               statistics.median(original["time_ns"]["ijk"]) /
                               statistics.median(original["time_ns"]["ikj"]))

    @staticmethod
    def counter_samples(hardware_line=128):
        # Distinct per-variant baselines detect both a shared-baseline bug and
        # accidental substitution of 128-byte padding for the required 64.
        timings = {"unpadded": (1.0, 9.0), "padded": (2.0, 4.0),
                   "privatized": (3.0, 3.0)}
        if hardware_line == 128:
            timings["padded_64"] = (4.0, 20.0)
        samples = []
        for variant, (baseline, parallel) in timings.items():
            for workers, center in ((1, baseline), (4, parallel)):
                for repeat, factor in enumerate((0.9, 1.0, 1.1), 1):
                    samples.append({"variant": variant, "workers": workers,
                                    "seconds": center * factor,
                                    "iterations_per_worker": 1000,
                                    "total_increments": workers * 1000,
                                    "stride_bytes": (hardware_line if variant == "padded"
                                                     else 64 if variant == "padded_64" else 8),
                                    "counts_verified": True, "repeat": repeat})
        return samples

    def test_counter_aliases_compare_real_variant_baselines_and_literal_padding(self):
        samples = self.counter_samples()
        before = copy.deepcopy(samples)
        rows = aggregate_trials(samples)
        expected_variants = {"e_unpadded": "unpadded", "e_padded": "padded_64",
                             "e_padded_128": "padded", "e_privatized": "privatized"}
        for row in rows:
            p = row["workers"]
            self.assertEqual(row["p"], p)
            self.assertEqual(row["padded_column_variant"], "padded_64")
            self.assertEqual(row["hardware_padded_column_variant"], "padded")
            for field, variant in expected_variants.items():
                with self.subTest(variant=row["variant"], p=p, field=field):
                    if p == 1:
                        self.assertIsNone(row[field])
                    else:
                        t1 = statistics.median(s["seconds"] for s in samples
                                               if s["variant"] == variant and s["workers"] == 1)
                        tp = statistics.median(s["seconds"] for s in samples
                                               if s["variant"] == variant and s["workers"] == p)
                        self.assertAlmostEqual(row[field], (p * tp / t1 - 1) / (p - 1))
            if p > 1:
                self.assertNotEqual(row["e_padded"], row["e_padded_128"])
        self.assertEqual(samples, before)

    def test_64_byte_host_does_not_invent_128_byte_padding_measurements(self):
        for row in aggregate_trials(self.counter_samples(hardware_line=64)):
            self.assertEqual(row["padded_column_variant"], "padded")
            self.assertIsNone(row["e_padded_128"])
            if row["variant"] == "padded":
                self.assertEqual(row["e_padded"], row["karp_flatt_requested"])

    def test_low_intensity_does_not_fabricate_a_roofline_classification(self):
        original = {"arithmetic_intensity_models": {
            "optimistic_streaming": {"flops_per_byte": 5 / 16},
            "streaming_with_write_allocation": {"flops_per_byte": 5 / 24}},
            "peak_float64_flops_per_second": None,
            "ridge_point_flops_per_byte": None,
            "limiting_regime": "undetermined_without_documented_bandwidth_and_float64_compute_peaks"}
        before = copy.deepcopy(original)
        result = add_teacher_roofline_aliases(original)
        self.assertEqual(result["arithmetic_intensity"], 0.3125)
        self.assertEqual(result["classification"], "undetermined")
        self.assertNotIn("bound", result["classification"])
        self.assertEqual(result["limiting_regime"], original["limiting_regime"])
        self.assertEqual(original, before)


if __name__ == "__main__":
    unittest.main()
