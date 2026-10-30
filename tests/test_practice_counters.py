"""Counter correctness with real spawn workers; no machine-dependent speed tests."""

from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import exp_b_contention as contention  # noqa: E402
import exp_c_fixed as privatized  # noqa: E402


class PracticeCounterTests(unittest.TestCase):
    def test_contended_spawn_preserves_uneven_fixed_work(self):
        for workers, total in ((1, 37), (2, 103), (4, 1003), (4, 2)):
            with self.subTest(workers=workers, total=total):
                sample = contention.run_trial(workers, total)
                self.assertEqual(sample["total_count"], total)
                self.assertEqual(sample["expected_total"], total)
                self.assertEqual(sum(sample["worker_iterations"]), total)
                self.assertEqual(len(sample["worker_iterations"]), workers)
                self.assertLessEqual(
                    max(sample["worker_iterations"]) - min(sample["worker_iterations"]), 1
                )
                self.assertEqual(sample["worker_exitcodes"], [0] * workers)
                self.assertEqual(sample["start_method"], "spawn")
                self.assertTrue(sample["counts_verified"])
                self.assertTrue(sample["value_uses_default_lock"])
                self.assertTrue(sample["explicit_lock_per_increment"])
                self.assertGreater(sample["runtime_seconds"], 0)

    def test_privatized_spawn_preserves_uneven_fixed_work(self):
        for workers, total in ((1, 37), (2, 103), (4, 1003), (4, 2)):
            with self.subTest(workers=workers, total=total):
                sample = privatized.run_trial(workers, total)
                self.assertEqual(sample["worker_counts"], sample["worker_iterations"])
                self.assertEqual(sum(sample["worker_counts"]), total)
                self.assertEqual(sample["total_count"], total)
                self.assertEqual(sample["expected_total"], total)
                self.assertEqual(len(sample["worker_counts"]), workers)
                self.assertEqual(sample["start_method"], "spawn")
                self.assertTrue(sample["counts_verified"])
                self.assertFalse(sample["shared_counter"])
                self.assertGreater(sample["runtime_seconds"], 0)

    def test_zero_work_still_produces_exact_counts(self):
        for module in (contention, privatized):
            with self.subTest(module=module.__name__):
                sample = module.run_trial(2, 0)
                self.assertEqual(sample["worker_iterations"], [0, 0])
                self.assertEqual(sample["total_count"], 0)

    def test_invalid_inputs_rejected_before_workers_start(self):
        for module in (contention, privatized):
            for workers, total in ((0, 10), (-1, 10), (2, -1), (1.5, 10), (2, 3.5)):
                with self.subTest(module=module.__name__, workers=workers, total=total):
                    with self.assertRaises((TypeError, ValueError)):
                        module.run_trial(workers, total)
        with self.assertRaisesRegex(ValueError, "Value"):
            contention.run_trial(1, 1 << 64)

    def test_handout_wrappers_return_seconds(self):
        self.assertGreater(contention.run_contended(1, 7), 0)
        self.assertGreater(privatized.run_privatized(1, 7), 0)

    def test_private_worker_is_an_exact_integer_reduction(self):
        self.assertEqual(privatized.private_worker(0), 0)
        self.assertEqual(privatized.private_worker(137), 137)


if __name__ == "__main__":
    unittest.main()
