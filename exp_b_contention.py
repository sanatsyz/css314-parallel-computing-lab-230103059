"""Experiment B: many spawned processes contend on one shared counter.

The synchronized Value intentionally keeps its own default lock, in addition
to the explicit outer Lock. This follows the handout literally; every increment
therefore pays for both synchronization layers.
"""

import argparse
import multiprocessing as mp
from pathlib import Path
import struct
import time

from practice_support import partition_work, write_experiment


DEFAULT_TOTAL_INCREMENTS = 2_000_000
WORKERS = (1, 2, 4)


def contended_worker(shared_counter, lock, iterations):
    """Increment the shared integer while holding the explicit common lock."""
    for _ in range(iterations):
        with lock:
            shared_counter.value += 1


def run_trial(p, total_increments=DEFAULT_TOTAL_INCREMENTS):
    """Run one fixed-work trial, including process startup and joins in time."""
    iterations = partition_work(total_increments, p)
    # Value('i') is a signed C int, exactly as in the instructor's example.
    max_counter = (1 << (8 * struct.calcsize("i") - 1)) - 1
    if total_increments > max_counter:
        raise ValueError("total_increments exceeds the range of Value('i')")

    context = mp.get_context("spawn")
    counter = context.Value("i", 0)
    lock = context.Lock()
    processes = [
        context.Process(target=contended_worker, args=(counter, lock, count))
        for count in iterations
    ]
    started = []
    t0 = time.perf_counter()
    try:
        for process in processes:
            process.start()
            started.append(process)
        for process in processes:
            process.join()
        t1 = time.perf_counter()
    except BaseException:
        for process in started:
            if process.is_alive():
                process.terminate()
        for process in started:
            process.join()
        raise

    exitcodes = [process.exitcode for process in processes]
    if any(code != 0 for code in exitcodes):
        raise RuntimeError("counter worker failed; exit codes: {!r}".format(exitcodes))
    total = counter.value
    if total != total_increments:
        raise RuntimeError(
            "counter mismatch: expected {}, observed {}".format(total_increments, total)
        )
    return {
        "workers": p,
        "runtime_seconds": t1 - t0,
        "total_count": total,
        "expected_total": total_increments,
        "worker_iterations": iterations,
        "worker_exitcodes": exitcodes,
        "counts_verified": True,
        "start_method": "spawn",
        "counter_type": "synchronized Value('i')",
        "value_uses_default_lock": True,
        "explicit_lock_per_increment": True,
    }


def run_contended(p, total_increments=DEFAULT_TOTAL_INCREMENTS):
    """Handout-compatible entry point returning only elapsed seconds."""
    return run_trial(p, total_increments)["runtime_seconds"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, default=Path("practice_results"))
    parser.add_argument("--total-increments", type=int, default=None)
    parser.add_argument(
        "--quick", action="store_true",
        help="use a small smoke-test workload and write beneath OUTPUT_DIR/smoke",
    )
    args = parser.parse_args(argv)
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    total = args.total_increments
    if total is None:
        total = 10_000 if args.quick else DEFAULT_TOTAL_INCREMENTS
    if total < 0:
        parser.error("--total-increments must be nonnegative")
    output_dir = args.output_dir / "smoke" if args.quick else args.output_dir

    samples = []
    for repeat in range(1, args.repeats + 1):
        offset = (repeat - 1) % len(WORKERS)
        order = WORKERS[offset:] + WORKERS[:offset]
        for p in order:
            sample = run_trial(p, total)
            sample["repeat"] = repeat
            samples.append(sample)
            print("B repeat={} P={} runtime={:.6f}s count={}".format(
                repeat, p, sample["runtime_seconds"], sample["total_count"]
            ), flush=True)

    config = {
        "total_increments": total,
        "repeats": args.repeats,
        "workers": list(WORKERS),
        "start_method": "spawn",
        "quick": args.quick,
        "timing_scope": "process start through all joins; process objects created before timer",
        "worker_order": "rotate (1, 2, 4) left by repeat index modulo 3",
    }
    notes = [
        "Literal handout synchronization: Value('i', 0) retains its default lock, "
        "and a separate common Lock protects each read-modify-write increment.",
        "Fixed total work is partitioned with remainders preserved; it is not multiplied by P.",
        "Timing includes spawn startup and worker teardown, without subtracting overhead.",
        "Measured speedup and Karp-Flatt values are reported as observed, without enforcing a trend.",
    ]
    write_experiment(output_dir, "B", samples, config, notes)
    print("Experiment B results written to {}".format(output_dir))


if __name__ == "__main__":
    main()
