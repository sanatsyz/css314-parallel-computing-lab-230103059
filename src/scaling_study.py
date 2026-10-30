#!/usr/bin/env python3
"""Measure strong/weak scaling of a synchronized, shared-memory 2-D stencil.

The five-point update is ``(center + north + south + west + east) * 0.2``.
Only the interior changes; all four boundaries remain zero. Workers own disjoint
row ranges of the destination grid. A barrier after *every* update makes the
entire new grid, including neighboring workers' halo rows, available before the
next step. No arrays are pickled between workers.

The reported kernel wall time includes start/finish barriers and every per-step
barrier. It excludes process creation, imports, one untimed warm-up update, and
initialization. End-to-end samples include those costs and shared-memory cleanup.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import multiprocessing as mp
from multiprocessing import shared_memory
from pathlib import Path
import platform
import queue
import statistics
import time
import traceback
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]


def _array_digest(array: np.ndarray) -> str:
    """Canonical exact bytes, separate from the assignment's rounded salted hash."""
    return hashlib.sha256(np.asarray(array, dtype="<f8", order="C").tobytes()).hexdigest()


def save_array_parts(
    array: np.ndarray, directory: Path, *, max_part_bytes: int = 16 * 1024 * 1024,
) -> Path:
    """Save every float64 value losslessly in small compressed row slabs.

    Raw payloads are at most 16 MiB by default, comfortably below GitHub's
    per-file limit even when floating-point data compresses poorly. A complete
    manifest records ordered rows and an exact, canonical uncompressed digest.
    """
    array = np.asarray(array, dtype=np.float64, order="C")
    if array.ndim != 2 or array.shape[0] < 1 or array.shape[1] < 1:
        raise ValueError("expected a nonempty two-dimensional array")
    row_bytes = array.shape[1] * array.itemsize
    if max_part_bytes < row_bytes:
        raise ValueError("max_part_bytes must hold at least one complete row")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    rows_per_part = max_part_bytes // row_bytes
    parts = []
    for index, start in enumerate(range(0, array.shape[0], rows_per_part)):
        stop = min(start + rows_per_part, array.shape[0])
        filename = f"part-{index:04d}.npz"
        values = array[start:stop]
        np.savez_compressed(directory / filename, values=values)
        parts.append({
            "path": filename, "row_start": start, "row_stop": stop,
            "uncompressed_value_bytes": values.nbytes,
            "sha256_float64_little_endian": _array_digest(values),
        })
    manifest = {
        "format": "lossless-float64-row-parts-v1",
        "shape": list(array.shape), "dtype": "float64",
        "max_uncompressed_part_bytes": max_part_bytes,
        "sha256_float64_little_endian": _array_digest(array),
        "digest_encoding": "C-order little-endian float64 exact bytes, without salt or rounding",
        "parts": parts,
    }
    path = directory / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    return path


def load_saved_array(path: Path | str) -> np.ndarray:
    """Reconstruct and validate a complete persisted stencil result exactly."""
    path = Path(path)
    if path.suffix == ".npy":
        return np.load(path, allow_pickle=False)
    if path.is_dir():
        path = path / "manifest.json"
    manifest = json.loads(path.read_text())
    if manifest.get("format") != "lossless-float64-row-parts-v1" or manifest.get("dtype") != "float64":
        raise ValueError("unsupported numerical output manifest")
    shape = manifest["shape"]
    if len(shape) != 2 or not all(isinstance(n, int) and n > 0 for n in shape):
        raise ValueError("invalid output shape")
    array = np.empty(shape, dtype=np.float64)
    next_row = 0
    for part in manifest["parts"]:
        start, stop = part["row_start"], part["row_stop"]
        if start != next_row or not start < stop <= shape[0]:
            raise ValueError("parts must cover all rows once in contiguous order")
        filename = part["path"]
        if Path(filename).name != filename:
            raise ValueError("part filenames must stay within the manifest directory")
        with np.load(path.parent / filename, allow_pickle=False) as archive:
            values = archive["values"]
            if values.dtype != np.float64 or values.shape != (stop - start, shape[1]):
                raise ValueError("output part has incorrect dtype or shape")
            if _array_digest(values) != part["sha256_float64_little_endian"]:
                raise ValueError("output part digest mismatch")
            array[start:stop] = values
        next_row = stop
    if next_row != shape[0] or _array_digest(array) != manifest["sha256_float64_little_endian"]:
        raise ValueError("incomplete or corrupted numerical output")
    return array


