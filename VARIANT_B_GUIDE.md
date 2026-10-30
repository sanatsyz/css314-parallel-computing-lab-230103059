# CSS314 Variant B: what this task means

This is the new ungraded practice about **task size and communication between processes**. It is separate from the earlier Karp-Flatt practice. Your course is CSS314; the teacher's uploaded PDF has CS482 in its filename, which is preserved unchanged as the source document.

The handout asks for the branch **`variant-b-230103059`**. It is in your [existing course repository](https://github.com/sanatsyz/css314-parallel-computing-lab-230103059/tree/variant-b-230103059), and includes the earlier work in its history. Your earlier `main` and `practice-230103059` branches remain available. A new repository is unnecessary.

The teacher's message supplies the account name `sufyanism`, with profiles on [GitHub](https://github.com/sufyanism) and [GitLab](https://gitlab.com/sufyanism). It does not identify a particular assignment repository. The supplied PDF's repository URL is a placeholder, so this submission uses the student's existing repository as requested.

## The experiments

| Script | What it does | Required workload |
| --- | --- | --- |
| `exp_a_granularity.py` | Calculates Collatz sequence lengths. Compares sending one number per task with sending 10,000 numbers per task. | The same 1,000,000 numbers for each configuration |
| `exp_b_queue.py` | Each worker sends every individual result to the parent through one shared queue. | 400,000 items in total |
| `exp_c_buffered.py` | Each worker buffers 10,000 values, then sends their sum as one queue message. | 10,000,000 items in total |

All four cases (A micro, A coarse, B, C) run at **1, 2, 4 and 8 worker processes**, with three full measurements at each count. Work stays fixed within each case. Only its distribution changes when workers are added. The median, or middle runtime, is reported.

For Collatz, an even number is divided by two and an odd number becomes `3*n+1`, until it reaches one. Each input has a sequence length. Both A configurations calculate exactly the same lengths; only the number of inputs packaged into one pool task changes. The timed implementation uses the teacher's scalar loop. A separate untimed memoized oracle checks the checksum.

B sends each `i % 7` value individually. C accumulates a local list and sends its sum every 10,000 values, plus a final partial batch if needed. Each C worker then sends `None` to say it has finished. The parent drains messages while the workers run and joins them afterward. Python documents queue serialization, background feeder threads, and the need to consume queued data before joining producers in its [multiprocessing reference](https://docs.python.org/3.14/library/multiprocessing.html#pipes-and-queues).

The sequence index starts at zero inside **each** worker, matching the supplied code. This means the expected sum can differ slightly with the number of workers. Validation calculates the exact expected sum for each worker's assigned length. Division remainders are preserved so custom uneven totals do not lose records or leave the parent waiting forever.

## How to run it

The new scripts use Python 3.8 or newer and the standard library. No package installation is needed for Variant B itself. From the repository directory:

```sh
cd "/Users/sanatsyz/Desktop/assignment sufi"
python3 run_variant_b.py
```

The micro-task case sends one million tasks per trial and can take several minutes across all trials. The workflow runs experiments sequentially; avoid running another benchmark at the same time. It refreshes only `variant_b_results/` and `RESULTS_B.md`.

Individual stages are:

```sh
python3 variant_b_support.py
python3 exp_a_granularity.py
python3 exp_b_queue.py
python3 exp_c_buffered.py
python3 variant_b_report.py
python3 verify_variant_b.py
```

To check code quickly without replacing the submitted measurements:

```sh
python3 exp_a_granularity.py --quick --repeats 1
python3 exp_b_queue.py --quick --repeats 1
python3 exp_c_buffered.py --quick --repeats 1
```

Small checks go into `variant_b_results/smoke/`. The verifier rejects small workloads in the primary results. To check the saved primary data without changing its receipt, run `python3 verify_variant_b.py --no-receipt`.

## How to read the report

Start with **[RESULTS_B.md](RESULTS_B.md)**. It contains the real times, all three requested metrics, the interpretation, and the measured status of each target.

`T1` is the runtime using one worker. `Tp` is the runtime using `p` workers. Each case uses its own one-worker baseline:

```text
Speedup S(p) = T1 / Tp
Efficiency E(p) = 100 * S(p) / p
Karp-Flatt e(p) = (p * Tp / T1 - 1) / (p - 1), for p > 1
```

Speedup below one means that extra workers made that case slower. Karp-Flatt is undefined at one worker. It summarizes overhead relative to ideal scaling, and can exceed one. It does not directly measure cache traffic, bus saturation, or time waiting for a lock.

B and C have **different total item counts**: C processes 25 times as many items. Compare their throughput, `items / seconds`, to discuss improvement between them. Comparing their own speedups answers a different question: how much adding workers helps each implementation.

The handout's expected numbers and speedup targets are hypotheses to test on this machine. They are not numbers to copy into your results. Startup, process scheduling, CPU core types and workload duration affect the outcome. The report retains missed targets instead of changing timings or the required workload.

The sample arithmetic also needs correction. A's illustrative times `(4.80, 2.50, 1.35, 0.75)` give `e(2)=0.041667` and `e(8)=0.035714`. B's illustrative times `(1.20, 1.95, 3.80, 7.60)` give `e(2)=2.250000` and `e(8)=7.095238`. These are illustrative examples only. C's task text asks for `e<0.04`, while the final sign-off criteria use `e(8)<=0.05`; the report shows both checks separately.

## What is saved and checked

`variant_b_results/` contains the hardware profile, full workload configuration, every timed trial, TSV summaries, and `verification.json`. `verify_variant_b.py` independently checks exact workloads, result counts and sums, the saved JSON/TSV metrics, and the measured target conditions. It records file hashes in an unsigned local receipt. It cannot certify that an instructor reviewed the work.

Normal queue consumption uses blocking `get()` calls. A low-frequency monitor detects failed or prematurely finished producers so a broken run does not silently wait forever. It starts outside the measurement; its occasional checks can still add a small amount of background overhead. B also adds a checksum in the timed parent receive loop, so numerical results can be checked as well as message counts. C uses the handout's sum reduction in that loop. Queue and monitor cleanup occur after the timer.

Your teacher still needs to perform the handout's **in-person or remote sign-off**. AI assistance was used to implement, test, measure and document this work. Before showing it, understand this explanation: “A changes how much computation is in each task. B sends too many individual messages. C sends sums of batches to reduce communication.” Then use the actual report to explain how each behaved on your Mac.
