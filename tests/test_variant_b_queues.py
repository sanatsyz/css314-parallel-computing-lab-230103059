"""Actual spawn/IPC tests including tails, zero work and failed producers."""

from pathlib import Path
import sys
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import exp_b_queue as queued
import exp_c_buffered as buffered


def _crash_worker(out_queue, items_per_worker, *args):
    raise RuntimeError("intentional test producer crash")


def _incomplete_worker(out_queue, items_per_worker, *args):
    # Successful exit with no records/sentinels must not leave get() hanging.
    return


class VariantBQueueTests(unittest.TestCase):
    def _expected(self, counts):
        return sum(sum(i % 7 for i in range(count)) for count in counts)

    def test_individual_queue_preserves_records_and_worker_local_sequence(self):
        for workers, total in ((1, 37), (2, 103), (4, 1003), (8, 2)):
            with self.subTest(workers=workers, total=total):
                sample = queued.run_trial(workers, total)
                self.assertEqual(sample["result_count"], total)
                self.assertEqual(sample["received_messages"], total)
                self.assertEqual(sum(sample["worker_items"]), total)
                self.assertEqual(sample["result_sum"], self._expected(sample["worker_items"]))
                self.assertEqual(sample["worker_exitcodes"], [0] * workers)
                self.assertGreater(sample["runtime_seconds"], 0)

    def test_buffered_queue_preserves_partial_batches_and_sentinels(self):
        for workers, total, batch in ((1, 37, 10), (2, 103, 7), (4, 1003, 100), (8, 2, 5)):
            with self.subTest(workers=workers, total=total, batch=batch):
                sample = buffered.run_trial(workers, total, batch)
                self.assertEqual(sample["result_count"], total)
                self.assertEqual(sum(sample["worker_items"]), total)
                self.assertEqual(sample["result_sum"], self._expected(sample["worker_items"]))
                expected_batches = sum((count + batch - 1) // batch for count in sample["worker_items"])
                self.assertEqual(sample["received_batches"], expected_batches)
                self.assertEqual(sample["sentinels_received"], workers)
                self.assertEqual(sample["received_messages"], expected_batches)
                self.assertEqual(sample["total_received_messages"], expected_batches + workers)
                self.assertEqual(sample["worker_exitcodes"], [0] * workers)

    def test_zero_records_still_completes(self):
        for module in (queued, buffered):
            with self.subTest(module=module.__name__):
                sample = module.run_trial(2, 0)
                self.assertEqual(sample["worker_items"], [0, 0])
                self.assertEqual(sample["result_count"], 0)
                self.assertEqual(sample["result_sum"], 0)
                if module is buffered:
                    self.assertEqual(sample["received_batches"], 0)
                    self.assertEqual(sample["sentinels_received"], 2)

    def test_worker_failure_and_incomplete_success_do_not_hang_consumers(self):
        for module, attribute in ((queued, "queue_worker"), (buffered, "buffered_worker")):
            for target in (_crash_worker, _incomplete_worker):
                with self.subTest(module=module.__name__, target=target.__name__):
                    with patch.object(module, attribute, target):
                        with self.assertRaisesRegex(RuntimeError, "workers exited"):
                            module.run_trial(2, 31)

    def test_invalid_parameters_fail_before_starting_processes(self):
        for module in (queued, buffered):
            for workers, total in ((0, 10), (-1, 10), (2, -1), (1.5, 10), (2, 3.5), (True, 3), (2, False)):
                with self.subTest(module=module.__name__, workers=workers, total=total):
                    with self.assertRaises((ValueError, TypeError)):
                        module.run_trial(workers, total)
        for batch in (0, -1, 1.5, True):
            with self.assertRaises(ValueError):
                buffered.run_trial(1, 10, batch)

    def test_handout_wrappers_keep_return_contract(self):
        self.assertGreater(queued.run_queue_benchmark(1, 7), 0)
        seconds, checksum = buffered.run_buffered(1, 13, 5)
        self.assertGreater(seconds, 0)
        self.assertEqual(checksum, sum(i % 7 for i in range(13)))


if __name__ == "__main__":
    unittest.main()
