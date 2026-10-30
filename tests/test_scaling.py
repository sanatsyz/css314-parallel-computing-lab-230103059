"""Numerical tests exercise halo exchange, uneven partitions and both buffers."""

import sys
from pathlib import Path
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from scaling_study import (  # noqa: E402
    _metrics, benchmark_once, fit_amdahl, init_grid, load_saved_array, process_counts,
    reference_stencil, save_array_parts,
)


def scalar_stencil(initial, steps):
    """A deliberately simple cell-by-cell oracle, separate from NumPy slices."""
    current = initial.copy()
    for _ in range(steps):
        updated = np.zeros_like(current)
        for row in range(1, current.shape[0] - 1):
            for col in range(1, current.shape[1] - 1):
                total = current[row, col] + current[row - 1, col]
                total += current[row + 1, col]
                total += current[row, col - 1]
                total += current[row, col + 1]
                updated[row, col] = total * 0.2
        current = updated
    return current


class StencilCorrectnessTests(unittest.TestCase):
    def test_lossless_output_round_trip_with_uneven_last_part(self):
        values = init_grid(11, 719)
        with tempfile.TemporaryDirectory() as temporary:
            # Four rows per part gives parts of 4, 4, 3 rows.
            manifest = save_array_parts(values, Path(temporary), max_part_bytes=11 * 8 * 4)
            np.testing.assert_array_equal(load_saved_array(manifest), values)
            import json
            metadata = json.loads(manifest.read_text())
            self.assertEqual([part["row_stop"] - part["row_start"] for part in metadata["parts"]], [4, 4, 3])
            self.assertTrue(all(part["uncompressed_value_bytes"] <= 11 * 8 * 4
                                for part in metadata["parts"]))
            # Altered bytes must not silently become a verified output.
            first_part = Path(temporary) / metadata["parts"][0]["path"]
            np.savez_compressed(first_part, values=np.ones((4, 11)))
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                load_saved_array(manifest)

    def test_seed_boundary_and_reference(self):
        initial = init_grid(8, 193)
        np.testing.assert_array_equal(initial, init_grid(8, 193))
        self.assertFalse(np.any(initial[[0, -1], :]))
        self.assertFalse(np.any(initial[:, [0, -1]]))
        original = initial.copy()
        np.testing.assert_array_equal(reference_stencil(initial, 5), scalar_stencil(initial, 5))
        np.testing.assert_array_equal(initial, original)

    def test_parallel_uneven_rows_odd_and_even_steps(self):
        for n, workers, steps in [(9, 2, 5), (10, 3, 4), (5, 1, 3)]:
            with self.subTest(n=n, workers=workers, steps=steps):
                initial = init_grid(n, 721)
                sample, actual = benchmark_once(initial, workers, steps, timeout=30)
                np.testing.assert_array_equal(actual, scalar_stencil(initial, steps))
                self.assertGreater(sample["kernel_seconds"], 0)
                self.assertGreater(sample["end_to_end_seconds"], sample["kernel_seconds"])
                spans = sample["row_ranges_exclusive_stop"]
                self.assertEqual(spans[0][0], 1)
                self.assertEqual(spans[-1][1], n - 1)
                self.assertTrue(all(a[1] == b[0] for a, b in zip(spans, spans[1:])))

    def test_physical_core_sequence(self):
        self.assertEqual(process_counts(10), [1, 2, 4, 8, 10])
        self.assertEqual(process_counts(8), [1, 2, 4, 8])
        self.assertEqual(process_counts(1), [1])

    def test_amdahl_fit_known_fraction_and_nonphysical_case(self):
        cases = [{"workers": p, "median_kernel_seconds": 0.2 + 0.8 / p}
                 for p in [1, 2, 4, 8]]
        fit = fit_amdahl(cases)
        self.assertAlmostEqual(fit["unconstrained_serial_fraction"], 0.2)
        self.assertAlmostEqual(fit["bounded_asymptotic_speedup"], 5)
        superlinear = fit_amdahl([{"workers": 1, "median_kernel_seconds": 1.0},
                                 {"workers": 2, "median_kernel_seconds": 0.1}])
        self.assertLess(superlinear["unconstrained_serial_fraction"], 0)
        self.assertEqual(superlinear["bounded_serial_fraction"], 0)
        self.assertIsNone(superlinear["bounded_asymptotic_speedup"])

    def test_assignment_and_conventional_weak_formulas_are_distinct(self):
        def case(p, work):
            return {"workers": p, "n": 8, "steps": 2, "work_cell_updates": work,
                    "median_kernel_seconds": 1.0, "minimum_kernel_seconds": 1.0,
                    "maximum_kernel_seconds": 1.0, "median_end_to_end_seconds": 2.0,
                    "max_absolute_error": 0.0}
        records = _metrics([case(1, 100)], [case(1, 100), case(4, 400)])
        largest = records[-1]
        self.assertEqual(largest["assignment_scaled_speedup"], 1.0)
        self.assertEqual(largest["conventional_throughput_speedup"], 4.0)
        self.assertEqual(largest["parallel_efficiency_percent"], 100.0)


if __name__ == "__main__":
    unittest.main()
