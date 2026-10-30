# CSS314 Variant B: granularity and IPC results

Student ID: **230103059**. Branch: **variant-b-230103059** in the existing course repository.
The supplied PDF is preserved unchanged under its original CS482 filename; the student's course label is CSS314.

## Hardware and method

| Item | Recorded value |
| --- | --- |
| CPU | Apple M4 |
| Physical cores / logical threads | 10 / 10 |
| Core groups | 4 performance cores; 6 efficiency cores |
| Architecture / OS | arm64 / Darwin 27.0.0 |
| Python | CPython 3.14.3 |
| os.cpu_count / multiprocessing.cpu_count | 10 / 10 |
| Process start method | spawn |
| Timer | mach_absolute_time(); resolution 4.17e-08 seconds |
| Repetitions | Three full trials at each P=1,2,4,8; median runtime |

Workers were not pinned; the operating system scheduled them. Available affinity information is recorded in the hardware JSON. Experiments ran sequentially, with worker-count order rotated across repetitions. Background desktop activity, scheduling, core type, frequency and thermal state can affect times.

A times fresh Pool creation, map and teardown; its final checksum reduction is outside the timer, matching the handout. B/C create the Queue and Process objects before timing, then time process startup, queue consumption, and joins. Monitor setup/teardown and queue cleanup are outside the interval. A low-frequency exit monitor remains active during B/C; B additionally accumulates a checksum in the timed receive loop. These safety checks add some parent/background overhead. No startup time was subtracted.

## Full default-workload matrix

| Configuration | T1 (s) | T2 (s) | T4 (s) | T8 (s) | S8 | E8 (%) | e(2) | e(4) | e(8) | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| A: Micro (k=1) | 13.962333 | 10.990058 | 13.521676 | 13.992705 | 0.998 | 12.47 | 0.574244 | 0.957919 | 1.002486 | Fine tasks slower at every P; compare with coarse tasks |
| A: Coarse (k=10000) | 5.522514 | 2.834427 | 1.569854 | 1.104414 | 5.000 | 62.51 | 0.026499 | 0.045686 | 0.085696 | Same computation, fewer dispatch envelopes |
| B: Queue choke | 1.790803 | 2.877787 | 2.938622 | 3.137713 | 0.571 | 7.13 | 2.213962 | 1.854602 | 1.859572 | Negative scaling at P=8 |
| C: Buffered batch | 0.341084 | 0.200141 | 0.130725 | 0.140127 | 2.434 | 30.43 | 0.173556 | 0.177684 | 0.326662 | Final numeric criteria: Not met on this run |

A processes range(1,1_000_000+1) with the handout's naive Collatz loop. Both A cases produce checksum **131434424** in every trial. Micro uses 1,000,000 task envelopes; coarse uses 100 envelopes of 10,000 inputs. No memoization enters the timed workload.

B processes exactly 400,000 items and C exactly 10,000,000, with C batch size 10,000. Every worker starts its local sequence at i=0. Work partitioning includes remainders, and all queue checksums, message/batch counts, sentinels and zero worker exit codes are checked. C sends 1,000 data batches at these defaults, plus P completion sentinels, instead of one data message per input.

Metrics: `S(P)=T1/TP`, `E(P)=100*S(P)/P`, `e(P)=(P*TP/T1-1)/(P-1)`. Each configuration uses its own one-worker median. The P=1 Karp-Flatt value is undefined (JSON null, empty TSV cell). Raw trials retain more precision than this table.

## Granularity comparison

| P | Micro / coarse runtime | Coarse S(P) | Coarse E(P) (%) |
| ---: | ---: | ---: | ---: |
| 1 | 2.528x | 1.000 | 100.00 |
| 2 | 3.877x | 1.948 | 97.42 |
| 4 | 8.613x | 3.518 | 87.95 |
| 8 | 12.670x | 5.000 | 62.51 |

