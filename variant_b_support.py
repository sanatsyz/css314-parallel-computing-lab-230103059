"""Shared standard-library utilities for the CSS314 Variant B practice."""

import argparse
import csv
import json
import multiprocessing as mp
import os
from pathlib import Path

from practice_support import capture_host, summarize_samples, timestamp_utc


ROOT = Path(__file__).resolve().parent
DEFAULT_DIR = ROOT / "variant_b_results"
WORKERS = (1, 2, 4, 8)
STUDENT_ID = "230103059"
CASES = ("a_micro", "a_coarse", "b_queue", "c_buffered")


def partition_work(total, workers):
    """Keep total work fixed and assign every item, including remainders."""
    if type(total) is not int or total < 0:
        raise ValueError("total must be a nonnegative integer")
    if type(workers) is not int or workers < 1:
        raise ValueError("workers must be a positive integer")
    quotient, remainder = divmod(total, workers)
    return [quotient + int(index < remainder) for index in range(workers)]


def pattern_sum(count):
    """Exact sum of a worker's sequence 0,1,...,6,0,1,... of given length."""
    if type(count) is not int or count < 0:
        raise ValueError("count must be a nonnegative integer")
    groups, tail = divmod(count, 7)
    return groups * 21 + tail * (tail - 1) // 2


def write_case(output_dir, case_id, samples, config, notes):
    if case_id not in CASES:
        raise ValueError("unknown Variant B case")
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    rows = summarize_samples(samples)
    payload = {"schema_version": 1, "case_id": case_id,
               "created_at_utc": timestamp_utc(), "config": config,
               "samples": samples, "summary": rows, "notes": notes}
    (directory / (case_id + ".json")).write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    with (directory / (case_id + ".tsv")).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return payload


def setup_workspace(output_dir=DEFAULT_DIR):
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    host = capture_host()
    host["os_cpu_count"] = os.cpu_count()
    host["multiprocessing_cpu_count"] = mp.cpu_count()
    host["available_cpu_affinity"] = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None
    host["affinity_note"] = "No worker affinity applied; macOS has no os.sched_getaffinity API."
    if host["available_cpu_affinity"] is not None:
        host["affinity_note"] = "Available process CPU mask recorded; workers are not pinned."
    config = {
        "course": "CSS314", "student_id": STUDENT_ID,
        "branch": "variant-b-" + STUDENT_ID,
        "handout": "CS482 Practice Lab Handout (Variant B).pdf",
        "workers": list(WORKERS), "repeats": 3, "start_method": "spawn",
        "aggregation": "median elapsed seconds of three full runs per worker count",
        "experiments_run_sequentially": True,
        "experiment_a": {"total_items": 1_000_000, "chunk_sizes": [1, 10_000]},
        "experiment_b": {"total_items": 400_000},
        "experiment_c": {"total_items": 10_000_000, "batch_size": 10_000},
        "timing_policy": "Fresh pools/processes; startup, IPC and worker shutdown included. A checksum reduction and queue cleanup occur after timing.",
        "instructor_signoff": "pending",
    }
    (directory / "host_profile.json").write_text(json.dumps(host, indent=2) + "\n", encoding="utf-8")
    (directory / "configuration.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print("CPU: {}; OS count: {}; multiprocessing count: {}; branch: {}".format(
        host["cpu_model"], host["os_cpu_count"], host["multiprocessing_cpu_count"], config["branch"]))
    return host, config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args()
    setup_workspace(args.output_dir)


if __name__ == "__main__":
    main()
