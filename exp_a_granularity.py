"""Variant B experiment A: fine and coarse Collatz process-pool dispatch.

Each timed trial uses the handout's scalar Collatz loop and a fresh spawn
Pool. Checksums are reduced after the timer, matching the handout's scope.
"""

import argparse
import multiprocessing as mp
from pathlib import Path
import time


DEFAULT_TOTAL_ITEMS = 1_000_000
WORKER_COUNTS = (1, 2, 4, 8)
CASES = (("a_micro", 1), ("a_coarse", 10_000))


def collatz_steps(n):
    """Perform the exact scalar Collatz loop from the handout."""
    steps = 0
    while n > 1:
        n = n // 2 if n % 2 == 0 else 3 * n + 1
        steps += 1
    return steps


def _integer(value, name, minimum):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError("{} must be an integer >= {}".format(name, minimum))


def collatz_checksum_reference(total_items):
    """Memoized untimed oracle; this optimization never enters the workload.

    Store lengths only for values in the input range, so reference memory is
    bounded by the requested input size rather than all trajectory peaks.
    """
    _integer(total_items, "total_items", 0)
    if total_items == 0:
        return 0
    known = [-1] * (total_items + 1)
    known[1] = 0
    checksum = 0
    for start in range(1, total_items + 1):
        value, path = start, []
        while value > total_items or known[value] < 0:
            path.append(value)
            value = (value >> 1) if (value & 1) == 0 else 3 * value + 1
        length = known[value]
        for value in reversed(path):
            length += 1
            if value <= total_items:
                known[value] = length
        checksum += known[start]
    return checksum


def run_trial(workers, total_items=DEFAULT_TOTAL_ITEMS, chunk_size=1):
    """Time fresh Pool creation, map and teardown; then reduce its results."""
    _integer(workers, "workers", 1)
    _integer(total_items, "total_items", 0)
    _integer(chunk_size, "chunk_size", 1)
    context = mp.get_context("spawn")
    numbers = range(1, total_items + 1)
    started = time.perf_counter()
    with context.Pool(processes=workers) as pool:
        results = pool.map(collatz_steps, numbers, chunksize=chunk_size)
    finished = time.perf_counter()
    checksum = sum(results)
    if len(results) != total_items:
        raise RuntimeError("Pool returned an incorrect number of Collatz results")
    return {
        "workers": workers,
        "runtime_seconds": finished - started,
        "total_items": total_items,
        "chunk_size": chunk_size,
        "result_count": len(results),
        "result_sum": checksum,
        "start_method": "spawn",
    }


def run_granularity(workers, total_items=DEFAULT_TOTAL_ITEMS, chunk_size=1):
    """Return the handout-compatible (elapsed seconds, checksum) pair."""
    trial = run_trial(workers, total_items, chunk_size)
    return trial["runtime_seconds"], trial["result_sum"]


def main(argv=None):
    from variant_b_support import DEFAULT_DIR, write_case

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--total-items", type=int, default=DEFAULT_TOTAL_ITEMS)
    parser.add_argument("--case", choices=("micro", "coarse", "both"), default="both")
    parser.add_argument("--quick", action="store_true",
                        help="use 1000 inputs and write beneath OUTPUT_DIR/smoke")
    args = parser.parse_args(argv)
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    if args.total_items < 0:
        parser.error("--total-items must be nonnegative")
    if args.quick:
        args.total_items = 1_000
        args.output_dir = args.output_dir / "smoke"

    # A fast reference keeps validation outside every measured Pool run.
    reference = collatz_checksum_reference(args.total_items)
    cases = CASES if args.case == "both" else tuple(
        pair for pair in CASES if pair[0] == "a_" + args.case)
    payloads = []
    for case_id, chunk_size in cases:
        samples = []
        for repeat in range(1, args.repeats + 1):
            offset = (repeat - 1) % len(WORKER_COUNTS)
            order = WORKER_COUNTS[offset:] + WORKER_COUNTS[:offset]
            for workers in order:
                sample = run_trial(workers, args.total_items, chunk_size)
                if sample["result_sum"] != reference:
                    raise ArithmeticError("Collatz checksum differs from the untimed reference")
                sample.update(repeat=repeat, correctness_passed=True)
                samples.append(sample)
                print("{} repeat={} P={} runtime={:.6f}s checksum={}".format(
                    case_id, repeat, workers, sample["runtime_seconds"],
                    sample["result_sum"]), flush=True)
        config = {
            "total_items": args.total_items, "chunk_size": chunk_size,
            "repeats": args.repeats, "workers": list(WORKER_COUNTS),
            "start_method": "spawn", "quick": args.quick,
            "timing_scope": "fresh Pool creation through map and teardown; checksum reduction excluded",
            "worker_order": "rotate (1, 2, 4, 8) left by repeat index modulo 4",
        }
        notes = [
            "Timed collatz_steps is the handout's scalar loop; it has no memoization.",
            "An optimized untimed oracle checks the same checksum for every worker count.",
            "Range construction and result checksum reduction are outside the elapsed-time scope.",
            "Each repetition uses a fresh spawn Pool and retains the full prescribed input size.",
        ]
        if args.quick:
            notes.append("SMOKE CHECK ONLY: this is not a full-workload scaling measurement.")
        payloads.append(write_case(args.output_dir, case_id, samples, config, notes))
    return payloads


if __name__ == "__main__":
    mp.freeze_support()
    main()
