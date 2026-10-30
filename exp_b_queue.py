"""Variant B experiment B: individual records contend on a shared IPC queue."""

import argparse
import multiprocessing as mp
from pathlib import Path
import threading
import time

from variant_b_support import DEFAULT_DIR, WORKERS, partition_work, pattern_sum, write_case


DEFAULT_TOTAL_ITEMS = 400_000
_MONITOR_TOKEN = "variant-b-worker-exit-diagnostic"


def queue_worker(out_queue, items_per_worker):
    """Send every individual record through the shared queue, as prescribed."""
    for i in range(items_per_worker):
        out_queue.put(i % 7)


class _QueueMonitor:
    """Wake a blocked consumer if a worker crashes or exits without enough data.

    Normal receives remain blocking Queue.get(), without a polling syscall for
    every record. The monitor checks exit codes only every 0.1 seconds, and never
    sends a token while successful worker feeder threads are still flushing.
    """

    def __init__(self, out_queue, processes):
        self.out_queue = out_queue
        self.processes = processes
        self.armed = threading.Event()
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self._watch, daemon=True)

    def start(self):
        self.thread.start()

    def _watch(self):
        while not self.stopped.wait(0.1):
            if not self.armed.is_set():
                continue
            codes = [process.exitcode for process in self.processes]
            if any(code is not None and code != 0 for code in codes) or all(
                code is not None for code in codes
            ):
                # Queue.put is unbounded and returns before its feeder writes.
                # Cleanup first joins this monitor; no puts can race Queue.close.
                self.out_queue.put((_MONITOR_TOKEN, codes))
                return

    def stop(self):
        self.stopped.set()
        self.thread.join()


def _receive(out_queue):
    value = out_queue.get()
    if isinstance(value, tuple) and value and value[0] == _MONITOR_TOKEN:
        raise RuntimeError("queue workers exited before all expected messages; exit codes: {!r}".format(value[1]))
    return value


def _finish_queue(out_queue, processes, monitor, succeeded):
    """Reap processes and close handles after the measured interval."""
    monitor.stop()
    for process in processes:
        if process.pid is not None and process.is_alive():
            process.terminate()
    for process in processes:
        if process.pid is not None:
            process.join()
    if not succeeded:
        # A failed consumer must not wait for a parent diagnostic feeder whose
        # pipe could be full of records from the terminated producers.
        out_queue.cancel_join_thread()
    out_queue.close()
    if succeeded:
        out_queue.join_thread()
    for process in processes:
        process.close()


def run_trial(p, total_items=DEFAULT_TOTAL_ITEMS):
    """Time starts, individual receives and joins; queue setup/cleanup excluded."""
    counts = partition_work(total_items, p)
    expected_sum = sum(pattern_sum(count) for count in counts)
    context = mp.get_context("spawn")
    out_queue = context.Queue()
    processes = [context.Process(target=queue_worker, args=(out_queue, count)) for count in counts]
    monitor = _QueueMonitor(out_queue, processes)
    monitor.start()
    succeeded = False
    try:
        t0 = time.perf_counter()
        for process in processes:
            process.start()
        monitor.armed.set()
        collected, total_sum = 0, 0
        while collected < total_items:
            value = _receive(out_queue)
            total_sum += value
            collected += 1
        for process in processes:
            process.join()
        runtime = time.perf_counter() - t0
        exitcodes = [process.exitcode for process in processes]
        if any(code != 0 for code in exitcodes):
            raise RuntimeError("queue worker failed; exit codes: {!r}".format(exitcodes))
        if total_sum != expected_sum:
            raise RuntimeError("queue checksum mismatch: expected {}, observed {}".format(expected_sum, total_sum))
        succeeded = True
        return {
            "workers": p, "runtime_seconds": runtime, "total_items": total_items,
            "worker_items": counts, "result_count": collected,
            "result_sum": total_sum, "expected_sum": expected_sum,
            "received_messages": collected, "worker_exitcodes": exitcodes,
            "start_method": "spawn", "counts_verified": True,
        }
    finally:
        _finish_queue(out_queue, processes, monitor, succeeded)


def run_queue_benchmark(p, total_items=DEFAULT_TOTAL_ITEMS):
    """Handout-compatible entry point returning elapsed seconds."""
    return run_trial(p, total_items)["runtime_seconds"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--total-items", type=int, default=None)
    parser.add_argument("--quick", action="store_true", help="small smoke run beneath OUTPUT_DIR/smoke")
    args = parser.parse_args(argv)
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    total = args.total_items if args.total_items is not None else (4_000 if args.quick else DEFAULT_TOTAL_ITEMS)
    if total < 0:
        parser.error("--total-items must be nonnegative")
    output_dir = args.output_dir / "smoke" if args.quick else args.output_dir
    samples = []
    for repeat in range(1, args.repeats + 1):
        offset = (repeat - 1) % len(WORKERS)
        for p in WORKERS[offset:] + WORKERS[:offset]:
            sample = run_trial(p, total)
            sample["repeat"] = repeat
            samples.append(sample)
            print("B repeat={} P={} runtime={:.6f}s records={} checksum={}".format(
                repeat, p, sample["runtime_seconds"], sample["result_count"], sample["result_sum"]), flush=True)
    config = {
        "total_items": total, "repeats": args.repeats, "workers": list(WORKERS),
        "start_method": "spawn", "quick": args.quick,
        "timing_scope": "process start through all queue receives and joins; setup/cleanup excluded",
        "worker_order": "rotate (1, 2, 4, 8) left by repeat index modulo 4",
        "parent_checksums_timed": True, "monitor_interval_seconds": 0.1,
    }
    notes = [
        "Every worker starts i at zero and sends i % 7 individually through one shared Queue.",
        "Division remainders are assigned exactly; total work is fixed as P changes.",
        "The timed parent additionally accumulates a checksum to validate record contents.",
        "A low-frequency exit monitor wakes failed/incomplete runs; normal receives use blocking Queue.get().",
        "Monitor setup/teardown and Queue resource cleanup occur outside the reported interval.",
        "Observed performance is retained without enforcing the handout's expected trend.",
    ]
    write_case(output_dir, "b_queue", samples, config, notes)
    print("Experiment B results written to {}".format(output_dir))


if __name__ == "__main__":
    main()
