"""Variant B experiment C: aggregate local buffers before shared-queue sends."""

import argparse
import multiprocessing as mp
from pathlib import Path
import time

from exp_b_queue import _QueueMonitor, _finish_queue, _receive
from variant_b_support import DEFAULT_DIR, WORKERS, partition_work, pattern_sum, write_case


DEFAULT_TOTAL_ITEMS = 10_000_000
DEFAULT_BATCH_SIZE = 10_000


def buffered_worker(out_queue, items_per_worker, batch_size=DEFAULT_BATCH_SIZE):
    """Follow the handout's list accumulation, sum/clear, and final sentinel."""
    buffer = []
    for i in range(items_per_worker):
        buffer.append(i % 7)
        if len(buffer) >= batch_size:
            out_queue.put(sum(buffer))
            buffer.clear()
    if buffer:
        out_queue.put(sum(buffer))
    out_queue.put(None)


def run_trial(p, total_items=DEFAULT_TOTAL_ITEMS, batch_size=DEFAULT_BATCH_SIZE):
    counts = partition_work(total_items, p)
    if not isinstance(batch_size, int) or isinstance(batch_size, bool) or batch_size < 1:
        raise ValueError("batch_size must be a positive integer")
    expected_sum = sum(pattern_sum(count) for count in counts)
    expected_batches = sum((count + batch_size - 1) // batch_size for count in counts)
    context = mp.get_context("spawn")
    out_queue = context.Queue()
    processes = [context.Process(target=buffered_worker, args=(out_queue, count, batch_size)) for count in counts]
    monitor = _QueueMonitor(out_queue, processes)
    monitor.start()
    succeeded = False
    try:
        t0 = time.perf_counter()
        for process in processes:
            process.start()
        monitor.armed.set()
        total_sum, sentinels, batches = 0, 0, 0
        while sentinels < p:
            value = _receive(out_queue)
            if value is None:
                sentinels += 1
            else:
                total_sum += value
                batches += 1
        for process in processes:
            process.join()
        runtime = time.perf_counter() - t0
        exitcodes = [process.exitcode for process in processes]
        if any(code != 0 for code in exitcodes):
            raise RuntimeError("buffered worker failed; exit codes: {!r}".format(exitcodes))
        if total_sum != expected_sum or batches != expected_batches:
            raise RuntimeError("buffered checksum/batch mismatch: expected ({}, {}), observed ({}, {})".format(
                expected_sum, expected_batches, total_sum, batches))
        succeeded = True
        return {
            "workers": p, "runtime_seconds": runtime, "total_items": total_items,
            "worker_items": counts, "result_count": total_items,
            "result_sum": total_sum, "expected_sum": expected_sum,
            "batch_size": batch_size, "received_batches": batches,
            "sentinels_received": sentinels, "received_messages": batches,
            "total_received_messages": batches + sentinels,
            "worker_exitcodes": exitcodes, "start_method": "spawn", "counts_verified": True,
        }
    finally:
        _finish_queue(out_queue, processes, monitor, succeeded)


def run_buffered(p, total_items=DEFAULT_TOTAL_ITEMS, batch_size=DEFAULT_BATCH_SIZE):
    """Handout-compatible entry point returning (elapsed seconds, checksum)."""
    sample = run_trial(p, total_items, batch_size)
    return sample["runtime_seconds"], sample["result_sum"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--total-items", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--quick", action="store_true", help="small smoke run beneath OUTPUT_DIR/smoke")
    args = parser.parse_args(argv)
    if args.repeats < 1 or args.batch_size < 1:
        parser.error("--repeats and --batch-size must be at least 1")
    total = args.total_items if args.total_items is not None else (40_000 if args.quick else DEFAULT_TOTAL_ITEMS)
    if total < 0:
        parser.error("--total-items must be nonnegative")
    output_dir = args.output_dir / "smoke" if args.quick else args.output_dir
    samples = []
    for repeat in range(1, args.repeats + 1):
        offset = (repeat - 1) % len(WORKERS)
        for p in WORKERS[offset:] + WORKERS[:offset]:
            sample = run_trial(p, total, args.batch_size)
            sample["repeat"] = repeat
            samples.append(sample)
            print("C repeat={} P={} runtime={:.6f}s records={} batches={} checksum={}".format(
                repeat, p, sample["runtime_seconds"], sample["result_count"],
                sample["received_batches"], sample["result_sum"]), flush=True)
    config = {
        "total_items": total, "batch_size": args.batch_size,
        "repeats": args.repeats, "workers": list(WORKERS),
        "start_method": "spawn", "quick": args.quick,
        "timing_scope": "process start through all batch/sentinel receives and joins; setup/cleanup excluded",
        "worker_order": "rotate (1, 2, 4, 8) left by repeat index modulo 4",
        "monitor_interval_seconds": 0.1,
    }
    notes = [
        "Workers append i % 7 to private lists, send each batch sum, clear the list, then send a None sentinel.",
        "Partial final batches are flushed; all division remainders are assigned exactly.",
        "Each worker restarts i at zero, so the independent checksum uses its own item count.",
        "The timed parent combines batch sums; individual records never traverse the queue.",
        "A low-frequency exit monitor wakes failed/incomplete runs; normal receives use blocking Queue.get().",
        "Monitor setup/teardown and Queue resource cleanup occur outside the reported interval.",
        "Observed performance is retained without enforcing the handout's expected trend.",
    ]
    write_case(output_dir, "c_buffered", samples, config, notes)
    print("Experiment C results written to {}".format(output_dir))


if __name__ == "__main__":
    main()
