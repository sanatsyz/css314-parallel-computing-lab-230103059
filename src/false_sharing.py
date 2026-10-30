#!/usr/bin/env python3
"""Measure false sharing with real multiprocessing and native volatile updates.

The assignment fixes K *per worker*, making this a weak-scaling experiment.
The requested S=T1/Tp and Karp--Flatt values are supplied, but cannot be
interpreted as strong-scaling serial fractions for this growing workload.
Throughput speedup P*T1/Tp is reported separately.

The native loop avoids Python interpreter overhead concealing cache coherence.
RawArray provides shared memory without multiprocessing.Array's default global
lock. Each counter has exactly one writer. Process startup, C compilation, and
process shutdown are excluded from the reported interval; start-event wake-up
and the final privatized publication are included. No CPU affinity is forced.
"""

from __future__ import annotations

import argparse
import csv
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import platform
import queue
import random
import shlex
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKERS = (1, 2, 4, 8)
INT64_BYTES = ctypes.sizeof(ctypes.c_int64)


def _find_cache_line(value: Any) -> int | None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"cache_line_bytes", "cache_line_size", "cache_line_size_bytes"}:
                try:
                    size = int(item)
                    if size >= 16 and size <= 4096 and size & (size - 1) == 0:
                        return size
                except (ValueError, TypeError):
                    pass
        for item in value.values():
            found = _find_cache_line(item)
            if found is not None:
                return found
    if isinstance(value, list):
        for item in value:
            found = _find_cache_line(item)
            if found is not None:
                return found
    return None


