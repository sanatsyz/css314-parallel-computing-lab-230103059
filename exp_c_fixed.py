"""Experiment C: private per-process counters followed by one reduction."""

import argparse
import multiprocessing as mp
from pathlib import Path
import time

from practice_support import partition_work, write_experiment


DEFAULT_TOTAL_INCREMENTS = 20_000_000
WORKERS = (1, 2, 4)


def private_worker(iterations):
    """Accumulate in private memory without shared state or explicit locks."""
    local_sum = 0
    for _ in range(iterations):
        local_sum += 1
    return local_sum


def run_trial(p, total_increments=DEFAULT_TOTAL_INCREMENTS):
    """Time a fresh spawn Pool, map, teardown, and final sum as in the handout."""
    iterations = partition_work(total_increments, p)
    context = mp.get_context("spawn")
    t0 = time.perf_counter()
    with context.Pool(processes=p) as pool:
        counts = pool.map(private_worker, iterations)
    total = sum(counts)
    t1 = time.perf_counter()

    if counts != iterations or total != total_increments:
        raise RuntimeError(
            "private counter mismatch: expected {}, observed {}".format(iterations, counts)
        )
    return {
        "workers": p,
        "runtime_seconds": t1 - t0,
        "worker_counts": counts,
        "worker_iterations": iterations,
        "total_count": total,
        "expected_total": total_increments,
        "counts_verified": True,
        "start_method": "spawn",
        "shared_counter": False,
    }


def run_privatized(p, total_increments=DEFAULT_TOTAL_INCREMENTS):
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
        total = 100_000 if args.quick else DEFAULT_TOTAL_INCREMENTS
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
            print("C repeat={} P={} runtime={:.6f}s count={}".format(
                repeat, p, sample["runtime_seconds"], sample["total_count"]
            ), flush=True)

    config = {
        "total_increments": total,
        "repeats": args.repeats,
        "workers": list(WORKERS),
        "start_method": "spawn",
        "quick": args.quick,
        "timing_scope": "before fresh Pool creation through teardown and final sum",
        "worker_order": "rotate (1, 2, 4) left by repeat index modulo 3",
    }
    notes = [
        "Each worker counts in a local variable; the parent sums returned counts once.",
        "Fixed total work is partitioned with remainders preserved; it is not multiplied by P.",
        "Each trial uses a fresh spawn Pool; startup, IPC, teardown, and final reduction are timed.",
        "Measured speedup and Karp-Flatt values are reported as observed, without enforcing a trend.",
    ]
    write_experiment(output_dir, "C", samples, config, notes)
    print("Experiment C results written to {}".format(output_dir))


if __name__ == "__main__":
    main()
