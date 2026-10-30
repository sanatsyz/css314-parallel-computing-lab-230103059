"""Numerical and real spawn checks for Variant B Collatz dispatch."""

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from exp_a_granularity import (collatz_checksum_reference, collatz_steps,
                               run_granularity, run_trial)


def independent_steps(n):
    """Count the trajectory length from an explicit sequence."""
    trajectory = [n]
    while trajectory[-1] != 1:
        value = trajectory[-1]
        trajectory.append(3 * value + 1 if value & 1 else value >> 1)
    return len(trajectory) - 1


class GranularityTests(unittest.TestCase):
    def test_known_collatz_lengths(self):
        for value, expected in ((1, 0), (2, 1), (3, 7), (6, 8), (27, 111)):
            with self.subTest(value=value):
                self.assertEqual(collatz_steps(value), expected)

    def test_memoized_oracle_agrees_with_independent_sequences(self):
        for count in (0, 1, 2, 17, 113):
            with self.subTest(count=count):
                expected = sum(independent_steps(value) for value in range(1, count + 1))
                self.assertEqual(collatz_checksum_reference(count), expected)

    def test_spawn_micro_and_coarse_return_all_uneven_inputs(self):
        count = 37
        expected = sum(independent_steps(value) for value in range(1, count + 1))
        for chunk_size in (1, 10_000):
            with self.subTest(chunk_size=chunk_size):
                trial = run_trial(2, count, chunk_size)
                self.assertEqual(trial["result_count"], count)
                self.assertEqual(trial["result_sum"], expected)
                self.assertEqual(trial["chunk_size"], chunk_size)
                self.assertEqual(trial["start_method"], "spawn")
                self.assertGreater(trial["runtime_seconds"], 0)

    def test_zero_inputs_still_has_a_valid_empty_reduction(self):
        trial = run_trial(1, 0, 1)
        self.assertEqual((trial["result_count"], trial["result_sum"]), (0, 0))

    def test_wrapper_preserves_handout_interface(self):
        with patch("exp_a_granularity.run_trial", return_value={
                "runtime_seconds": 1.25, "result_sum": 91}) as trial:
            self.assertEqual(run_granularity(4, 37, 1), (1.25, 91))
            trial.assert_called_once_with(4, 37, 1)

    def test_invalid_inputs_rejected_before_creating_pool(self):
        invalid = ((0, 3, 1), (True, 3, 1), (1.5, 3, 1),
                   (1, -1, 1), (1, True, 1), (1, 3, 0), (1, 3, 1.5))
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(ValueError):
                run_trial(*values)
        for count in (-1, True, 1.5):
            with self.subTest(reference_count=count), self.assertRaises(ValueError):
                collatz_checksum_reference(count)


if __name__ == "__main__":
    unittest.main()
