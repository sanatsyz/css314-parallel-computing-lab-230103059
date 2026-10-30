"""Real strided reads, five warmups then five timed samples per stride."""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import time
import numpy as np

from locality_native import load_library, pointer


def benchmark(elements=16_777_216, warmups=5, repeats=5):
    lib, metadata = load_library()
    data = np.ones(elements, dtype=np.float64)
    address = pointer(data)
    rows, raw = [], []
    for stride in [1, 2, 4, 8, 16, 32, 64, 128]:
        touched = (elements + stride - 1) // stride
        warmup_samples, samples = [], []
        for i in range(warmups + repeats):
            begin = time.perf_counter_ns()
            total = lib.stride_sum(address, elements, stride)
            elapsed = time.perf_counter_ns() - begin
            if total != touched:
                raise AssertionError(f"Stride {stride}: incorrect reduction")
            (warmup_samples if i < warmups else samples).append(elapsed)
        median = statistics.median(samples)
        rows.append({"stride_elements": stride, "stride_bytes": stride * 8,
                     "elements_touched": touched, "median_time_ns": median,
                     "ns_per_element": median / touched, "sum": total})
        raw.append({"stride_elements": stride, "warmup_time_ns": warmup_samples,
                    "time_ns": samples, "verified_sum": total})
    return rows, {"recorded_at_utc": datetime.now(timezone.utc).isoformat(),
                  "buffer_elements": elements, "dtype": "float64", "buffer_bytes": data.nbytes,
                  "warmups": warmups, "repeats": repeats, "native": metadata,
                  "notes": "Scalar native volatile loads; measures wall time per element, not hardware cache-miss latency. Fixed stride order; no fabricated cache counters.",
                  "runs": raw}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    elements = 8192 if args.quick else json.loads((args.output_dir / "salted_params.json").read_text())["buffer_elements"]
    rows, raw = benchmark(elements)
    with (args.output_dir / "stride_results.tsv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader(); writer.writerows(rows)
    (args.output_dir / "stride_raw.json").write_text(json.dumps(raw, indent=2) + "\n")
    for row in rows:
        print(f"stride {row['stride_elements']:3}: {row['ns_per_element']:.3f} ns/element")


if __name__ == "__main__":
    main()