def init_grid(n: int, seed: int) -> np.ndarray:
    """Return a deterministic C-contiguous float64 grid with zero boundaries."""
    if n < 3:
        raise ValueError("a stencil grid needs at least 3 rows and columns")
    grid = np.random.default_rng(seed).random((n, n), dtype=np.float64)
    grid[[0, -1], :] = 0.0
    grid[:, [0, -1]] = 0.0
    return grid


def reference_stencil(array: np.ndarray, steps: int) -> np.ndarray:
    """Independent serial reference; never modifies the caller's array."""
    if steps < 0:
        raise ValueError("steps cannot be negative")
    current = np.asarray(array, dtype=np.float64).copy()
    if current.ndim != 2 or min(current.shape) < 3:
        raise ValueError("expected a two-dimensional grid at least 3 by 3")
    if np.any(current[[0, -1], :]) or np.any(current[:, [0, -1]]):
        raise ValueError("the fixed boundaries must be zero")
    for _ in range(steps):
        updated = np.zeros_like(current)
        updated[1:-1, 1:-1] = (
            current[1:-1, 1:-1]
            + current[:-2, 1:-1]
            + current[2:, 1:-1]
            + current[1:-1, :-2]
            + current[1:-1, 2:]
        ) * 0.2
        current = updated
    return current


def process_counts(physical_cores: int) -> list[int]:
    """Powers of two, also including a non-power-of-two physical-core limit."""
    if physical_cores < 1:
        raise ValueError("physical_cores must be positive")
    values = []
    p = 1
    while p <= physical_cores:
        values.append(p)
        p *= 2
    if values[-1] != physical_cores:
        values.append(physical_cores)
    return values


def _row_ranges(n: int, workers: int) -> list[tuple[int, int]]:
    if not 1 <= workers <= n - 2:
        raise ValueError("workers must be between 1 and the interior row count")
    rows, remainder = divmod(n - 2, workers)
    ranges = []
    start = 1
    for worker in range(workers):
        stop = start + rows + (worker < remainder)
        ranges.append((start, stop))
        start = stop
    return ranges


def _stencil_slice(src: np.ndarray, dst: np.ndarray, start: int, stop: int) -> None:
    """Five ufunc passes without large temporary arrays; 5 FLOPs per update."""
    out = dst[start:stop, 1:-1]
    np.add(src[start:stop, 1:-1], src[start - 1:stop - 1, 1:-1], out=out)
    np.add(out, src[start + 1:stop + 1, 1:-1], out=out)
    np.add(out, src[start:stop, :-2], out=out)
    np.add(out, src[start:stop, 2:], out=out)
    np.multiply(out, 0.2, out=out)


def _worker(
    names: tuple[str, str], n: int, start: int, stop: int, steps: int,
    step_barrier: Any, start_barrier: Any, finish_barrier: Any, messages: Any,
) -> None:
    buffers = []
    try:
        buffers = [shared_memory.SharedMemory(name=name) for name in names]
        grids = [np.ndarray((n, n), dtype=np.float64, buffer=b.buf) for b in buffers]
        # Populate NumPy's code path and touch this worker's destination pages.
        # The parent resets both grids after every worker reports readiness.
        _stencil_slice(grids[0], grids[1], start, stop)
        messages.put(("ready", start))
        start_barrier.wait()
        for step in range(steps):
            _stencil_slice(grids[step % 2], grids[(step + 1) % 2], start, stop)
            step_barrier.wait()
        finish_barrier.wait()
    except BaseException:
        messages.put(("error", traceback.format_exc()))
        # An exception must not strand other participants indefinitely.
        for barrier in (step_barrier, start_barrier, finish_barrier):
            try:
                barrier.abort()
            except Exception:
                pass
        raise
    finally:
        for buffer in buffers:
            buffer.close()


