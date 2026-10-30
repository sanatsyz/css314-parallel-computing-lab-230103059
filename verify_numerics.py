#!/usr/bin/env python3
"""Independent local numerical checks, not an instructor verification signature.

The instructor-provided script is preserved separately as verify_outputs.py.
These additional checks independently recompute numerical outputs and reported
metrics, and emit an explicitly unsigned JSON self-check receipt. Its hashes
detect later changes when compared with the receipt; they do not authenticate
the author, timing, or origin of measurements.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import sys
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from scaling_study import init_grid, load_saved_array, reference_stencil  # noqa: E402


class VerificationError(ValueError):
    """A persisted dataset does not satisfy its declared experiment."""


def require(condition: bool, description: str) -> None:
    if not condition:
        raise VerificationError(description)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rounded_salted_digest(array: np.ndarray, student_id: str) -> str:
    """Salt with student ID and shape; hash rounded C-order little-endian f64."""
    values = np.asarray(array, dtype=np.float64)
    require(np.all(np.isfinite(values)), "nonfinite numerical output")
    header = {"scheme": "local-rounded-array-v1", "student_id": student_id,
              "shape": list(values.shape), "decimals": 6, "dtype": "<f8", "order": "C"}
    canonical = np.asarray(np.round(values, 6), dtype="<f8", order="C")
    canonical[canonical == 0] = 0.0  # Canonicalize the IEEE negative-zero encoding.
    digest = hashlib.sha256(json.dumps(header, sort_keys=True, separators=(",", ":")).encode() + b"\0")
    digest.update(canonical.tobytes(order="C"))
    return digest.hexdigest()


def check_close(actual: Any, expected: Any, description: str) -> None:
    if isinstance(expected, bool):
        require(actual is expected or actual == str(expected), description)
    elif expected is None:
        require(actual is None or actual == "", description)
    elif isinstance(expected, (int, float)):
        try:
            value = float(actual)
        except (TypeError, ValueError) as error:
            raise VerificationError(description) from error
        require(math.isfinite(value) and math.isclose(value, expected, rel_tol=1e-12, abs_tol=1e-12), description)
    else:
        require(actual == expected, description)


def check_fields(actual: dict, expected: dict, label: str) -> None:
    for field, value in expected.items():
        require(field in actual, f"{label}: missing {field}")
        check_close(actual[field], value, f"{label}: inconsistent {field}")


def positive_samples(values: list, count: int, label: str) -> None:
    require(len(values) == count, f"{label}: expected {count} samples")
    require(all(isinstance(x, (int, float)) and math.isfinite(x) and x > 0 for x in values),
            f"{label}: timings must be finite and positive")


def tsv_by(path: Path, columns: tuple[str, ...]) -> dict[tuple, dict]:
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    indexed = {tuple(row[field] for field in columns): row for row in rows}
    require(len(rows) == len(indexed), f"{path.name}: duplicate rows")
    return indexed


def check_native(metadata: dict, relative_source: str, root: Path) -> None:
    require(metadata["source_sha256"] == sha256_file(root / relative_source),
            f"native source changed since measurement: {relative_source}")


def verify_m0(directory: Path, student_id: str = "30103059") -> tuple[dict, dict, dict]:
    require(len(student_id) == 8 and student_id.isascii() and student_id.isdigit(), "invalid student ID")
    h = int(hashlib.sha256(student_id.encode()).hexdigest()[:8], 16)
    expected = {"student_id": student_id, "N": 1024 + h % 9 * 64,
                "buffer_elements": 16_777_216, "seed": h % 100_007}
    params = read_json(directory / "salted_params.json")
    require(params == expected, "M0: salted parameters differ from the exact handout algorithm")
    profile = read_json(directory / "host_profile.json")
    require(isinstance(profile["physical_cores"], int) and profile["physical_cores"] > 0, "M0: physical core count missing")
    require(isinstance(profile["logical_threads"], int) and profile["logical_threads"] >= profile["physical_cores"],
            "M0: inconsistent logical/physical topology")
    line = profile["cache_line_bytes"]
    require(isinstance(line, int) and line >= 8 and line & (line - 1) == 0, "M0: invalid cache line size")
    require(bool(profile["cpu_model"]) and bool(profile["architecture"]) and bool(profile["os"]), "M0: incomplete host identity")
    require(profile["timer"]["monotonic"] is True and profile["timer"]["resolution_seconds"] > 0, "M0: invalid timer")
    return params, profile, {"milestone": "M0", "status": "pass", "student_id": student_id,
        "salted_parameters": expected, "physical_cores": profile["physical_cores"], "cache_line_bytes": line,
        "scope": "recorded profile structural consistency; no claim of hardware attestation"}


def verify_m1(directory: Path, params: dict, root: Path = ROOT) -> dict:
    raw = read_json(directory / "stride_raw.json")
    require(raw["buffer_elements"] == params["buffer_elements"] and raw["dtype"] == "float64", "M1: quick or incorrect stride dataset")
    require(raw["buffer_bytes"] == params["buffer_elements"] * 8, "M1: incorrect buffer bytes")
    require(raw["warmups"] == 5 and raw["repeats"] == 5, "M1: five warmups and five runs required")
    check_native(raw["native"], "src/native/locality.c", root)
    table = tsv_by(directory / "stride_results.tsv", ("stride_elements",))
    strides = [1, 2, 4, 8, 16, 32, 64, 128]
    require([run["stride_elements"] for run in raw["runs"]] == strides, "M1: incorrect stride schedule")
    require(set(table) == {(str(stride),) for stride in strides}, "M1: incorrect stride TSV rows")
    for run in raw["runs"]:
        stride = run["stride_elements"]
        positive_samples(run["warmup_time_ns"], 5, f"stride {stride} warmup")
        positive_samples(run["time_ns"], 5, f"stride {stride}")
        touched = (params["buffer_elements"] + stride - 1) // stride
        require(run["verified_sum"] == touched, f"M1: stride {stride} reduction incorrect")
        median = statistics.median(run["time_ns"])
        check_fields(table[(str(stride),)], {"stride_bytes": stride * 8, "elements_touched": touched,
            "median_time_ns": median, "ns_per_element": median / touched, "sum": touched,
            "stride": stride, "latency_ns": median / touched}, f"stride {stride}")

    dense = read_json(directory / "loop_interchange.json")
    n, m = params["N"], params["N"] // 2
    require(dense["N"] == n and dense["M"] == m and dense["seed"] == params["seed"], "M1: quick or incorrectly salted dense dataset")
    require(dense["repeats"] >= 3 and dense["warmups_per_algorithm"] >= 1, "M1: insufficient dense repetitions")
    check_native(dense["native"], "src/native/locality.c", root)
    rng = np.random.default_rng(params["seed"])
    a = np.ascontiguousarray(rng.random((n, n))[:m, :m])
    b = np.ascontiguousarray(rng.random((n, n))[:m, :m])
    arrays_dir = directory / "arrays"
    for name, expected in (("dense_a", a), ("dense_b", b)):
        stored = np.load(arrays_dir / f"{name}.npy", allow_pickle=False)
        require(stored.dtype == np.float64 and stored.shape == (m, m), f"M1: {name} shape/dtype")
        require(np.array_equal(stored, expected), f"M1: {name} does not match fresh seeded input")
    reference = a @ b
    reference_digest = rounded_salted_digest(reference, params["student_id"])
    hashes, errors, outputs = {}, {}, {}
    for order in ("ijk", "ikj"):
        positive_samples(dense["time_ns"][order], dense["repeats"], f"dense {order}")
        check_close(dense["median_time_ns"][order], statistics.median(dense["time_ns"][order]), f"M1: dense {order} median")
        actual = np.load(arrays_dir / f"dense_{order}.npy", allow_pickle=False)
        require(actual.dtype == np.float64 and actual.shape == (m, m), f"M1: dense {order} shape/dtype")
        require(np.all(np.isfinite(actual)) and np.allclose(actual, reference, rtol=0, atol=1e-12), f"M1: dense {order} oracle mismatch")
        errors[order] = float(np.max(np.abs(actual - reference)))
        hashes[order] = rounded_salted_digest(actual, params["student_id"])
        require(hashes[order] == reference_digest, f"M1: dense {order} six-decimal digest mismatch")
        check_close(dense["max_abs_error_vs_numpy"][order], errors[order], f"M1: dense {order} recorded error")
        outputs[order] = actual
    difference = float(np.max(np.abs(outputs["ijk"] - outputs["ikj"])))
    require(difference <= 1e-12, "M1: loop orders disagree")
    check_close(dense["max_abs_difference"], difference, "M1: recorded loop difference")
    check_close(dense["speedup"], dense["median_time_ns"]["ijk"] / dense["median_time_ns"]["ikj"], "M1: dense speedup")
    check_fields(dense, {"naive_time_s": statistics.median(dense["time_ns"]["ijk"]) / 1e9,
                         "interchanged_time_s": statistics.median(dense["time_ns"]["ikj"]) / 1e9},
                 "M1: instructor timing aliases")
    return {"milestone": "M1", "status": "pass", "stride_cases": 8, "warmups_per_stride": 5,
            "timed_runs_per_stride": 5, "dense_shape": [m, m], "max_absolute_errors": errors,
            "salted_rounded_sha256": hashes, "numpy_oracle_salted_rounded_sha256": reference_digest}


def check_teacher_metric_aliases(row: dict, groups: dict, variants: dict, p: int, label: str) -> None:
    """Recompute per-P compatibility columns directly from raw sample times."""
    padded_variant = "padded_64" if "padded_64" in variants else "padded"

    def metric(variant: str) -> float | None:
        if p == 1:
            return None
        current = statistics.median(sample["seconds"] for sample in groups[(variant, p)])
        baseline = statistics.median(sample["seconds"] for sample in groups[(variant, 1)])
        return (p * current / baseline - 1) / (p - 1)

    check_fields(row, {"p": p, "e_unpadded": metric("unpadded"),
        "e_padded": metric(padded_variant),
        "e_padded_128": metric("padded") if variants["padded"] == 128 else None,
        "e_privatized": metric("privatized"), "padded_column_variant": padded_variant,
        "hardware_padded_column_variant": "padded"}, label)


def verify_m2(directory: Path, profile: dict, root: Path = ROOT) -> dict:
    raw = read_json(directory / "false_sharing_raw.json")
    meta = raw["metadata"]
    require(meta["quick_smoke_test"] is False and meta["iterations_per_worker"] == 5_000_000,
            "M2: full K=5,000,000 dataset required")
    require(meta["workers"] == [1, 2, 4, 8] and meta["repeats"] >= 3, "M2: complete worker/repeat schedule required")
    require(meta["cache_line_bytes"] == profile["cache_line_bytes"], "M2: line size/profile mismatch")
    check_native(meta["native"], "src/native/false_sharing.c", root)
    line = profile["cache_line_bytes"]
    variants = {"unpadded": 8, "padded": max(64, line), "privatized": 8}
    if line != 64:
        variants["padded_64"] = 64
    require(meta["variants_byte_stride"] == variants, "M2: padding variants incorrect")
    groups: dict[tuple, list] = {}
    for sample in raw["samples"]:
        variant, p, k = sample["variant"], sample["workers"], sample["iterations_per_worker"]
        require(variant in variants and p in meta["workers"] and k == 5_000_000, "M2: unexpected sample")
        require(sample["counts"] == [k] * p and sum(sample["counts"]) == p * k, "M2: incorrect per-worker or total count")
        require(sample["counts_verified"] is True and sample["total_increments"] == p * k, "M2: incorrect count metadata")
        require(sample["stride_bytes"] == variants[variant] and sample["alignment_bytes"] >= max(64, line), "M2: incorrect padding alignment")
        records = sample["worker_records"]
        require([r["worker_id"] for r in records] == list(range(p)), "M2: missing/duplicate worker records")
        for record in records:
            require(record["count"] == k and record["finished_ns"] >= record["started_ns"] >= sample["start_release_ns"], "M2: invalid worker result/timestamps")
            check_close(record["loop_seconds"], (record["finished_ns"] - record["started_ns"]) / 1e9, "M2: worker timing")
        seconds = (max(r["finished_ns"] for r in records) - sample["start_release_ns"]) / 1e9
        require(seconds > 0, "M2: nonpositive timing")
        check_close(sample["seconds"], seconds, "M2: sample timing")
        groups.setdefault((variant, p), []).append(sample)
    expected_keys = {(variant, p) for variant in variants for p in meta["workers"]}
    require(set(groups) == expected_keys, "M2: missing variant/worker cases")
    aggregates = {(row["variant"], row["workers"]): row for row in raw["aggregates"]}
    require(set(aggregates) == expected_keys and len(aggregates) == len(raw["aggregates"]), "M2: invalid aggregate rows")
    table = tsv_by(directory / "false_sharing_karp_flatt.tsv", ("variant", "workers"))
    require(set(table) == {(v, str(p)) for v, p in expected_keys}, "M2: invalid TSV cases")
    for (variant, p), runs in groups.items():
        require(sorted(r["repeat"] for r in runs) == list(range(1, meta["repeats"] + 1)), "M2: missing/duplicate repeat")
        timings = [r["seconds"] for r in runs]
        t = statistics.median(timings)
        t1 = statistics.median(r["seconds"] for r in groups[(variant, 1)])
        speedup = t1 / t
        expected = {"variant": variant, "workers": p, "iterations_per_worker": 5_000_000,
            "total_increments": p * 5_000_000, "stride_bytes": variants[variant], "repeats": len(runs),
            "median_seconds": t, "min_seconds": min(timings), "max_seconds": max(timings),
            "mean_seconds": statistics.mean(timings), "stdev_seconds": statistics.stdev(timings),
            "increments_per_second": p * 5_000_000 / t, "requested_speedup_t1_over_tp": speedup,
            "karp_flatt_requested": None if p == 1 else (p * t / t1 - 1) / (p - 1),
            "throughput_speedup": p * speedup, "weak_scaling_efficiency": speedup, "all_counts_verified": True}
        check_fields(aggregates[(variant, p)], expected, f"M2 aggregate {variant}/{p}")
        check_fields(table[(variant, str(p))], expected, f"M2 TSV {variant}/{p}")
        check_teacher_metric_aliases(aggregates[(variant, p)], groups, variants, p,
                                    f"M2 aggregate aliases {variant}/{p}")
        check_teacher_metric_aliases(table[(variant, str(p))], groups, variants, p,
                                    f"M2 TSV aliases {variant}/{p}")
    return {"milestone": "M2", "status": "pass", "verified_runs": len(raw["samples"]),
            "iterations_per_worker": 5_000_000, "worker_counts": meta["workers"], "variants": variants,
            "interpretation": "Fixed K per worker is weak scaling; requested Karp-Flatt values are not strong-scaling serial fractions."}


def physical_sequence(cores: int) -> list[int]:
    values = [1]
    while values[-1] * 2 <= cores:
        values.append(values[-1] * 2)
    if values[-1] != cores:
        values.append(cores)
    return values


def validated_roofline_peaks(profile: dict, roof: dict) -> tuple[float | None, float | None]:
    """Accept recorded peaks or the explicitly sourced published Apple M4 limit.

    A missing telemetry field is not a claim that manufacturer documentation is
    unavailable. This narrow fallback is a chip-wide upper bound, never a
    measurement of this kernel's sustained CPU memory bandwidth.
    """
    bandwidth = profile.get("peak_memory_bandwidth_bytes_per_second")
    recorded_bandwidth = roof.get("peak_memory_bandwidth_bytes_per_second")
    if bandwidth is None and recorded_bandwidth is not None:
        require(profile.get("cpu_model") == "Apple M4", "M3: unsupported published bandwidth fallback CPU")
        require(recorded_bandwidth == 120_000_000_000, "M3: incorrect published Apple M4 bandwidth")
        require(roof.get("peak_memory_bandwidth_source") == "https://support.apple.com/en-au/122209",
                "M3: unsupported Apple M4 bandwidth source")
        require(roof.get("peak_memory_bandwidth_scope") ==
                "Apple's documented 120 GB/s unified-memory bandwidth upper bound; shared by the chip, not measured sustained CPU bandwidth for this kernel",
                "M3: published Apple M4 bandwidth must be scoped as an unmeasured chip-wide upper bound")
        bandwidth = recorded_bandwidth
    check_close(recorded_bandwidth, bandwidth, "M3: roofline bandwidth/profile mismatch")
    compute = profile.get("peak_float64_flops_per_second")
    check_close(roof.get("peak_float64_flops_per_second"), compute, "M3: roofline compute/profile mismatch")
    for value, name in ((bandwidth, "bandwidth"), (compute, "float64 compute")):
        require(value is None or isinstance(value, (int, float)) and math.isfinite(value) and value > 0,
                f"M3: invalid asserted {name} peak")
    return bandwidth, compute


def verify_m3(directory: Path, params: dict, profile: dict) -> dict:
    raw = read_json(directory / "scaling_raw.json")
    require(raw["benchmark_mode"] == "full" and raw["base_n"] == params["N"] and raw["salted_n"] == params["N"], "M3: full salted dataset required")
    require(raw["student_id"] == params["student_id"] and raw["seed"] == params["seed"], "M3: incorrect salt")
    counts = physical_sequence(profile["physical_cores"])
    require(raw["process_counts"] == counts and raw["steps"] > 0 and raw["repeats"] >= 3, "M3: incomplete process/repeat schedule")
    table = tsv_by(directory / "scaling_metrics.tsv", ("mode", "workers"))
    require(set(table) == {(mode, str(p)) for mode in ("strong", "weak") for p in counts}, "M3: incorrect metric cases")
    digests = []
    for mode in ("strong", "weak"):
        cases = raw[mode]
        require([case["workers"] for case in cases] == counts, f"M3: missing {mode} cases")
        baseline = cases[0]
        for case in cases:
            p = case["workers"]
            n = params["N"] if mode == "strong" else math.ceil(params["N"] * math.sqrt(p))
            steps = raw["steps"]
            require(case["n"] == n and case["steps"] == steps, f"M3: incorrect {mode}/{p} dimensions")
            work = (n - 2) ** 2 * steps
            require(case["work_cell_updates"] == work, "M3: work definition mismatch")
            samples = case["samples"]
            require(sorted(s["repeat"] for s in samples) == list(range(1, raw["repeats"] + 1)), "M3: incomplete repeats")
            positive_samples([s["kernel_seconds"] for s in samples], raw["repeats"], f"M3 {mode}/{p}")
            for sample in samples:
                require(sample["workers"] == p and sample["n"] == n and sample["steps"] == steps and sample["warmup_updates_per_worker"] == 1,
                        "M3: inconsistent sample parameters")
                require(sample["end_to_end_seconds"] >= sample["kernel_seconds"] and sample["startup_and_initialization_seconds"] >= 0,
                        "M3: invalid end-to-end timing")
                spans = sample["row_ranges_exclusive_stop"]
                require(len(spans) == p and spans[0][0] == 1 and spans[-1][1] == n - 1 and
                        all(a < b for a, b in spans) and all(a[1] == b[0] for a, b in zip(spans, spans[1:])),
                        "M3: invalid row/halo decomposition")
                require(0 <= sample["max_absolute_error"] <= 1e-12, "M3: sample numerical error")
            times = [s["kernel_seconds"] for s in samples]
            summary = {"median_kernel_seconds": statistics.median(times), "minimum_kernel_seconds": min(times),
                "maximum_kernel_seconds": max(times), "median_end_to_end_seconds": statistics.median(s["end_to_end_seconds"] for s in samples),
                "max_absolute_error": max(s["max_absolute_error"] for s in samples)}
            check_fields(case, summary, f"M3 case {mode}/{p}")
            t_ratio = baseline["median_kernel_seconds"] / summary["median_kernel_seconds"]
            work_ratio = work / baseline["work_cell_updates"]
            check_fields(table[(mode, str(p))], {**summary, "mode": mode, "workers": p, "n": n, "steps": steps,
                "work_cell_updates": work, "time_speedup_T1_over_Tp": t_ratio,
                "conventional_throughput_speedup": work_ratio * t_ratio,
                "parallel_efficiency_percent": work_ratio * t_ratio / p * 100,
                "assignment_scaled_speedup": p / work_ratio * t_ratio if mode == "weak" else "",
                "gustafson_effective_serial_fraction": (p - work_ratio * t_ratio) / (p - 1) if mode == "weak" and p > 1 else "",
                "updates_per_second": work / summary["median_kernel_seconds"]}, f"M3 TSV {mode}/{p}")
            path = directory / case["array_path"]
            require(path.resolve().is_relative_to(directory.resolve()), "M3: output array escapes result directory")
            actual = load_saved_array(path)
            require(actual.shape == (n, n) and actual.dtype == np.float64, "M3: saved shape/dtype mismatch")
            expected = reference_stencil(init_grid(n, params["seed"]), steps)
            require(np.all(np.isfinite(actual)) and np.allclose(actual, expected, rtol=0, atol=1e-12), f"M3: stencil mismatch {mode}/{p}")
            digest = rounded_salted_digest(actual, params["student_id"])
            require(digest == rounded_salted_digest(expected, params["student_id"]), f"M3: rounded digest mismatch {mode}/{p}")
            digests.append({"mode": mode, "workers": p, "shape": [n, n], "salted_rounded_sha256": digest,
                            "maximum_absolute_error": float(np.max(np.abs(actual - expected)))})
            print(f"  checked stencil {mode} P={p}, N={n}", flush=True)
            del actual, expected

    strong = raw["strong"]
    t1 = strong[0]["median_kernel_seconds"]
    denominator = sum((1 - 1 / c["workers"]) ** 2 for c in strong)
    fit = raw["amdahl_fit"]
    if denominator:
        serial = sum((1 - 1 / c["workers"]) * (c["median_kernel_seconds"] / t1 - 1 / c["workers"]) for c in strong) / denominator
        bounded = min(1, max(0, serial))
        check_fields(fit, {"identifiable": True, "unconstrained_serial_fraction": serial, "bounded_serial_fraction": bounded,
            "unconstrained_asymptotic_speedup": 1 / serial if serial > 0 else None,
            "bounded_asymptotic_speedup": 1 / bounded if bounded > 0 else None,
            "inverse_speedup_residual_sum_of_squares": sum((c["median_kernel_seconds"] / t1 - (serial + (1 - serial) / c["workers"])) ** 2 for c in strong),
            "physical_range_violation": not 0 <= serial <= 1}, "M3 Amdahl")
    else:
        require(fit["identifiable"] is False, "M3: unidentifiable Amdahl fit")
    weak = raw["weak"]
    baseline = weak[0]
    scaled = [(case["workers"], case["work_cell_updates"] / baseline["work_cell_updates"] *
               baseline["median_kernel_seconds"] / case["median_kernel_seconds"]) for case in weak]
    gustafson = raw["gustafson_fit"]
    gust_denominator = sum((p - 1) ** 2 for p, _ in scaled)
    if gust_denominator:
        alpha = sum((p - 1) * (p - speedup) for p, speedup in scaled) / gust_denominator
        bounded_alpha = min(1, max(0, alpha))
        check_fields(gustafson, {"identifiable": True, "unconstrained_serial_fraction": alpha,
            "bounded_serial_fraction": bounded_alpha, "physical_range_violation": not 0 <= alpha <= 1,
            "unconstrained_residual_sum_of_squares": sum((speedup - (p - alpha * (p - 1))) ** 2 for p, speedup in scaled),
            "bounded_residual_sum_of_squares": sum((speedup - (p - bounded_alpha * (p - 1))) ** 2 for p, speedup in scaled)}, "M3 Gustafson")
        require([row["workers"] for row in gustafson["residuals"]] == counts, "M3: missing Gustafson residuals")
        for row, (p, speedup) in zip(gustafson["residuals"], scaled):
            unconstrained_fitted, bounded_fitted = p - alpha * (p - 1), p - bounded_alpha * (p - 1)
            check_fields(row, {"workers": p, "measured_conventional_throughput_speedup": speedup,
                "unconstrained_fitted_speedup": unconstrained_fitted, "bounded_fitted_speedup": bounded_fitted,
                "unconstrained_residual": speedup - unconstrained_fitted,
                "bounded_residual": speedup - bounded_fitted}, "M3 Gustafson residual")
    else:
        require(gustafson["identifiable"] is False, "M3: unidentifiable Gustafson fit")
    roof = read_json(directory / "roofline_summary.json")
    require(roof["benchmark_mode"] == "full" and roof["salted_n"] == params["N"], "M3: incorrect roofline dataset")
    require(roof["amdahl_fit"] == fit, "M3: roofline/Amdahl mismatch")
    require(roof["gustafson_fit"] == gustafson, "M3: roofline/Gustafson mismatch")
    check_close(roof["flops_per_interior_update"], 5, "M3: roofline FLOP count")
    models = roof["arithmetic_intensity_models"]
    check_fields(models["optimistic_streaming"], {"dram_bytes_per_update": 16, "flops_per_byte": 5 / 16}, "M3: streaming intensity")
    check_fields(models["streaming_with_write_allocation"], {"dram_bytes_per_update": 24, "flops_per_byte": 5 / 24}, "M3: write allocation intensity")
    check_fields(models["logical_ufunc_array_traffic"], {"array_bytes_per_update": 112, "flops_per_byte": 5 / 112}, "M3: logical intensity")
    check_fields(roof, {"arithmetic_intensity": 5 / 16, "classification": "undetermined"},
                 "M3: instructor compatibility fields")
    bandwidth, compute = validated_roofline_peaks(profile, roof)
    if "theoretical_bandwidth_ceiling_gflops_per_second" in roof:
        check_fields(roof["theoretical_bandwidth_ceiling_gflops_per_second"], {
            "optimistic_16_bytes_per_update": bandwidth * (5 / 16) / 1e9 if bandwidth is not None else None,
            "write_allocate_24_bytes_per_update": bandwidth * (5 / 24) / 1e9 if bandwidth is not None else None,
        }, "M3: theoretical bandwidth ceiling")
    if isinstance(bandwidth, (int, float)) and bandwidth > 0 and isinstance(compute, (int, float)) and compute > 0:
        check_close(roof["ridge_point_flops_per_byte"], compute / bandwidth, "M3: roofline ridge")
    else:
        require(roof["ridge_point_flops_per_byte"] is None and roof["limiting_regime"] ==
                "undetermined_without_documented_bandwidth_and_float64_compute_peaks",
                "M3: unsupported definitive roofline classification")
    cases = raw["strong"] + raw["weak"]
    require(len(roof["operating_points"]) == len(cases), "M3: missing roofline operating points")
    for point, case in zip(roof["operating_points"], cases):
        work, seconds = case["work_cell_updates"], case["median_kernel_seconds"]
        check_fields(point, {"workers": case["workers"], "n": case["n"], "two_grid_working_set_bytes": 2 * case["n"] ** 2 * 8,
            "estimated_flops": work * 5, "measured_gflops_per_second": work * 5 / seconds / 1e9,
            "minimum_streaming_bytes_per_second_model": work * 16 / seconds,
            "logical_ufunc_array_bytes_per_second_model": work * 112 / seconds}, "M3 roofline operating point")
    return {"milestone": "M3", "status": "pass", "steps": raw["steps"], "process_counts": counts,
            "verified_arrays": digests, "amdahl_fit_recomputed": True, "gustafson_fit_recomputed": True,
            "roofline_arithmetic_recomputed": True}


def file_manifest(root: Path, directory: Path) -> list[dict]:
    paths = {root / name for name in ("verify_numerics.py", "verify_outputs.py", "verify_outputs.py.txt", "check_teacher.py") if (root / name).is_file()}
    for folder in (root / "src", root / "tests", directory):
        if folder.exists():
            paths.update(path for path in folder.rglob("*") if path.is_file() and
                "__pycache__" not in path.parts and path.suffix != ".pyc" and path.name != "local_verification_receipt.json")
    for name in ("README.md", "GUIDE.md", "HANDOUT_NOTES.md", "TEACHER_VERIFICATION.md", "requirements.txt", "requirements-dev.txt",
                 "run_lab.py", ".gitignore", "ParallelComputingLabPracticum_Paradigm.pdf"):
        if (root / name).exists():
            paths.add(root / name)
    return [{"path": str(path.relative_to(root)) if path.is_relative_to(root) else str(path),
             "bytes": path.stat().st_size, "sha256": sha256_file(path)} for path in sorted(paths)]


def verify_file_manifest(manifest: list[dict], root: Path) -> None:
    """Compare an earlier local receipt to files; this is not authentication."""
    for record in manifest:
        path = root / record["path"]
        require(path.is_file() and path.stat().st_size == record["bytes"] and sha256_file(path) == record["sha256"],
                f"file changed since local receipt: {record['path']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results")
    parser.add_argument("--student-id", default="30103059")
    parser.add_argument("--no-receipt", action="store_true")
    args = parser.parse_args(argv)
    directory = args.output_dir.resolve()
    receipt_path = directory / "local_verification_receipt.json"
    # A normal rerun invalidates its own stale receipt; read-only mode leaves
    # receipts untouched, including the separate instructor-generated .sig.
    if not args.no_receipt:
        receipt_path.unlink(missing_ok=True)
    try:
        params, profile, first = verify_m0(directory, args.student_id)
        checks = [first]
        print("[PASS] M0 recorded host topology and exact salt", flush=True)
        for label, operation in (("M1", lambda: verify_m1(directory, params)),
                                 ("M2", lambda: verify_m2(directory, profile)),
                                 ("M3", lambda: verify_m3(directory, params, profile))):
            checks.append(operation())
            print(f"[PASS] {label} persisted outputs and recomputed metrics", flush=True)
        receipt = {
            "schema_version": 1, "scope": "local_self_check_not_instructor_signature",
            "cryptographically_signed": False,
            "instructor_verifier_available": (ROOT / "verify_outputs.py.txt").is_file(),
            "authenticity_limit": "Unsigned local checks and hashes; not an instructor signature or proof of authorship, measurement origin, or timing.",
            "verified_at_utc": datetime.now(timezone.utc).isoformat(), "student_id": args.student_id,
            "environment": {"python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform()},
            "digest_encoding": "SHA-256 of canonical JSON header (scheme local-rounded-array-v1, student_id, shape, decimals=6, dtype=<f8, order=C), NUL, then np.round(array,6) C-order little-endian float64 bytes; signed zero normalized",
            "checks": checks, "files": file_manifest(ROOT, directory),
            "manifest_exclusions": ["local_verification_receipt.json itself", "__pycache__ and .pyc runtime caches"],
        }
        if not args.no_receipt:
            receipt_path.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")
        print("All local checks passed. " + ("Receipt omitted." if args.no_receipt else f"Unsigned local receipt: {receipt_path}"))
        return 0
    except Exception as error:
        if not args.no_receipt:
            receipt_path.unlink(missing_ok=True)
        print(f"[FAIL] {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