def detect_cache_line(profile_path: Path | None = None) -> tuple[int, str]:
    """Use an explicit host profile, OS query, or a disclosed 64-byte fallback."""
    profiles = [profile_path] if profile_path else [ROOT / "results" / "host_profile.json"]
    for path in profiles:
        if path is not None and path.exists():
            found = _find_cache_line(json.loads(path.read_text()))
            if found is not None:
                return found, f"host profile: {path}"
    if sys.platform == "darwin":
        result = subprocess.run(
            ["/usr/sbin/sysctl", "-n", "hw.cachelinesize"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode == 0:
            found = _find_cache_line({"cache_line_bytes": result.stdout.strip()})
            if found is not None:
                return found, "sysctl hw.cachelinesize"
    linux_cache = Path("/sys/devices/system/cpu/cpu0/cache/index0/coherency_line_size")
    if linux_cache.exists():
        found = _find_cache_line({"cache_line_bytes": linux_cache.read_text().strip()})
        if found is not None:
            return found, str(linux_cache)
    return 64, "assumed 64 bytes; hardware query unavailable"


def variants_for_cache_line(cache_line_bytes: int) -> dict[str, int]:
    """Return byte strides, retaining the literal 64-byte assignment variant."""
    if cache_line_bytes < INT64_BYTES or cache_line_bytes % INT64_BYTES:
        raise ValueError("cache line must be a positive multiple of eight bytes")
    variants = {"unpadded": INT64_BYTES, "padded": max(64, cache_line_bytes), "privatized": INT64_BYTES}
    if cache_line_bytes != 64:
        variants["padded_64"] = 64
    return variants


def build_native_library(cache_dir: Path | None = None) -> tuple[Path, dict[str, Any]]:
    source = ROOT / "src" / "native" / "false_sharing.c"
    compiler = shlex.split(os.environ.get("CC", "cc"))
    if not compiler or shutil.which(compiler[0]) is None:
        raise RuntimeError("A C compiler is required; install Command Line Tools on macOS or cc on Linux.")
    flags = ["-O3", "-std=c11", "-fPIC", "-dynamiclib" if sys.platform == "darwin" else "-shared"]
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    identity = json.dumps([source_sha, compiler, flags, platform.system(), platform.machine()])
    digest = hashlib.sha256(identity.encode()).hexdigest()[:16]
    cache = cache_dir or ROOT / ".native-cache"
    cache.mkdir(parents=True, exist_ok=True)
    suffix = ".dylib" if sys.platform == "darwin" else ".so"
    library = cache / f"false_sharing_{digest}{suffix}"
    command = compiler + flags + [str(source), "-o", str(library)]
    if not library.exists():
        fd, name = tempfile.mkstemp(prefix="compile_", suffix=suffix, dir=cache)
        os.close(fd)
        temporary = Path(name)
        try:
            result = subprocess.run(
                compiler + flags + [str(source), "-o", str(temporary)],
                capture_output=True, text=True, check=False,
            )
            if result.returncode:
                raise RuntimeError(f"Native compilation failed:\n{result.stderr}")
            temporary.replace(library)
        finally:
            temporary.unlink(missing_ok=True)
    compiler_version = subprocess.run(compiler + ["--version"], capture_output=True, text=True, check=False)
    return library, {
        "source": str(source.relative_to(ROOT)),
        "source_sha256": source_sha,
        "compile_command": command,
        "compiler_version": compiler_version.stdout.splitlines()[0] if compiler_version.stdout else "unknown",
        "cache_path": str(library),
    }


def _load_native(library_path: str) -> ctypes.CDLL:
    library = ctypes.CDLL(library_path)
    library.increment_shared.argtypes = [ctypes.POINTER(ctypes.c_int64), ctypes.c_int64]
    library.increment_shared.restype = None
    library.increment_private.argtypes = [ctypes.c_int64]
    library.increment_private.restype = ctypes.c_int64
    return library


def _worker(
    memory: Any, offset_bytes: int, stride_bytes: int, worker_id: int,
    iterations: int, variant: str, library_path: str, ready: Any,
    start: Any, completed: Any, publication_lock: Any,
) -> None:
    try:
        native = _load_native(library_path)
        counter = ctypes.cast(
            ctypes.byref(memory, offset_bytes + worker_id * stride_bytes),
            ctypes.POINTER(ctypes.c_int64),
        )
        ready.put({"worker_id": worker_id, "status": "ready"})
        if not start.wait(timeout=120):
            raise TimeoutError("parent did not release start event")
        started_ns = time.perf_counter_ns()
        if variant == "privatized":
            local_count = native.increment_private(iterations)
            with publication_lock:
                counter[0] = local_count
        else:
            native.increment_shared(counter, iterations)
        finished_ns = time.perf_counter_ns()
        completed.put({
            "worker_id": worker_id,
            "started_ns": started_ns,
            "finished_ns": finished_ns,
            "loop_seconds": (finished_ns - started_ns) / 1e9,
            "count": int(counter[0]),
        })
    except BaseException as error:
        completed.put({"worker_id": worker_id, "error": repr(error)})
        raise


def run_trial(
    variant: str, workers: int, iterations: int, cache_line_bytes: int,
    library_path: Path, timeout: float = 120.0,
) -> dict[str, Any]:
    """Run one measured sample and verify every independently owned counter."""
    if workers < 1 or iterations < 1 or iterations >= 2**63:
        raise ValueError("workers and iterations must be positive; iterations must fit signed int64")
    variants = variants_for_cache_line(cache_line_bytes)
    if variant not in variants:
        raise ValueError(f"unknown variant: {variant}")
    stride_bytes = variants[variant]
    context = mp.get_context("spawn")
    alignment_bytes = max(64, cache_line_bytes)
    memory = context.RawArray(ctypes.c_int64, (workers * stride_bytes + alignment_bytes) // INT64_BYTES)
    base_address = ctypes.addressof(memory)
    offset_bytes = (-base_address) % alignment_bytes
    ready = context.Queue()
    completed = context.Queue()
    start = context.Event()
    publication_lock = context.Lock()
    processes = [context.Process(
        target=_worker,
        args=(memory, offset_bytes, stride_bytes, worker_id, iterations, variant,
              str(library_path), ready, start, completed, publication_lock),
    ) for worker_id in range(workers)]
    try:
        for process in processes:
            process.start()
        ready_workers = {ready.get(timeout=timeout)["worker_id"] for _ in range(workers)}
        if ready_workers != set(range(workers)):
            raise RuntimeError("not all workers became ready")
        released_ns = time.perf_counter_ns()
        start.set()
        records = [completed.get(timeout=timeout) for _ in range(workers)]
        errors = [record for record in records if "error" in record]
        if errors:
            raise RuntimeError(f"worker failed: {errors}")
        for process in processes:
            process.join(timeout=timeout)
            if process.exitcode != 0:
                raise RuntimeError(f"worker {process.pid} exited with {process.exitcode}")
        counts = [int(memory[(offset_bytes + worker_id * stride_bytes) // INT64_BYTES])
                  for worker_id in range(workers)]
        if counts != [iterations] * workers:
            raise RuntimeError(f"incorrect counter values: {counts}; expected {iterations} each")
        elapsed = (max(record["finished_ns"] for record in records) - released_ns) / 1e9
        return {
            "variant": variant, "workers": workers, "iterations_per_worker": iterations,
            "total_increments": workers * iterations, "stride_bytes": stride_bytes,
            "alignment_bytes": alignment_bytes,
            "counter_offset_within_cache_line": [
                (offset_bytes + base_address + worker_id * stride_bytes) % cache_line_bytes
                for worker_id in range(workers)
            ],
            "seconds": elapsed, "counts": counts, "counts_verified": True,
            "start_release_ns": released_ns,
            "worker_records": sorted(records, key=lambda record: record["worker_id"]),
        }
    except queue.Empty as error:
        raise RuntimeError("timed out waiting for a worker") from error
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
            if process.pid is not None:
                process.join(timeout=5)
        for channel in (ready, completed):
            channel.close()
            channel.join_thread()


def scaling_metrics(baseline_seconds: float, elapsed_seconds: float, workers: int) -> dict[str, float | None]:
    if baseline_seconds <= 0 or elapsed_seconds <= 0 or workers < 1:
        raise ValueError("timings and worker count must be positive")
    requested_speedup = baseline_seconds / elapsed_seconds
    return {
        "requested_speedup_t1_over_tp": requested_speedup,
        "karp_flatt_requested": None if workers == 1 else (
            (1.0 / requested_speedup - 1.0 / workers) / (1.0 - 1.0 / workers)
        ),
        "throughput_speedup": workers * requested_speedup,
        "weak_scaling_efficiency": requested_speedup,
    }


def aggregate_trials(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for sample in samples:
        groups.setdefault((sample["variant"], sample["workers"]), []).append(sample)
    baselines = {variant: statistics.median(sample["seconds"] for sample in runs)
                 for (variant, workers), runs in groups.items() if workers == 1}
    rows = []
    for (variant, workers), runs in groups.items():
        timings = [sample["seconds"] for sample in runs]
        median = statistics.median(timings)
        row = {
            "variant": variant, "workers": workers, "iterations_per_worker": runs[0]["iterations_per_worker"],
            "total_increments": runs[0]["total_increments"], "stride_bytes": runs[0]["stride_bytes"],
            "repeats": len(runs), "median_seconds": median,
            "min_seconds": min(timings), "max_seconds": max(timings),
            "mean_seconds": statistics.mean(timings),
            "stdev_seconds": statistics.stdev(timings) if len(timings) > 1 else 0.0,
            "increments_per_second": runs[0]["total_increments"] / median,
            **scaling_metrics(baselines[variant], median, workers),
            "all_counts_verified": all(sample["counts_verified"] for sample in runs),
        }
        rows.append(row)
    return sorted(rows, key=lambda row: (list(dict.fromkeys(sample["variant"] for sample in samples)).index(row["variant"]), row["workers"]))


def write_results(output_dir: Path, metadata: dict[str, Any], samples: list[dict[str, Any]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {"metadata": metadata, "samples": samples, "aggregates": aggregate_trials(samples)}
    destination = output_dir / "false_sharing_raw.json"
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n")
    temporary.replace(destination)
    rows = payload["aggregates"]
    with (output_dir / "false_sharing_karp_flatt.tsv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--iterations", type=int, default=5_000_000)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--workers", type=int, nargs="+", default=list(DEFAULT_WORKERS))
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results")
    parser.add_argument("--host-profile", type=Path)
    parser.add_argument("--cache-line-bytes", type=int)
    parser.add_argument("--seed", type=int, default=482)
    parser.add_argument("--quick", action="store_true", help="smoke test only: 20,000 increments, P=1,2, one repeat")
    args = parser.parse_args(argv)
    if args.quick:
        args.iterations, args.repeats, args.workers = 20_000, 1, [1, 2]
    if args.iterations < 1 or args.iterations >= 2**63 or args.repeats < 1:
        parser.error("iterations must be positive and fit int64; repeats must be positive")
    if not args.workers or any(workers < 1 for workers in args.workers) or 1 not in args.workers:
        parser.error("workers must be positive and include baseline P=1")
    args.workers = sorted(set(args.workers))
    cache_line_bytes, cache_line_source = detect_cache_line(args.host_profile)
    if args.cache_line_bytes is not None:
        cache_line_bytes, cache_line_source = args.cache_line_bytes, "CLI override"
    try:
        variants = variants_for_cache_line(cache_line_bytes)
    except ValueError as error:
        parser.error(str(error))
    library_path, native_metadata = build_native_library()
    metadata = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version, "platform": platform.platform(), "machine": platform.machine(),
        "logical_cpus": os.cpu_count(), "start_method": "spawn",
        "cache_line_bytes": cache_line_bytes, "cache_line_source": cache_line_source,
        "iterations_per_worker": args.iterations, "workers": args.workers, "repeats": args.repeats,
        "quick_smoke_test": args.quick, "schedule_seed": args.seed,
        "variants_byte_stride": variants, "native": native_metadata,
        "workload": "weak scaling: each worker performs K increments, total work P*K",
        "timing": "parent start-event release to latest worker finish; spawn, compilation, and process exit excluded; event wakeup and privatized final locked write included",
        "aggregation": "median over repeats; each variant uses its own P=1 median baseline",
        "requested_speedup_formula": "S_requested = T1 / Tp (unequal total work)",
        "karp_flatt_formula": "e_requested = (1 / S_requested - 1/P) / (1 - 1/P)",
        "karp_flatt_interpretation": "The assignment requests this formula despite fixed K per worker. These are NOT strong-scaling serial-fraction estimates: ideal weak scaling yields e_requested=1, not 0.",
        "throughput_speedup_formula": "S_throughput = P * T1 / Tp; weak_scaling_efficiency = T1 / Tp",
        "measurement_caveats": [
            "Native volatile C loops, not Python interpreted increments; every shared increment reads and writes memory.",
            "Counters are aligned; unpadded P<=8 fits within the first 64 bytes. padded uses at least one detected hardware cache line.",
            "padded_64 is additionally reported when the detected line differs from 64 bytes; 64-byte strides do not isolate a 128-byte line.",
            "RawArray is lock-free in the hot loop; privatized uses one lock only for each worker's final publication.",
            "OS scheduling, heterogeneous cores, power management, and unrelated load can affect measurements; no observed collapse is assumed or fabricated.",
            "Very short native loops may be dominated by event wakeup; inspect repeat spread and per-worker native loop times.",
        ],
    }
    samples: list[dict[str, Any]] = []
    rng = random.Random(args.seed)
    for repeat in range(args.repeats):
        schedule = [(variant, workers) for variant in variants for workers in args.workers]
        rng.shuffle(schedule)
        for variant, workers in schedule:
            sample = run_trial(variant, workers, args.iterations, cache_line_bytes, library_path)
            sample["repeat"] = repeat + 1
            sample["execution_order"] = len(samples) + 1
            samples.append(sample)
            print(f"repeat={repeat + 1} variant={variant:<11} P={workers:<2} seconds={sample['seconds']:.6f} counts=OK", flush=True)
        # Save complete repeats so an interrupted longer experiment retains data.
        write_results(args.output_dir, metadata, samples)
    print(f"Saved {len(samples)} verified samples to {args.output_dir}")
    print("Fixed K per worker is weak scaling. Requested Karp-Flatt values are not strong-scaling serial fractions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