def benchmark_once(
    initial: np.ndarray, workers: int, steps: int, *, timeout: float = 180.0,
) -> tuple[dict[str, Any], np.ndarray]:
    """One real process-based run, returning raw timings and its final grid."""
    if steps < 1:
        raise ValueError("benchmark steps must be positive")
    initial = np.asarray(initial, dtype=np.float64, order="C")
    if initial.ndim != 2 or initial.shape[0] != initial.shape[1]:
        raise ValueError("expected a square matrix")
    if np.any(initial[[0, -1], :]) or np.any(initial[:, [0, -1]]):
        raise ValueError("the fixed boundaries must be zero")
    n = initial.shape[0]
    ranges = _row_ranges(n, workers)
    # Explicit spawn keeps the implementation consistent across macOS/Linux.
    context = mp.get_context("spawn")
    messages = context.Queue()
    step_barrier = context.Barrier(workers, timeout=timeout)
    start_barrier = context.Barrier(workers + 1, timeout=timeout)
    finish_barrier = context.Barrier(workers + 1, timeout=timeout)
    buffers: list[shared_memory.SharedMemory] = []
    processes: list[Any] = []
    sample: dict[str, Any] = {}
    result = None
    overall_start = time.perf_counter()
    try:
        buffers = [shared_memory.SharedMemory(create=True, size=initial.nbytes)
                   for _ in range(2)]
        grids = [np.ndarray(initial.shape, dtype=np.float64, buffer=b.buf) for b in buffers]
        grids[0][:] = initial
        grids[1].fill(0.0)
        for start, stop in ranges:
            process = context.Process(
                target=_worker,
                args=(tuple(b.name for b in buffers), n, start, stop, steps,
                      step_barrier, start_barrier, finish_barrier, messages),
            )
            process.start()
            processes.append(process)
        for _ in processes:
            try:
                kind, detail = messages.get(timeout=timeout)
            except queue.Empty as exc:
                raise RuntimeError("timed out waiting for stencil worker startup") from exc
            if kind != "ready":
                raise RuntimeError(f"stencil worker failed during startup:\n{detail}")
        # Undo the warm-up before releasing workers into the measured region.
        grids[0][:] = initial
        grids[1].fill(0.0)
        ready_at = time.perf_counter()
        start_barrier.wait()
        finish_barrier.wait()
        kernel_end = time.perf_counter()
        result = grids[steps % 2].copy()
        for process in processes:
            process.join(timeout)
            if process.is_alive() or process.exitcode != 0:
                raise RuntimeError(f"stencil worker exited incorrectly: {process.exitcode}")
        sample = {
            "kernel_seconds": kernel_end - ready_at,
            "startup_and_initialization_seconds": ready_at - overall_start,
            "workers": workers,
            "n": n,
            "steps": steps,
            "row_ranges_exclusive_stop": [list(r) for r in ranges],
            "warmup_updates_per_worker": 1,
        }
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join()
        for buffer in buffers:
            buffer.close()
            buffer.unlink()
        messages.close()
        messages.join_thread()
    sample["end_to_end_seconds"] = time.perf_counter() - overall_start
    assert result is not None
    return sample, result


def benchmark_case(
    n: int, workers: int, steps: int, seed: int, repeats: int,
) -> tuple[dict[str, Any], np.ndarray]:
    """Repeated runs and a serial correctness check, all recorded honestly."""
    if repeats < 1:
        raise ValueError("repeats must be positive")
    initial = init_grid(n, seed)
    expected = reference_stencil(initial, steps)
    samples = []
    final = None
    max_error = 0.0
    for repeat in range(repeats):
        sample, final = benchmark_once(initial, workers, steps)
        error = float(np.max(np.abs(final - expected)))
        if not np.allclose(final, expected, rtol=0.0, atol=1e-12):
            raise AssertionError(f"parallel stencil mismatch: P={workers}, error={error}")
        sample["repeat"] = repeat + 1
        sample["max_absolute_error"] = error
        max_error = max(max_error, error)
        samples.append(sample)
    assert final is not None
    case = {
        "n": n, "workers": workers, "steps": steps,
        "work_cell_updates": (n - 2) ** 2 * steps,
        "samples": samples,
        "median_kernel_seconds": statistics.median(s["kernel_seconds"] for s in samples),
        "minimum_kernel_seconds": min(s["kernel_seconds"] for s in samples),
        "maximum_kernel_seconds": max(s["kernel_seconds"] for s in samples),
        "median_end_to_end_seconds": statistics.median(s["end_to_end_seconds"] for s in samples),
        "max_absolute_error": max_error,
    }
    return case, final


