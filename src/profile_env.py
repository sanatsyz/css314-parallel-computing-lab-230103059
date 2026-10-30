"""Capture observed topology; unsupported telemetry is null, never invented."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

from salt import get_student_params


def sysctl(key):
    try:
        p = subprocess.run(["sysctl", "-n", key], capture_output=True, text=True)
        value = p.stdout.strip()
        return value if p.returncode == 0 and value else None
    except FileNotFoundError:
        return None


def integer(key):
    value = sysctl(key)
    return int(value) if value is not None else None


def profile():
    clock = time.get_clock_info("perf_counter")
    result = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "cpu_model": platform.processor(), "architecture": platform.machine(),
        "microarchitecture": None, "base_frequency_hz": None,
        "physical_cores": None, "logical_threads": os.cpu_count(),
        "cache_line_bytes": None, "caches": {}, "performance_levels": [],
        "os": platform.system(), "kernel_version": platform.release(),
        "python": {"implementation": platform.python_implementation(),
                   "version": platform.python_version(), "executable": sys.executable},
        "timer": {"name": "perf_counter_ns", "implementation": clock.implementation,
                  "resolution_seconds": clock.resolution, "monotonic": clock.monotonic},
        "peak_memory_bandwidth_bytes_per_second": None,
        "hardware_performance_counters": {"status": "not_collected",
            "reason": "No privileged hardware counter profiler was available; no cache hit rates inferred."},
        "notes": []}
    if platform.system() == "Darwin":
        result.update(cpu_model=sysctl("machdep.cpu.brand_string"),
                      physical_cores=integer("hw.physicalcpu"),
                      logical_threads=integer("hw.logicalcpu"),
                      cache_line_bytes=integer("hw.cachelinesize"),
                      base_frequency_hz=integer("hw.cpufrequency"))
        result["caches"] = {"l1_data_bytes": integer("hw.l1dcachesize"),
                            "l2_bytes": integer("hw.l2cachesize"),
                            "l3_bytes": integer("hw.l3cachesize")}
        for i in range(integer("hw.nperflevels") or 0):
            prefix = f"hw.perflevel{i}."
            result["performance_levels"].append({
                "name": sysctl(prefix + "name"),
                "physical_cores": integer(prefix + "physicalcpu"),
                "logical_threads": integer(prefix + "logicalcpu"),
                "l1_data_bytes": integer(prefix + "l1dcachesize"),
                "l2_bytes": integer(prefix + "l2cachesize"),
                "cores_per_l2": integer(prefix + "cpusperl2")})
        result["notes"].append("sysctl source. Cache values differ by performance/efficiency cluster; see performance_levels. Unknown base frequency, L3 and microarchitecture remain null; absence of a sysctl is not evidence of zero capacity.")
    elif platform.system() == "Linux":
        text = Path("/proc/cpuinfo").read_text()
        records = [dict(line.split(":", 1) for line in block.splitlines() if ":" in line)
                   for block in text.split("\n\n") if block.strip()]
        records = [{k.strip(): v.strip() for k, v in row.items()} for row in records]
        if records:
            result["cpu_model"] = records[0].get("model name", result["cpu_model"])
            identities = {(r.get("physical id"), r.get("core id")) for r in records}
            if all(a is not None and b is not None for a, b in identities):
                result["physical_cores"] = len(identities)
        cache_details = []
        for directory in Path("/sys/devices/system/cpu/cpu0/cache").glob("index*"):
            row = {name: (directory / name).read_text().strip()
                   for name in ["level", "type", "size", "coherency_line_size", "shared_cpu_list"]}
            cache_details.append(row)
        result["caches"]["sysfs_entries"] = cache_details
        if cache_details:
            result["cache_line_bytes"] = int(cache_details[0]["coherency_line_size"])
    result["smt_detected"] = (result["logical_threads"] > result["physical_cores"]
                              if result["physical_cores"] else None)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--student-id", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    args = parser.parse_args()
    params = get_student_params(args.student_id)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, data in [("host_profile.json", profile()), ("salted_params.json", params)]:
        (args.output_dir / name).write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps(params))


if __name__ == "__main__":
    main()
