# CSS314: Karp-Flatt practice results

Student ID: **230103059**. Git branch: **practice-230103059**.
The practice handout requests a student branch, so this work uses the existing course repository. The previous lab remains on `main`.

## Hardware and measurement method

| Item | Observed value |
| --- | --- |
| CPU | Apple M4 |
| Physical cores / logical threads | 10 / 10 |
| Architecture / OS | arm64 / Darwin 27.0.0 |
| Python | CPython 3.14.3 |
| Process start method | spawn |
| Repetitions | Three complete trials for each P=1,2,4; median reported |
| Timer | mach_absolute_time(); resolution 4.17e-08 seconds |

Recorded core groups: 4 performance cores; 6 efficiency cores. Workers were not pinned. All experiments ran sequentially; desktop activity, scheduling, frequency and thermal state can still affect timings.

Each trial includes fresh process/pool startup and shutdown as specified by the handout. A includes the intentional 0.40-second sleep. B times process start through join after creating its counter, locks and Process objects. C includes fresh Pool creation, task execution, teardown, and the final sum. No startup time was subtracted.

## Required default-workload results

| Experiment | T1 (s) | T2 (s) | T4 (s) | S4 | E4 (%) | e(2) | e(4) | Architectural diagnosis |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| A: Serial tail | 2.945825 | 1.583706 | 1.056806 | 2.787 | 69.69 | 0.075221 | 0.144996 | Fixed 0.40 s serial delay; other overhead also affects observed e. |
| B: Lock contention | 2.943990 | 7.782049 | 8.478879 | 0.347 | 8.68 | 4.286736 | 3.506751 | One shared counter with per-increment locks; contention causes negative speedup. |
| C: Privatized state | 0.280510 | 0.163781 | 0.112838 | 2.486 | 62.15 | 0.167740 | 0.203016 | Private counters and one final reduction; process startup remains in elapsed time. |

A performs 16 chunks of `heavy_math(2_000_000)` plus the delay. B performs exactly 2,000,000 total increments. C performs exactly 20,000,000 total increments. These totals stay fixed as P changes. B and C have different default work sizes; their within-experiment speedups use their own one-worker baseline.

Metrics use `S(P)=T1/TP`, `E(P)=100*S(P)/P`, and `e(P)=(P*TP/T1-1)/(P-1)`. The P=1 Karp-Flatt value is undefined and is stored as null, not zero.

## Handout rubric assessed against the measured data

| Check | Actual observation | Numeric condition |
| --- | --- | --- |
| A: 0.80 <= e(4)/e(2) <= 1.25 | Ratio 1.927613 | Not met on this run |
| B: T4 > T1 and substantially increasing e | T4/T1=2.880; e(2)=4.286736, e(4)=3.506751 | Not met on this run for T4>T1 and increasing e; instructor interprets 'substantially' |
| C: T4 < T1 and E4 > 70% | T4<T1: True; E4=62.15% | Not met on this run |

Every numerical result and recomputed metric passes the separate local verifier. A missed performance condition remains reported as missed; the measurements were not changed to match the example table.

A's known serial pause is present in every timed run, but that does not make the entire implementation obey an ideal fixed-serial-fraction model: process startup, scheduling and mixed core speeds also contribute. B's slowdown directly shows that shared locking can defeat parallel execution. Its e values need not grow monotonically when elapsed-time growth saturates. C removes the shared hot-loop lock, but startup is a substantial cost for its short default run.

Karp-Flatt values summarize departure from ideal strong scaling. They alone cannot prove a specific cache-coherence protocol, bus bottleneck, or lock-wait mechanism; no hardware counters were collected.

## Supplemental C: startup amortization

This separately labelled diagnostic uses **200,000,000** total increments, ten times the required C workload. It retains fresh spawn pools and all startup/shutdown costs. It does not replace the 20,000,000-increment primary result or change the rubric verdict above.

| Total increments | T1 (s) | T2 (s) | T4 (s) | S4 | E4 (%) | e(2) | e(4) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 200000000 | 2.432229 | 1.250067 | 0.670182 | 3.629 | 90.73 | 0.027919 | 0.034056 |

Compare this efficiency with the default workload to inspect how additional independent work amortizes process overhead. All supplemental counter totals and metrics are independently checked too.

## Handout arithmetic notes

The example A timings (3.20, 1.80, 1.10 seconds) give e(2)=0.125 and e(4)=0.125. The example B timings (0.65, 1.10, 2.40 seconds) give e(2)=2.384615 and e(4)=4.589744. The inconsistent printed example e values were not copied into the measured table.

## Evidence and reproduction

- [Beginner instructions](PRACTICE_GUIDE.md)
- [Hardware profile](practice_results/host_profile.json) and [configuration](practice_results/configuration.json)
- [A raw samples](practice_results/experiment_a.json), [B raw samples](practice_results/experiment_b.json), [C raw samples](practice_results/experiment_c.json)
- [Independent local verification](practice_results/verification.json)

Run `python3 run_practice.py` from this directory for the default experiments. Use `python3 run_practice.py --supplemental-c` to also reproduce the additional 200-million-increment C diagnostic.

## Git provenance and instructor sign-off

The practice branch contains the handout's three requested checkpoint messages: `Part 1: Experiment A complete`, `Part 2: Captured lock contention pathology and Karp-Flatt surge`, and `Part 3 & 4: Completed privatization fix and verified RESULTS.md`. Existing main-branch lab history and milestone tags are retained.

**Instructor sign-off: pending.** This report and its local verification do not substitute for the in-person or remote Git sign-off requested by the handout. This work was prepared with AI assistance.
