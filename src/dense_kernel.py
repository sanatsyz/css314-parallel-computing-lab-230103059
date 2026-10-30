"""Compare the literal i-j-k and i-k-j loop orders via ctypes."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import time
import numpy as np

from locality_native import load_library, pointer


def multiply(a, b, order):
    if order not in {"ijk", "ikj"}:
        raise ValueError("order must be ijk or ikj")
    if a.ndim != 2 or a.shape != b.shape or a.shape[0] != a.shape[1]:
        raise ValueError("equal square matrices required")
    a = np.ascontiguousarray(a, dtype=np.float64)
    b = np.ascontiguousarray(b, dtype=np.float64)
    c = np.zeros_like(a)
    lib, _ = load_library()
    getattr(lib, "matmul_" + order)(pointer(a), pointer(b), pointer(c), a.shape[0])
    return c


def benchmark(n, seed, repeats=3):
    m = n // 2
    rng = np.random.default_rng(seed)
    a = np.ascontiguousarray(rng.random((n, n))[:m, :m])
    b = np.ascontiguousarray(rng.random((n, n))[:m, :m])
    lib, metadata = load_library()
    arrays, samples = {}, {"ijk": [], "ikj": []}
    for order in ["ijk", "ikj"]:
        warmup = np.zeros_like(a)
        getattr(lib, "matmul_" + order)(pointer(a), pointer(b), pointer(warmup), m)
    # Alternate order between trials to reduce consistent warm-cache ordering bias.
    for repeat in range(repeats):
        for order in (["ijk", "ikj"] if repeat % 2 == 0 else ["ikj", "ijk"]):
            c = np.zeros_like(a)
            begin = time.perf_counter_ns()
            getattr(lib, "matmul_" + order)(pointer(a), pointer(b), pointer(c), m)
            elapsed = time.perf_counter_ns() - begin
            samples[order].append(elapsed)
            arrays[order] = c
    reference = a @ b
    for c in arrays.values():
        np.testing.assert_allclose(c, reference, rtol=0, atol=1e-12)
    medians = {key: statistics.median(value) for key, value in samples.items()}
    return {"recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "N": n, "M": m, "seed": seed, "repeats": repeats, "warmups_per_algorithm": 1,
            "time_ns": samples, "median_time_ns": medians,
            "speedup": medians["ijk"] / medians["ikj"],
            "max_abs_difference": float(np.max(np.abs(arrays["ijk"] - arrays["ikj"]))),
            "max_abs_error_vs_numpy": {k: float(np.max(np.abs(v - reference))) for k, v in arrays.items()},
            "tolerance": {"rtol": 0, "atol": 1e-12}, "native": metadata,
            "notes": "Full salted NxN matrices initialized; contiguous leading M=N/2 block multiplied. Allocation excluded; no fast math or fused contraction. Native hot loops permitted by ctypes option."}, {"dense_a": a, "dense_b": b, "dense_ijk": arrays["ijk"], "dense_ikj": arrays["ikj"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    params = json.loads((args.output_dir / "salted_params.json").read_text())
    result, arrays = benchmark(32 if args.quick else params["N"], params["seed"])
    directory = args.output_dir / "arrays"
    directory.mkdir(parents=True, exist_ok=True)
    for name, array in arrays.items():
        np.save(directory / (name + ".npy"), array, allow_pickle=False)
    (args.output_dir / "loop_interchange.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"M={result['M']}; ijk/ikj speedup {result['speedup']:.3f}; results verified")


if __name__ == "__main__":
    main()
