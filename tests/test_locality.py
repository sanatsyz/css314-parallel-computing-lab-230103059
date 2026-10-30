"""Numerical checks for salted parameters, native reads and both loop orders."""

from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dense_kernel import benchmark as dense_benchmark, multiply
from locality_native import load_library, pointer
from salt import get_student_params
from stride_bench import benchmark as stride_benchmark


class SaltTests(unittest.TestCase):
    def test_confirmed_student_id_has_stable_handout_parameters(self):
        expected = {
            "student_id": "30103059",
            "N": 1536,
            "buffer_elements": 16_777_216,
            "seed": 91405,
        }
        self.assertEqual(get_student_params("30103059"), expected)
        self.assertEqual(get_student_params("30103059"), expected)

    def test_ambiguous_or_non_ascii_identifiers_are_rejected(self):
        for identifier in ("230103059", "3010305", "30103O59", "３０１０３０５９", "30103059 "):
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                get_student_params(identifier)


class NativeStrideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library, _ = load_library()

    def test_stride_reads_correct_values_including_uneven_tails(self):
        # Binary fractions make these signed, nonuniform reference sums exact.
        values = (np.arange(43, dtype=np.float64) - 19) / 8
        for size in (0, 1, 5, 43):
            for stride in (1, 2, 3, 8, 16, 43, 50):
                with self.subTest(size=size, stride=stride):
                    result = self.library.stride_sum(pointer(values), size, stride)
                    self.assertEqual(result, sum(values[:size:stride]))

    def test_benchmark_records_all_warmups_samples_and_actual_touch_counts(self):
        rows, raw = stride_benchmark(elements=259)
        self.assertEqual([row["stride_elements"] for row in rows], [1, 2, 4, 8, 16, 32, 64, 128])
        self.assertEqual(raw["buffer_bytes"], 259 * 8)
        self.assertEqual(len(raw["runs"]), len(rows))
        for row, run in zip(rows, raw["runs"]):
            with self.subTest(stride=row["stride_elements"]):
                touched = len(range(0, 259, row["stride_elements"]))
                self.assertEqual(row["elements_touched"], touched)
                self.assertEqual(row["sum"], touched)
                self.assertEqual(run["verified_sum"], touched)
                self.assertEqual(len(run["warmup_time_ns"]), 5)
                self.assertEqual(len(run["time_ns"]), 5)
                self.assertEqual(row["ns_per_element"], row["median_time_ns"] / touched)


class DenseKernelTests(unittest.TestCase):
    def test_both_loop_orders_match_numpy_for_signed_noncontiguous_inputs(self):
        rng = np.random.default_rng(712)
        # Odd dimensions expose tail errors; these views also require conversion.
        a = rng.uniform(-2, 2, (14, 14))[::2, ::2]
        b = rng.uniform(-2, 2, (7, 7)).T
        before_a, before_b = a.copy(), b.copy()
        expected = a @ b
        for order in ("ijk", "ikj"):
            with self.subTest(order=order):
                actual = multiply(a, b, order)
                np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-12)
                np.testing.assert_array_equal(a, before_a)
                np.testing.assert_array_equal(b, before_b)

    def test_invalid_orders_and_incompatible_shapes_are_rejected(self):
        with self.assertRaises(ValueError):
            multiply(np.ones((3, 3)), np.ones((3, 3)), "jki")
        for a, b in ((np.ones((3, 2)), np.ones((3, 2))),
                     (np.ones((3, 3)), np.ones((2, 2))),
                     (np.ones(3), np.ones(3))):
            with self.subTest(a=a.shape, b=b.shape), self.assertRaises(ValueError):
                multiply(a, b, "ijk")

    def test_benchmark_preserves_recomputable_inputs_and_three_trials(self):
        result, arrays = dense_benchmark(n=10, seed=91405)
        self.assertEqual((result["N"], result["M"]), (10, 5))
        expected = arrays["dense_a"] @ arrays["dense_b"]
        for order in ("ijk", "ikj"):
            with self.subTest(order=order):
                self.assertEqual(len(result["time_ns"][order]), 3)
                self.assertEqual(arrays["dense_" + order].shape, (5, 5))
                np.testing.assert_allclose(arrays["dense_" + order], expected, rtol=0, atol=1e-12)


if __name__ == "__main__":
    unittest.main()
