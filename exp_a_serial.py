"""Experiment A: a fixed serial pause before independent process-pool work.

The primary runtime includes the pause and a new pool's startup, work and
teardown, exactly as in the practice handout. Use --quick for a smoke check;
only the default workload is suitable for the submitted measurement table.
"""

import argparse
import math
import multiprocessing as mp
from pathlib import Path
import time


WORKER_COUNTS = (1, 2, 4)


def heavy_math(n):
    """The scalar CPU workload specified by the handout."""
    return sum(math.sin(i) * math.cos(i) for i in range(1, n))


def _positive_int(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("{} must be a positive integer".format(name))


def run_trial(workers, total_chunks=16, chunk_size=2_000_000,
              serial_pause=0.40):
    """Time one trial, returning the actual worker results for verification."""
    _positive_int(workers, "workers")
    _positive_int(total_chunks, "total_chunks")
    _positive_int(chunk_size, "chunk_size")
    if not math.isfinite(serial_pause) or serial_pause < 0:
        raise ValueError("serial_pause must be finite and non-negative")
    context = mp.get_context("spawn")

    started = time.perf_counter()
    time.sleep(serial_pause)
    slept = time.perf_counter()
    with context.Pool(processes=workers) as pool:
        chunk_results = pool.map(heavy_math, [chunk_size] * total_chunks)
    finished = time.perf_counter()

    chunk_results = [float(value) for value in chunk_results]
    total_result = sum(chunk_results)
    if not all(math.isfinite(value) for value in chunk_results):
        raise ArithmeticError("Experiment A produced a non-finite chunk result")
    if not math.isfinite(total_result):
        raise ArithmeticError("Experiment A produced a non-finite total")
    return {
        "workers": workers,
        "runtime_seconds": finished - started,
        "chunk_results": chunk_results,
        "total_result": total_result,
        "phase_sleep_seconds": slept - started,
        "phase_pool_seconds": finished - slept,
    }


def run_experiment(workers, total_chunks=16, chunk_size=2_000_000,
                   serial_pause=0.40):
    """Return the handout-compatible end-to-end runtime in seconds."""
    return run_trial(workers, total_chunks, chunk_size,
                     serial_pause)["runtime_seconds"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, default=Path("practice_results"))
    parser.add_argument("--total-chunks", type=int, default=16)
    parser.add_argument("--chunk-size", type=int, default=2_000_000)
    parser.add_argument("--serial-pause", type=float, default=0.40)
    parser.add_argument("--quick", action="store_true",
                        help="use a small smoke workload and separate output directory")
    args = parser.parse_args(argv)
    for value, name in [(args.repeats, "repeats"),
                        (args.total_chunks, "total_chunks"),
                        (args.chunk_size, "chunk_size")]:
        if value < 1:
            parser.error("{} must be positive".format(name))
    if not math.isfinite(args.serial_pause) or args.serial_pause < 0:
        parser.error("serial-pause must be finite and non-negative")

    if args.quick:
        args.total_chunks = 4
        args.chunk_size = 2_000
        args.output_dir = args.output_dir / "smoke"

    # Calculate the independent serial reference once, outside every timer.
    reference = heavy_math(args.chunk_size)
    samples = []
    for repeat in range(args.repeats):
        offset = repeat % len(WORKER_COUNTS)
        order = WORKER_COUNTS[offset:] + WORKER_COUNTS[:offset]
        for workers in order:
            sample = run_trial(workers, args.total_chunks, args.chunk_size,
                               args.serial_pause)
            if not all(math.isclose(value, reference, rel_tol=1e-12,
                                    abs_tol=1e-12)
                       for value in sample["chunk_results"]):
                raise ArithmeticError("Worker result differs from the serial reference")
            sample["repeat"] = repeat
            sample["reference_chunk_result"] = reference
            sample["correctness_passed"] = True
            samples.append(sample)
            print("A repeat {} workers {}: {:.6f} s".format(
                repeat + 1, workers, sample["runtime_seconds"]), flush=True)

    from practice_support import write_experiment
    config = {
        "total_chunks": args.total_chunks,
        "chunk_size": args.chunk_size,
        "serial_pause_seconds": args.serial_pause,
        "start_method": "spawn",
        "repeats": args.repeats,
        "workers": list(WORKER_COUNTS),
        "quick": args.quick,
    }
    notes = [
        "Runtime includes the serial pause and fresh pool startup, map and teardown.",
        "One scalar chunk reference is calculated outside all trial timers.",
        "Worker-count order rotates between repeats to reduce order bias.",
        "The handout's suggested e(p) range is an expectation, not a pass criterion.",
    ]
    if args.quick:
        notes.append("SMOKE CHECK ONLY: this small workload is not a scaling result.")
    payload = write_experiment(args.output_dir, "A", samples, config, notes)
    print("Saved Experiment A to {}".format(args.output_dir), flush=True)
    return payload


if __name__ == "__main__":
    mp.freeze_support()
    main()
