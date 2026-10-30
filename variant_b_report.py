"""Generate RESULTS_B.md using independently verified Variant B evidence."""

import argparse
import json
from pathlib import Path

from verify_variant_b import CASES, TOTALS, verify_results


ROOT = Path(__file__).resolve().parent
LABELS = {"a_micro": "A: Micro (k=1)", "a_coarse": "A: Coarse (k=10000)",
          "b_queue": "B: Queue choke", "c_buffered": "C: Buffered batch"}


def status(value):
    return "Met" if value else "Not met on this run"


def render_report(output_dir=ROOT / "variant_b_results", destination=ROOT / "RESULTS_B.md"):
    directory = Path(output_dir)
    checked = verify_results(directory)
    host = json.loads((directory / "host_profile.json").read_text(encoding="utf-8"))
    config = json.loads((directory / "configuration.json").read_text(encoding="utf-8"))
    rows = {case: {row["workers"]: row for row in checked["checks"][case]["summary"]} for case in CASES}
    a, b, c = (checked["rubric"][letter] for letter in "ABC")
    topology = "; ".join("{} {} cores".format(level["physical_cores"], level["name"].lower())
                         for level in host.get("performance_levels", []))
    lines = [
        "# CSS314 Variant B: granularity and IPC results", "",
        "Student ID: **{}**. Branch: **{}** in the existing course repository.".format(config["student_id"], config["branch"]),
        "The supplied PDF is preserved unchanged under its original CS482 filename; the student's course label is CSS314.",
        "", "## Hardware and method", "",
        "| Item | Recorded value |", "| --- | --- |",
        "| CPU | {} |".format(host["cpu_model"]),
        "| Physical cores / logical threads | {} / {} |".format(host["physical_cores"], host["logical_threads"]),
        "| Core groups | {} |".format(topology or "Not reported"),
        "| Architecture / OS | {} / {} {} |".format(host["architecture"], host["os"], host["kernel_version"]),
        "| Python | {} {} |".format(host["python"]["implementation"], host["python"]["version"]),
        "| os.cpu_count / multiprocessing.cpu_count | {} / {} |".format(host["os_cpu_count"], host["multiprocessing_cpu_count"]),
        "| Process start method | spawn |",
        "| Timer | {}; resolution {:.3g} seconds |".format(host["timer"]["implementation"], host["timer"]["resolution_seconds"]),
        "| Repetitions | Three full trials at each P=1,2,4,8; median runtime |",
        "", "Workers were not pinned; the operating system scheduled them. Available affinity information is recorded in the hardware JSON. Experiments ran sequentially, with worker-count order rotated across repetitions. Background desktop activity, scheduling, core type, frequency and thermal state can affect times.",
        "", "A times fresh Pool creation, map and teardown; its final checksum reduction is outside the timer, matching the handout. B/C create the Queue and Process objects before timing, then time process startup, queue consumption, and joins. Monitor setup/teardown and queue cleanup are outside the interval. A low-frequency exit monitor remains active during B/C; B additionally accumulates a checksum in the timed receive loop. These safety checks add some parent/background overhead. No startup time was subtracted.",
        "", "## Full default-workload matrix", "",
        "| Configuration | T1 (s) | T2 (s) | T4 (s) | T8 (s) | S8 | E8 (%) | e(2) | e(4) | e(8) | Verdict |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    verdicts = {
        "a_micro": "{}; compare with coarse tasks".format("Fine tasks slower at every P" if a["micro_slower_at_all_worker_counts"] else "Fine/coarse difference depends on P"),
        "a_coarse": "Same computation, fewer dispatch envelopes",
        "b_queue": "Negative scaling at P=8" if b["t8_greater_than_t1"] else "P=8 runtime below baseline",
        "c_buffered": "Final numeric criteria: {}".format(status(c["meets_numeric_condition"])),
    }
    for case in CASES:
        item = rows[case]
        lines.append("| {} | {:.6f} | {:.6f} | {:.6f} | {:.6f} | {:.3f} | {:.2f} | {:.6f} | {:.6f} | {:.6f} | {} |".format(
            LABELS[case], *(item[p]["median_seconds"] for p in (1, 2, 4, 8)),
            item[8]["speedup"], item[8]["efficiency_percent"],
            *(item[p]["karp_flatt"] for p in (2, 4, 8)), verdicts[case]))
    lines.extend([
        "", "A processes range(1,1_000_000+1) with the handout's naive Collatz loop. Both A cases produce checksum **131434424** in every trial. Micro uses 1,000,000 task envelopes; coarse uses 100 envelopes of 10,000 inputs. No memoization enters the timed workload.",
        "", "B processes exactly 400,000 items and C exactly 10,000,000, with C batch size 10,000. Every worker starts its local sequence at i=0. Work partitioning includes remainders, and all queue checksums, message/batch counts, sentinels and zero worker exit codes are checked. C sends 1,000 data batches at these defaults, plus P completion sentinels, instead of one data message per input.",
        "", "Metrics: `S(P)=T1/TP`, `E(P)=100*S(P)/P`, `e(P)=(P*TP/T1-1)/(P-1)`. Each configuration uses its own one-worker median. The P=1 Karp-Flatt value is undefined (JSON null, empty TSV cell). Raw trials retain more precision than this table.",
        "", "## Granularity comparison", "",
        "| P | Micro / coarse runtime | Coarse S(P) | Coarse E(P) (%) |", "| ---: | ---: | ---: | ---: |",
    ])
    for p in (1, 2, 4, 8):
        lines.append("| {} | {:.3f}x | {:.3f} | {:.2f} |".format(
            p, a["micro_over_coarse_runtime_ratio"][str(p)], rows["a_coarse"][p]["speedup"], rows["a_coarse"][p]["efficiency_percent"]))
    lines.extend([
        "", "The fine/coarse comparison changes dispatch granularity while keeping the input range and scalar work identical. A larger runtime for micro-tasks is consistent with dispatch and result-handling overhead overwhelming useful computation. Timing alone does not directly measure master starvation or isolate each part of that overhead.",
        "", "## Buffering throughput comparison", "",
        "| P | B items/s | C items/s | C / B throughput gain | C runtime below B? |",
        "| ---: | ---: | ---: | ---: | --- |",
    ])
    for p in (1, 2, 4, 8):
        lines.append("| {} | {:.0f} | {:.0f} | {:.3f}x | {} |".format(
            p, TOTALS["b_queue"] / rows["b_queue"][p]["median_seconds"],
            TOTALS["c_buffered"] / rows["c_buffered"][p]["median_seconds"],
            c["throughput_gain_over_unbuffered"][str(p)],
            rows["c_buffered"][p]["median_seconds"] < rows["b_queue"][p]["median_seconds"]))
    lines.extend([
        "", "C processes 25 times as many items as B. Throughput normalizes that difference: `(10,000,000/TC)/(400,000/TB)`. This cross-configuration improvement is distinct from C's within-configuration strong-scaling speedup, `TC1/TC8`.",
        "", "## Measured handout criteria", "",
        "| Check | Actual observation | Condition |", "| --- | --- | --- |",
        "| A: micro slower than coarse at each P | See ratios above | {} |".format(status(a["meets_numeric_condition"])),
        "| B: T8 > T1 | T8/T1={:.3f} | {} |".format(rows["b_queue"][8]["median_seconds"] / rows["b_queue"][1]["median_seconds"], status(b["t8_greater_than_t1"])),
        "| B: monotonically increasing runtime | {:.6f}, {:.6f}, {:.6f}, {:.6f} seconds | {} |".format(
            *(rows["b_queue"][p]["median_seconds"] for p in (1, 2, 4, 8)), status(b["runtime_monotonically_increases"])),
        "| B: increasing e across 2,4,8 | {:.6f}, {:.6f}, {:.6f} | {} |".format(b["e2"], b["e4"], b["e8"], status(b["e2_e4_e8_strictly_increase"])),
        "| C: throughput gain at P=8 >10x | {:.3f}x | {} |".format(c["throughput_gain_over_unbuffered"]["8"], status(c["eight_worker_throughput_gain_over_ten"])),
        "| C: S8 >5 | {:.6f} | {} |".format(c["speedup_8"], status(c["speedup_8"] > 5)),
        "| C: final e(8) <=0.05 | {:.6f} | {} |".format(c["karp_flatt_8"], status(c["karp_flatt_8"] <= 0.05)),
        "| C: task text e(8) <0.04 | {:.6f} | {} |".format(c["karp_flatt_8"], status(c["task_e8_below_004"])),
        "", "Independent numerical/schema verification passes. The empirical conditions are reported separately; a missed condition stays missed. The programs retain the exact default workloads rather than editing times or changing the workload to satisfy an expected trend.",
        "", "Shared-queue negative scaling is consistent with communication and synchronization overhead. A Karp-Flatt trajectory alone cannot prove bus thrashing, cache-coherence storms, or lock-wait time; no hardware performance counters were collected. Buffering reduces message frequency, but fresh process startup and scheduling across mixed core types remain part of elapsed time and can limit short-run S8.",
        "", "## Handout inconsistencies", "",
        "The illustrative A coarse times (4.80,2.50,1.35,0.75 seconds) give e(2)=0.041667 and e(8)=0.035714, rather than printed e(8)=0.038. The illustrative B times (1.20,1.95,3.80,7.60) give e(2)=2.250000 and e(8)=7.095238, rather than 1.250 and 6.280. These examples were not copied into the measured matrix.",
        "", "C's task text asks for e<0.04; the final sign-off uses e(8)<=0.05 and the synthesis table uses e(2),e(8)<0.05. The underlying e values are supplied above and the local receipt retains these separate observations. Page 1's final task line is clipped in the supplied PDF. The visible experiment parameters and final requirements are preserved.",
        "", "## Evidence, reproduction and Git submission", "",
        "- [Beginner explanation and commands](VARIANT_B_GUIDE.md)",
        "- [Host profile](variant_b_results/host_profile.json) and [configuration](variant_b_results/configuration.json)",
        "- [A micro](variant_b_results/a_micro.json), [A coarse](variant_b_results/a_coarse.json), [B queue](variant_b_results/b_queue.json), [C buffered](variant_b_results/c_buffered.json): full raw trials and adjacent TSV summaries",
        "- [Independent unsigned local verification](variant_b_results/verification.json)",
        "", "Run `python3 run_variant_b.py` to reproduce all default cases sequentially and refresh this report. This can take several minutes. Small `--quick` runs are kept under a separate smoke directory and cannot pass full-workload verification.",
        "", "The branch uses `Part 1: Completed task granularity comparison`, the handout's `Part 2: Reproduced IPC queue contention and recorded e(p) explosion`, and `Part 3 & 4: Completed buffer optimization and verified RESULTS_B.md` checkpoint messages. The requested 'explosion' message is a provenance label; the measured e curve above determines whether that trend occurred.",
        "", "**Instructor sign-off: pending.** An in-person or remote Git review must be performed by the instructor. This work was prepared with AI assistance. Source and data hashes in the local receipt record the delivered files; they are not an instructor signature or independent proof of timing capture.",
    ])
    target = Path(destination)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "variant_b_results")
    parser.add_argument("--report", type=Path, default=ROOT / "RESULTS_B.md")
    args = parser.parse_args()
    print("Wrote {}".format(render_report(args.output_dir, args.report)))


if __name__ == "__main__":
    main()
