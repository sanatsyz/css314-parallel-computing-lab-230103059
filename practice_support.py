"""Shared standard-library helpers for the CSS314 Karp-Flatt practice lab."""

import csv
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parent
WORKERS = (1, 2, 4)
STUDENT_ID = "230103059"


def timestamp_utc():
    return datetime.now(timezone.utc).isoformat()


def partition_work(total, workers):
    """Assign all work exactly once, including any division remainder."""
    if not isinstance(total, int) or total < 0 or not isinstance(workers, int) or workers < 1:
        raise ValueError("total must be nonnegative and workers must be positive integers")
    quotient, remainder = divmod(total, workers)
    return [quotient + (worker < remainder) for worker in range(workers)]


def summarize_samples(samples):
    grouped = {}
    for sample in samples:
        workers, elapsed = sample["workers"], sample["runtime_seconds"]
        if workers < 1 or not math.isfinite(elapsed) or elapsed <= 0:
            raise ValueError("worker counts and finite elapsed times must be positive")
        grouped.setdefault(workers, []).append(elapsed)
    if 1 not in grouped:
        raise ValueError("the one-worker baseline is required")
    baseline = statistics.median(grouped[1])
    rows = []
    for workers in sorted(grouped):
        values = grouped[workers]
        median = statistics.median(values)
        speedup = baseline / median
        rows.append({
            "workers": workers, "repeats": len(values),
            "median_seconds": median, "minimum_seconds": min(values),
            "maximum_seconds": max(values), "speedup": speedup,
            "efficiency_percent": 100.0 * speedup / workers,
            "karp_flatt": None if workers == 1 else (workers * median / baseline - 1.0) / (workers - 1.0),
        })
    return rows


def write_experiment(output_dir, experiment, samples, config, notes):
    if experiment not in ("A", "B", "C"):
        raise ValueError("experiment must be A, B or C")
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    rows = summarize_samples(samples)
    payload = {"schema_version": 1, "experiment": experiment,
               "created_at_utc": timestamp_utc(), "config": config,
               "samples": samples, "summary": rows, "notes": notes}
    stem = "experiment_" + experiment.lower()
    (directory / (stem + ".json")).write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")
    with (directory / (stem + ".tsv")).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return payload


def _sysctl(key, numeric=False):
    if platform.system() != "Darwin":
        return None
    process = subprocess.run(["sysctl", "-n", key], capture_output=True, text=True)
    value = process.stdout.strip()
    if process.returncode or not value:
        return None
    return int(value) if numeric else value


def capture_host():
    """Record available topology without substituting assumed hardware values."""
    clock = time.get_clock_info("perf_counter")
    profile = {
        "recorded_at_utc": timestamp_utc(), "cpu_model": platform.processor(),
        "architecture": platform.machine(), "os": platform.system(),
        "kernel_version": platform.release(), "physical_cores": None,
        "logical_threads": os.cpu_count(), "cache_line_bytes": None,
        "python": {"version": platform.python_version(),
                   "implementation": platform.python_implementation()},
        "timer": {"name": "perf_counter", "implementation": clock.implementation,
                  "resolution_seconds": clock.resolution, "monotonic": clock.monotonic},
        "multiprocessing_start_method": "spawn", "performance_levels": [],
        "cpu_affinity": "not pinned; the operating system schedules workers",
        "hardware_performance_counters": "not collected",
    }
    if platform.system() == "Darwin":
        profile.update(cpu_model=_sysctl("machdep.cpu.brand_string"),
                       physical_cores=_sysctl("hw.physicalcpu", True),
                       logical_threads=_sysctl("hw.logicalcpu", True),
                       cache_line_bytes=_sysctl("hw.cachelinesize", True))
        for index in range(_sysctl("hw.nperflevels", True) or 0):
            prefix = "hw.perflevel{}.".format(index)
            profile["performance_levels"].append({
                "name": _sysctl(prefix + "name"),
                "physical_cores": _sysctl(prefix + "physicalcpu", True),
                "l1_data_bytes": _sysctl(prefix + "l1dcachesize", True),
                "l2_bytes": _sysctl(prefix + "l2cachesize", True)})
    elif platform.system() == "Linux":
        cpuinfo = Path("/proc/cpuinfo")
        if cpuinfo.exists():
            records = []
            for block in cpuinfo.read_text().strip().split("\n\n"):
                records.append(dict((key.strip(), value.strip()) for key, value in
                                    (line.split(":", 1) for line in block.splitlines() if ":" in line)))
            if records:
                profile["cpu_model"] = records[0].get("model name", profile["cpu_model"])
                ids = {(row.get("physical id"), row.get("core id")) for row in records}
                if all(a is not None and b is not None for a, b in ids):
                    profile["physical_cores"] = len(ids)
        line_file = Path("/sys/devices/system/cpu/cpu0/cache/index0/coherency_line_size")
        if line_file.exists():
            profile["cache_line_bytes"] = int(line_file.read_text())
    return profile


def setup_workspace(output_dir=ROOT / "practice_results"):
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    host = capture_host()
    if host["logical_threads"] is None or host["logical_threads"] < max(WORKERS):
        raise RuntimeError("the specified experiment requires at least four logical CPUs")
    config = {
        "student_id": STUDENT_ID, "branch": "practice-" + STUDENT_ID,
        "handout": "Practice Lab Handout.pdf", "workers": list(WORKERS),
        "repeats": 3, "aggregation": "median wall-clock seconds across three full runs",
        "start_method": "spawn", "experiments_run_sequentially": True,
        "experiment_a": {"total_chunks": 16, "chunk_size": 2_000_000, "serial_pause_seconds": 0.40},
        "experiment_b": {"total_increments": 2_000_000},
        "experiment_c": {"total_increments": 20_000_000},
        "timing_policy": "fresh processes/pools; startup and shutdown included as specified in the handout",
        "instructor_sign_off": "pending; requires an instructor, not an automated check",
    }
    (directory / "host_profile.json").write_text(json.dumps(host, indent=2) + "\n")
    (directory / "configuration.json").write_text(json.dumps(config, indent=2) + "\n")
    print("CPU: {}; logical execution cores: {}; branch: {}".format(
        host["cpu_model"], host["logical_threads"], config["branch"]))


if __name__ == "__main__":
    setup_workspace()