The fine/coarse comparison changes dispatch granularity while keeping the input range and scalar work identical. A larger runtime for micro-tasks is consistent with dispatch and result-handling overhead overwhelming useful computation. Timing alone does not directly measure master starvation or isolate each part of that overhead.

## Buffering throughput comparison

| P | B items/s | C items/s | C / B throughput gain | C runtime below B? |
| ---: | ---: | ---: | ---: | --- |
| 1 | 223363 | 29318288 | 131.258x | True |
| 2 | 138996 | 49964889 | 359.471x | True |
| 4 | 136118 | 76496487 | 561.986x | True |
| 8 | 127481 | 71363643 | 559.797x | True |

C processes 25 times as many items as B. Throughput normalizes that difference: `(10,000,000/TC)/(400,000/TB)`. This cross-configuration improvement is distinct from C's within-configuration strong-scaling speedup, `TC1/TC8`.

## Measured handout criteria

| Check | Actual observation | Condition |
| --- | --- | --- |
| A: micro slower than coarse at each P | See ratios above | Met |
| B: T8 > T1 | T8/T1=1.752 | Met |
| B: monotonically increasing runtime | 1.790803, 2.877787, 2.938622, 3.137713 seconds | Met |
| B: increasing e across 2,4,8 | 2.213962, 1.854602, 1.859572 | Not met on this run |
| C: throughput gain at P=8 >10x | 559.797x | Met |
| C: S8 >5 | 2.434100 | Not met on this run |
| C: final e(8) <=0.05 | 0.326662 | Not met on this run |
| C: task text e(8) <0.04 | 0.326662 | Not met on this run |

Independent numerical/schema verification passes. The empirical conditions are reported separately; a missed condition stays missed. The programs retain the exact default workloads rather than editing times or changing the workload to satisfy an expected trend.

Shared-queue negative scaling is consistent with communication and synchronization overhead. A Karp-Flatt trajectory alone cannot prove bus thrashing, cache-coherence storms, or lock-wait time; no hardware performance counters were collected. Buffering reduces message frequency, but fresh process startup and scheduling across mixed core types remain part of elapsed time and can limit short-run S8.

## Handout inconsistencies

The illustrative A coarse times (4.80,2.50,1.35,0.75 seconds) give e(2)=0.041667 and e(8)=0.035714, rather than printed e(8)=0.038. The illustrative B times (1.20,1.95,3.80,7.60) give e(2)=2.250000 and e(8)=7.095238, rather than 1.250 and 6.280. These examples were not copied into the measured matrix.

C's task text asks for e<0.04; the final sign-off uses e(8)<=0.05 and the synthesis table uses e(2),e(8)<0.05. The underlying e values are supplied above and the local receipt retains these separate observations. Page 1's final task line is clipped in the supplied PDF. The visible experiment parameters and final requirements are preserved.

## Evidence, reproduction and Git submission

- [Beginner explanation and commands](VARIANT_B_GUIDE.md)
- [Host profile](variant_b_results/host_profile.json) and [configuration](variant_b_results/configuration.json)
- [A micro](variant_b_results/a_micro.json), [A coarse](variant_b_results/a_coarse.json), [B queue](variant_b_results/b_queue.json), [C buffered](variant_b_results/c_buffered.json): full raw trials and adjacent TSV summaries
- [Independent unsigned local verification](variant_b_results/verification.json)

Run `python3 run_variant_b.py` to reproduce all default cases sequentially and refresh this report. This can take several minutes. Small `--quick` runs are kept under a separate smoke directory and cannot pass full-workload verification.

The branch uses `Part 1: Completed task granularity comparison`, the handout's `Part 2: Reproduced IPC queue contention and recorded e(p) explosion`, and `Part 3 & 4: Completed buffer optimization and verified RESULTS_B.md` checkpoint messages. The requested 'explosion' message is a provenance label; the measured e curve above determines whether that trend occurred.

**Instructor sign-off: pending.** An in-person or remote Git review must be performed by the instructor. This work was prepared with AI assistance. Source and data hashes in the local receipt record the delivered files; they are not an instructor signature or independent proof of timing capture.
