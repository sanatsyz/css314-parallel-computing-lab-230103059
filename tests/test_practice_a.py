"""Small numerical and spawn tests for the serial-tail practice experiment."""

import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from exp_a_serial import heavy_math, run_experiment, run_trial


class SerialTailTests(unittest.TestCase):
    def test_workload_matches_independent_trigonometric_oracle(self):
        # sin(i)cos(i) = sin(2i)/2, independently of the workload expression.
        for n in (0, 1, 2, 17, 113):
            expected = math.fsum(0.5 * math.sin(2 * i) for i in range(1, n))
            with self.subTest(n=n):
                self.assertAlmostEqual(heavy_math(n), expected, places=12)

    def test_spawn_returns_every_chunk_and_includes_serial_pause(self):
        pause = 0.025
        expected = math.fsum(0.5 * math.sin(2 * i) for i in range(1, 73))
        trial = run_trial(2, total_chunks=5, chunk_size=73, serial_pause=pause)
        self.assertEqual(trial["workers"], 2)
        self.assertEqual(len(trial["chunk_results"]), 5)
        for actual in trial["chunk_results"]:
            self.assertAlmostEqual(actual, expected, places=12)
        self.assertEqual(trial["total_result"], sum(trial["chunk_results"]))
        self.assertGreaterEqual(trial["runtime_seconds"], pause)
        self.assertGreaterEqual(trial["phase_sleep_seconds"], pause)
        self.assertGreater(trial["phase_pool_seconds"], 0)
        self.assertAlmostEqual(trial["runtime_seconds"],
                               trial["phase_sleep_seconds"] + trial["phase_pool_seconds"])

    def test_runtime_wrapper_preserves_handout_interface(self):
        with patch("exp_a_serial.run_trial", return_value={"runtime_seconds": 1.25}) as trial:
            self.assertEqual(run_experiment(4, 8, 17), 1.25)
            trial.assert_called_once_with(4, 8, 17, 0.40)

    def test_invalid_inputs_fail_before_creating_a_pool(self):
        invalid = [
            {"workers": 0}, {"workers": True}, {"workers": 1.5},
            {"workers": 1, "total_chunks": 0},
            {"workers": 1, "chunk_size": 0},
            {"workers": 1, "serial_pause": -0.1},
            {"workers": 1, "serial_pause": float("nan")},
            {"workers": 1, "serial_pause": float("inf")},
        ]
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                run_trial(**kwargs)


if __name__ == "__main__":
    unittest.main()
