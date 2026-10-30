"""Generate the required RESULTS.md from independently checked practice data."""

import argparse
import json
from pathlib import Path

from practice_verify import verify_results


ROOT = Path(__file__).resolve().parent


def render_report(output_dir, report_path=ROOT / "RESULTS.md"):
    directory = Path(output_dir)
    verification = verify_results(directory)
    host = json.loads((directory / "host_profile.json").read_text())
    config = json.loads((directory / "configuration.json").read_text())
    summaries = {letter: {row["workers"]: row for row in verification["checks"][letter]["summary"]}
                 for letter in "ABC"}
    observations = verification["rubric"]
    topology = "; ".join("{} {} cores".format(level["physical_cores"], level["name"].lower())
                         for level in host.get("performance_levels", []))
    topology_note = "Recorded core groups: {}. ".format(topology) if topology else ""
    lines = [
        "# CSS314: Karp-Flatt practice results", "",
        "Student ID: **{}**. Git branch: **{}**.".format(config["student_id"], config["branch"]),
        "The practice handout requests a student branch, so this work uses the existing course repository. The previous lab remains on `main`.",
        "", "## Hardware and measurement method", "",
        "| Item | Observed value |", "| --- | --- |",
        "| CPU | {} |".format(host["cpu_model"]),
        "| Physical cores / logical threads | {} / {} |".format(host["physical_cores"], host["logical_threads"]),
        "| Architecture / OS | {} / {} {} |".format(host["architecture"], host["os"], host["kernel_version"]),
        "| Python | {} {} |".format(host["python"]["implementation"], host["python"]["version"]),
        "| Process start method | spawn |",
        "| Repetitions | Three complete trials for each P=1,2,4; median reported |",
        "| Timer | {}; resolution {:.3g} seconds |".format(host["timer"]["implementation"], host["timer"]["resolution_seconds"]),
        "", topology_note + "Workers were not pinned. All experiments ran sequentially; desktop activity, scheduling, frequency and thermal state can still affect timings.",
        "", "Each trial includes fresh process/pool startup and shutdown as specified by the handout. A includes the intentional 0.40-second sleep. B times process start through join after creating its counter, locks and Process objects. C includes fresh Pool creation, task execution, teardown, and the final sum. No startup time was subtracted.",
        "", "## Required default-workload results", "",
        "| Experiment | T1 (s) | T2 (s) | T4 (s) | S4 | E4 (%) | e(2) | e(4) | Architectural diagnosis |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    descriptions = {
        "A": "Fixed 0.40 s serial delay; other overhead also affects observed e.",
        "B": "One shared counter with per-increment locks; contention causes negative speedup." if summaries["B"][4]["speedup"] < 1 else "Shared-counter synchronization cost measured directly.",
        "C": "Private counters and one final reduction; process startup remains in elapsed time.",
    }
    labels = {"A": "A: Serial tail", "B": "B: Lock contention", "C": "C: Privatized state"}
    for letter in "ABC":
        rows = summaries[letter]
        lines.append("| {} | {:.6f} | {:.6f} | {:.6f} | {:.3f} | {:.2f} | {:.6f} | {:.6f} | {} |".format(
            labels[letter], rows[1]["median_seconds"], rows[2]["median_seconds"], rows[4]["median_seconds"],
            rows[4]["speedup"], rows[4]["efficiency_percent"], rows[2]["karp_flatt"], rows[4]["karp_flatt"], descriptions[letter]))
    lines.extend([
        "", "A performs 16 chunks of `heavy_math(2_000_000)` plus the delay. B performs exactly 2,000,000 total increments. C performs exactly 20,000,000 total increments. These totals stay fixed as P changes. B and C have different default work sizes; their within-experiment speedups use their own one-worker baseline.",
        "", "Metrics use `S(P)=T1/TP`, `E(P)=100*S(P)/P`, and `e(P)=(P*TP/T1-1)/(P-1)`. The P=1 Karp-Flatt value is undefined and is stored as null, not zero.",
        "", "## Handout rubric assessed against the measured data", "",
        "| Check | Actual observation | Numeric condition |", "| --- | --- | --- |",
    ])
    ratio = observations["A"]["e4_over_e2"]
    ratio_text = "undefined" if ratio is None else "{:.6f}".format(ratio)
    verdict = lambda letter: "Met" if observations[letter]["meets_numeric_condition"] else "Not met on this run"
    lines.extend([
        "| A: 0.80 <= e(4)/e(2) <= 1.25 | Ratio {} | {} |".format(ratio_text, verdict("A")),
        "| B: T4 > T1 and substantially increasing e | T4/T1={:.3f}; e(2)={:.6f}, e(4)={:.6f} | {} for T4>T1 and increasing e; instructor interprets 'substantially' |".format(
            summaries["B"][4]["median_seconds"] / summaries["B"][1]["median_seconds"], observations["B"]["e2"], observations["B"]["e4"], verdict("B")),
        "| C: T4 < T1 and E4 > 70% | T4<T1: {}; E4={:.2f}% | {} |".format(
            observations["C"]["t4_less_than_t1"], observations["C"]["efficiency_4_percent"], verdict("C")),
        "", "Every numerical result and recomputed metric passes the separate local verifier. A missed performance condition remains reported as missed; the measurements were not changed to match the example table.",
        "", "A's known serial pause is present in every timed run, but that does not make the entire implementation obey an ideal fixed-serial-fraction model: process startup, scheduling and mixed core speeds also contribute. B's slowdown directly shows that shared locking can defeat parallel execution. Its e values need not grow monotonically when elapsed-time growth saturates. C removes the shared hot-loop lock, but startup is a substantial cost for its short default run.",
        "", "Karp-Flatt values summarize departure from ideal strong scaling. They alone cannot prove a specific cache-coherence protocol, bus bottleneck, or lock-wait mechanism; no hardware counters were collected.",
    ])
    supplemental = verification.get("supplemental", {}).get("C_200m")
    if supplemental is not None:
        rows = {row["workers"]: row for row in supplemental["summary"]}
        lines.extend([
            "", "## Supplemental C: startup amortization", "",
            "This separately labelled diagnostic uses **200,000,000** total increments, ten times the required C workload. It retains fresh spawn pools and all startup/shutdown costs. It does not replace the 20,000,000-increment primary result or change the rubric verdict above.",
            "", "| Total increments | T1 (s) | T2 (s) | T4 (s) | S4 | E4 (%) | e(2) | e(4) |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            "| 200000000 | {:.6f} | {:.6f} | {:.6f} | {:.3f} | {:.2f} | {:.6f} | {:.6f} |".format(
                rows[1]["median_seconds"], rows[2]["median_seconds"], rows[4]["median_seconds"],
                rows[4]["speedup"], rows[4]["efficiency_percent"], rows[2]["karp_flatt"], rows[4]["karp_flatt"]),
            "", "Compare this efficiency with the default workload to inspect how additional independent work amortizes process overhead. All supplemental counter totals and metrics are independently checked too.",
        ])
    lines.extend([
        "", "## Handout arithmetic notes", "",
        "The example A timings (3.20, 1.80, 1.10 seconds) give e(2)=0.125 and e(4)=0.125. The example B timings (0.65, 1.10, 2.40 seconds) give e(2)=2.384615 and e(4)=4.589744. The inconsistent printed example e values were not copied into the measured table.",
        "", "## Evidence and reproduction", "",
        "- [Beginner instructions](PRACTICE_GUIDE.md)",
        "- [Hardware profile](practice_results/host_profile.json) and [configuration](practice_results/configuration.json)",
        "- [A raw samples](practice_results/experiment_a.json), [B raw samples](practice_results/experiment_b.json), [C raw samples](practice_results/experiment_c.json)",
        "- [Independent local verification](practice_results/verification.json)",
        "", "Run `python3 run_practice.py` from this directory for the default experiments. Use `python3 run_practice.py --supplemental-c` to also reproduce the additional 200-million-increment C diagnostic.",
        "", "## Git provenance and instructor sign-off", "",
        "The practice branch contains the handout's three requested checkpoint messages: `Part 1: Experiment A complete`, `Part 2: Captured lock contention pathology and Karp-Flatt surge`, and `Part 3 & 4: Completed privatization fix and verified RESULTS.md`. Existing main-branch lab history and milestone tags are retained.",
        "", "**Instructor sign-off: pending.** This report and its local verification do not substitute for the in-person or remote Git sign-off requested by the handout. This work was prepared with AI assistance.",
    ])
    destination = Path(report_path)
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "practice_results")
    parser.add_argument("--report", type=Path, default=ROOT / "RESULTS.md")
    args = parser.parse_args()
    print("Wrote {}".format(render_report(args.output_dir, args.report)))


if __name__ == "__main__":
    main()