def fit_amdahl(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Fit 1/S = 1/P + s(1 - 1/P), with T1 fixed to its measured median."""
    t1 = next(c["median_kernel_seconds"] for c in cases if c["workers"] == 1)
    numerator = denominator = 0.0
    for case in cases:
        p = case["workers"]
        x = 1.0 - 1.0 / p
        numerator += x * (case["median_kernel_seconds"] / t1 - 1.0 / p)
        denominator += x * x
    if denominator == 0:
        return {"identifiable": False, "reason": "at least one P > 1 is required"}
    unconstrained = numerator / denominator
    bounded = min(1.0, max(0.0, unconstrained))
    residuals = [
        c["median_kernel_seconds"] / t1
        - (unconstrained + (1.0 - unconstrained) / c["workers"])
        for c in cases
    ]
    return {
        "identifiable": True,
        "method": "least squares on inverse speedup with measured T1 fixed",
        "unconstrained_serial_fraction": unconstrained,
        "bounded_serial_fraction": bounded,
        "unconstrained_asymptotic_speedup": 1.0 / unconstrained if unconstrained > 0 else None,
        "bounded_asymptotic_speedup": 1.0 / bounded if bounded > 0 else None,
        "bounded_zero_ceiling_interpretation": "unbounded in the idealized model" if bounded == 0 else None,
        "inverse_speedup_residual_sum_of_squares": sum(r * r for r in residuals),
        "physical_range_violation": not 0.0 <= unconstrained <= 1.0,
        "caveat": (
            "An effective fit includes communication, barriers, heterogeneous cores and noise. "
            "Values outside [0,1] indicate model mismatch; the bounded fit is a constrained summary."
        ),
    }


def _metrics(strong: list[dict[str, Any]], weak: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for mode, cases in (("strong", strong), ("weak", weak)):
        base = next(c for c in cases if c["workers"] == 1)
        for case in cases:
            p = case["workers"]
            time_ratio = base["median_kernel_seconds"] / case["median_kernel_seconds"]
            work_ratio = case["work_cell_updates"] / base["work_cell_updates"]
            throughput_speedup = work_ratio * time_ratio
            records.append({
                "mode": mode, "workers": p, "n": case["n"], "steps": case["steps"],
                "work_cell_updates": case["work_cell_updates"],
                "median_kernel_seconds": case["median_kernel_seconds"],
                "minimum_kernel_seconds": case["minimum_kernel_seconds"],
                "maximum_kernel_seconds": case["maximum_kernel_seconds"],
                "median_end_to_end_seconds": case["median_end_to_end_seconds"],
                "time_speedup_T1_over_Tp": time_ratio,
                "conventional_throughput_speedup": throughput_speedup,
                "parallel_efficiency_percent": throughput_speedup / p * 100.0,
                # This is the formula printed in Task 3.2, recorded literally.
                "assignment_scaled_speedup": p / work_ratio * time_ratio if mode == "weak" else "",
                "updates_per_second": case["work_cell_updates"] / case["median_kernel_seconds"],
                "max_absolute_error": case["max_absolute_error"],
            })
    return records


def _roofline_summary(
    profile: dict[str, Any], cases: list[dict[str, Any]], records: list[dict[str, Any]],
    amdahl: dict[str, Any], salted_n: int, mode: str,
) -> dict[str, Any]:
    bandwidth = profile.get("peak_memory_bandwidth_bytes_per_second")
    bandwidth_source = profile.get("peak_memory_bandwidth_source")
    bandwidth_scope = "host profile value; consult its source for peak/sustained scope"
    bandwidth_source_accessed = None
    if bandwidth is None and profile.get("cpu_model") == "Apple M4":
        bandwidth = 120_000_000_000
        bandwidth_source = "https://support.apple.com/en-au/122209"
        bandwidth_source_accessed = "2026-10-30"
        bandwidth_scope = (
            "Apple's documented 120 GB/s unified-memory bandwidth upper bound; "
            "shared by the chip, not measured sustained CPU bandwidth for this kernel"
        )
    compute_peak = profile.get("peak_float64_flops_per_second")
    optimistic_ai = 5.0 / 16.0
    classification = "undetermined_without_documented_bandwidth_and_float64_compute_peaks"
    ridge = None
    if isinstance(bandwidth, (int, float)) and bandwidth > 0 and isinstance(compute_peak, (int, float)) and compute_peak > 0:
        ridge = compute_peak / bandwidth
        classification = "memory_bandwidth_bound_in_ideal_streaming_roofline" if optimistic_ai < ridge else "compute_bound_in_ideal_streaming_roofline"
    operating_points = []
    for case, record in zip(cases, records):
        updates = case["work_cell_updates"]
        seconds = case["median_kernel_seconds"]
        operating_points.append({
            "mode": record["mode"], "workers": case["workers"], "n": case["n"],
            "two_grid_working_set_bytes": 2 * case["n"] ** 2 * 8,
            "estimated_flops": updates * 5,
            "measured_gflops_per_second": updates * 5 / seconds / 1e9,
            "minimum_streaming_bytes_per_second_model": updates * 16 / seconds,
            "logical_ufunc_array_bytes_per_second_model": updates * 112 / seconds,
        })
    strong_records = [r for r in records if r["mode"] == "strong"]
    weak_records = [r for r in records if r["mode"] == "weak"]
    return {
        "benchmark_mode": mode,
        "salted_n": salted_n,
        "stencil": "u_next[i,j] = (u[i,j] + u[i-1,j] + u[i+1,j] + u[i,j-1] + u[i,j+1]) * 0.2",
        "boundary_condition": "all four boundaries fixed at zero; interior updated synchronously",
        "flops_per_interior_update": 5,
        "flops_definition": "four additions and one multiplication; no fused operations",
        "arithmetic_intensity_models": {
            "optimistic_streaming": {"dram_bytes_per_update": 16, "flops_per_byte": optimistic_ai,
                "assumption": "each source element fetched once, one destination write, no write allocation or halo overhead"},
            "streaming_with_write_allocation": {"dram_bytes_per_update": 24, "flops_per_byte": 5 / 24,
                "assumption": "one 8-byte read, one 8-byte write allocation, one 8-byte writeback"},
            "logical_ufunc_array_traffic": {"array_bytes_per_update": 112, "flops_per_byte": 5 / 112,
                "assumption": "four adds each read two values and write one; multiply reads and writes one; cache may serve these accesses"},
        },
        "traffic_caveat": "These are explicit estimates, not hardware-counter measurements of DRAM traffic. Cache reuse, write policy and halo rows change actual traffic.",
        "host_caches": profile.get("caches", {}),
        "cache_line_bytes": profile.get("cache_line_bytes"),
        "performance_levels": profile.get("performance_levels", []),
        "cache_interpretation": "Compare each worker's two row slabs plus halo rows with its cache group. Aggregate private/shared cache sizes cannot be treated as one fully accessible cache. Small slabs can be cache resident; full-grid bytes alone do not establish DRAM traffic.",
        "peak_memory_bandwidth_bytes_per_second": bandwidth,
        "peak_memory_bandwidth_source": bandwidth_source,
        "peak_memory_bandwidth_source_accessed": bandwidth_source_accessed,
        "peak_memory_bandwidth_scope": bandwidth_scope,
        "theoretical_bandwidth_ceiling_gflops_per_second": {
            "optimistic_16_bytes_per_update": bandwidth * (5 / 16) / 1e9
                if isinstance(bandwidth, (int, float)) and bandwidth > 0 else None,
            "write_allocate_24_bytes_per_update": bandwidth * (5 / 24) / 1e9
                if isinstance(bandwidth, (int, float)) and bandwidth > 0 else None,
            "caveat": "AI times manufacturer bandwidth is an upper bound, not a measured sustained rate; cache-resident execution follows a different bandwidth ceiling.",
        },
        "peak_float64_flops_per_second": compute_peak,
        "ridge_point_flops_per_byte": ridge,
        "limiting_regime": classification,
        "conclusion": "The stencil has low arithmetic intensity and is sensitive to memory traffic. Barrier synchronization, NumPy pass overhead, process scheduling and mixed core types can also limit measured scaling. A definitive roofline classification requires documented compute/bandwidth peaks and evidence of the cache/DRAM regime.",
        "operating_points": operating_points,
        "amdahl_fit": amdahl,
        "scaling_comparison": {
            "largest_strong_efficiency_percent": strong_records[-1]["parallel_efficiency_percent"],
            "largest_weak_efficiency_percent": weak_records[-1]["parallel_efficiency_percent"],
            "largest_weak_conventional_throughput_speedup": weak_records[-1]["conventional_throughput_speedup"],
            "largest_weak_assignment_scaled_speedup": weak_records[-1]["assignment_scaled_speedup"],
            "interpretation": "Compare strong and weak efficiencies empirically. Weak throughput may improve when larger per-process work amortizes barriers; no monotonic improvement is assumed.",
        },
        "weak_scaling_formula_note": "Task 3.2 prints P*Work(1)*T1/(Work(P)*Tp). This approaches T1/Tp when Work(P) is P*Work(1). It is recorded literally as assignment_scaled_speedup. Conventional throughput speedup is Work(P)/Work(1)*T1/Tp, with efficiency equal to throughput speedup/P.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results")
    parser.add_argument("--params", type=Path, default=ROOT / "results" / "salted_params.json")
    parser.add_argument("--profile", type=Path, default=ROOT / "results" / "host_profile.json")
    parser.add_argument("--quick", action="store_true", help="small smoke run; outputs explicitly marked smoke")
    args = parser.parse_args(argv)
    if args.steps < 1 or args.repeats < 1:
        parser.error("steps and repeats must be positive")
    params = json.loads(args.params.read_text())
    profile = json.loads(args.profile.read_text())
    created_utc = datetime.now(timezone.utc).isoformat()
    salted_n = int(params["N"])
    n = min(salted_n, 64) if args.quick else salted_n
    steps = min(args.steps, 6) if args.quick else args.steps
    repeats = 1 if args.quick else args.repeats
    cores = int(profile["physical_cores"])
    if args.quick:
        cores = min(cores, 2)
    counts = process_counts(cores)
    output_dir = args.output_dir
    if args.quick and output_dir == ROOT / "results":
        output_dir = output_dir / "smoke_scaling"
    arrays_dir = output_dir / "arrays"
    arrays_dir.mkdir(parents=True, exist_ok=True)
    strong = []
    weak = []
    for mode, collection in (("strong", strong), ("weak", weak)):
        for p in counts:
            size = n if mode == "strong" else math.ceil(n * math.sqrt(p))
            print(f"{mode}: P={p}, N={size}, steps={steps}, repeats={repeats}", flush=True)
            case, final = benchmark_case(size, p, steps, int(params["seed"]), repeats)
            case["array_path"] = f"arrays/scaling_{mode}_p{p}/manifest.json"
            save_array_parts(final, output_dir / "arrays" / f"scaling_{mode}_p{p}")
            collection.append(case)
            print(f"  median kernel {case['median_kernel_seconds']:.6f}s; max error {case['max_absolute_error']:.3g}", flush=True)
    records = _metrics(strong, weak)
    amdahl = fit_amdahl(strong)
    raw = {
        "schema_version": 1,
        "created_utc": created_utc,
        "environment": {"numpy_version": np.__version__,
                        "python_version": platform.python_version(),
                        "platform": platform.platform()},
        "benchmark_mode": "smoke" if args.quick else "full",
        "student_id": params["student_id"], "seed": int(params["seed"]),
        "salted_n": salted_n, "base_n": n, "steps": steps, "repeats": repeats,
        "process_counts": counts,
        "multiprocessing_start_method": "spawn",
        "timing_scope": "kernel wall time includes start/finish and per-step barriers; excludes process startup, initialization and one warm-up update per worker",
        "end_to_end_scope": "shared-memory allocation, initialization, spawn/import, warmup, kernel, output copy, joining and cleanup; excludes independent serial validation and saving arrays",
        "work_definition": "(N-2)^2 * steps interior cell updates",
        "strong": strong, "weak": weak, "amdahl_fit": amdahl,
    }
    (output_dir / "scaling_raw.json").write_text(json.dumps(raw, indent=2, allow_nan=False) + "\n")
    with (output_dir / "scaling_metrics.tsv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(records[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(records)
    roofline = _roofline_summary(profile, strong + weak, records, amdahl, salted_n, raw["benchmark_mode"])
    (output_dir / "roofline_summary.json").write_text(json.dumps(roofline, indent=2, allow_nan=False) + "\n")
    print(f"Saved scaling samples, metrics, arrays and roofline analysis to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
