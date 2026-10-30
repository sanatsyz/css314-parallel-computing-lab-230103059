# CSS314 practice lab: a beginner's guide

This is the **ungraded Karp–Flatt practice lab** in `Practice Lab Handout.pdf`. It asks you to measure why adding CPU workers sometimes helps and sometimes makes a program slower. The three experiments deliberately create different bottlenecks, then compare one, two and four worker processes.

The handout requests a **Git branch**, so this practice belongs in your existing CSS314 repository. A second repository is unnecessary. The practice branch is **`practice-230103059`**, using your full student ID. The earlier assignment used the shortened eight-digit ID `30103059` for its separate salted calculations; that does not change the ID for this new branch. Use the [practice branch on GitHub](https://github.com/sanatsyz/css314-parallel-computing-lab-230103059/tree/practice-230103059) for submission. The repository name ends in your full ID, using a hyphen because GitHub repository names cannot contain `=`.

## What the three experiments do

| Experiment | Required workload | What you are investigating |
|---|---|---|
| A: `exp_a_serial.py` | Pause for **0.40 seconds**, then compute **16 independent chunks**, each with `chunk_size=2_000_000` | A fixed part of the program must run sequentially, even when the remaining work uses more processes. |
| B: `exp_b_contention.py` | Perform **2,000,000 total increments** of one shared counter | Workers repeatedly wait for exclusive access to the same counter. More workers can create more coordination overhead. |
| C: `exp_c_fixed.py` | Perform **20,000,000 total increments** in private worker counters, then add the returned totals once | Each process can work independently, avoiding a shared lock on every increment. |

A uses the handout's exact scalar function:

```python
sum(math.sin(i) * math.cos(i) for i in range(1, n))
```

Its timer starts **before** the pause. The runtime also includes creating the process pool, dispatching the tasks, receiving the results and shutting the pool down. The pause cannot become faster by adding workers, so it limits the overall speedup.

B preserves the handout's synchronized `multiprocessing.Value` plus its explicit outer `Lock`. Accessing `counter.value` already uses the value's internal synchronization; the outer lock protects the whole read–increment–write operation. This repeated synchronization is part of the prescribed experiment. The final counter is checked against the requested total.

C keeps each counter private to its **process**. After its loop finishes, a worker returns its count. The parent adds those counts at the end and checks the total. There is no shared counter update inside the loop.

**B and C use different required totals: two million and twenty million.** Their absolute runtimes are therefore not a comparison of equal workloads. Use each experiment's own one-worker baseline to discuss scaling. A separately labelled longer C run, if present in the results, is an additional overhead diagnostic; it does not replace the required twenty-million-increment measurement.

## How to run it

The new practice scripts need **Python 3.8 or later and only the standard library**. They do not require a new `pip` dependency. Run them from the repository folder:

```sh
cd "/Users/sanatsyz/Desktop/assignment sufi"
python3 run_practice.py
```

That is the complete practice workflow. The individual stages can also be run in this order:

```sh
python3 practice_support.py
python3 exp_a_serial.py
python3 exp_b_contention.py
python3 exp_c_fixed.py
python3 practice_report.py
python3 practice_verify.py
```

To also reproduce the separately labelled 200-million-increment C diagnostic, run `python3 run_practice.py --supplemental-c`. Its output stays under `practice_results/supplemental_c_200m/`; the required C workload remains 20 million increments.

Each experiment defaults to **three full trials at each of 1, 2 and 4 workers**. Worker-count order rotates across trials. The reported runtime is the median, which is the middle value of the three measurements. Runs happen sequentially so the experiments do not compete with one another for the CPU.

The scripts explicitly use the `spawn` process-start method, which is the normal macOS default. Each timed run creates fresh processes or a fresh pool, including startup and shutdown in the runtime as the handout does. This makes the short C workload sensitive to process startup costs.

If you only want to check that the scripts work, their `--quick` option uses a small smoke workload. For example:

```sh
python3 exp_a_serial.py --quick --repeats 1
```

Smoke output goes under `practice_results/smoke/`, separate from the full measurements. Smoke runs are not evidence of full-workload scaling and must not replace the submission table.

## Where to look afterward

- **`RESULTS.md`** contains the real measured table, hardware profile, interpretation and checks against the instructor's rubric.
- **`practice_results/`** contains the new practice's machine profile, configuration, raw trial results and calculated summaries.
- **`results/`** belongs to the earlier assignment.
- **`practice_verify.py`** independently checks saved counts, runtimes and metric calculations. It reports the measured rubric outcome rather than treating an expected performance shape as a numerical correctness requirement.

The JSON files retain individual trials and returned values or counts. TSV summaries can be opened as tables. Keeping the raw trials makes the reported medians and formulas reviewable.

## Reading the numbers

`T1` is the runtime with one worker, and `Tp` is the runtime with `p` workers. For each experiment:

```text
Speedup Sp = T1 / Tp
Efficiency Ep = Sp / p
Karp–Flatt e(p) = ((p × Tp / T1) − 1) / (p − 1), for p ≥ 2
```

For efficiency as a percentage, multiply `Ep` by 100. A speedup of 2 means twice as fast as that experiment's one-worker run. A speedup below 1 means that adding workers made it slower. There is no Karp–Flatt value for one worker because the formula's denominator would be zero.

A roughly stable `e(p)` is consistent with a fixed serial component. An increasing value can indicate growing coordination costs. The metric measures an **effective overhead fraction**; it can exceed 1 when additional workers make a program slower. By itself it does not identify a physical cause such as cache-line traffic. Here the intentionally different programs help explain the observed behavior.

For illustration only, the handout gives A runtimes of 3.20, 1.80 and 1.10 seconds. Applying its formula gives **`e(2)=0.125` and `e(4)=0.125`**. Its printed `e(4)=0.120` is an arithmetic error. With the handout's B runtimes of 0.65, 1.10 and 2.40 seconds, the correct values are approximately **`e(2)=2.385` and `e(4)=4.590`**, rather than its printed 1.380 and 3.920. These are corrections to illustrative examples, not this computer's measurements.

## What the teacher wants you to explain

The final handout rubric asks for:

1. **A:** `e(4) / e(2)` between **0.80 and 1.25**, showing an approximately flat effective serial fraction.
2. **B:** `T4 > T1`, with `e(4)` much larger than `e(2)`, showing increasing contention overhead. The phrase “much larger” has no exact numerical threshold in the handout.
3. **C:** `T4 < T1` and four-worker efficiency **above 70%**, showing that privatization restores useful scaling.

These are empirical targets. The same source code can miss a target on a different machine because process startup, CPU scheduling, background work and the workload duration affect measured time. The fixed 0.40-second pause is also a different fraction of the total runtime on faster and slower CPUs. Correct counts and honest timings must be retained even when a performance expectation is missed. The report records what happened; it does not manufacture timings or silently change the required workload to obtain a desired result.

For a verbal explanation, you can say: “A keeps a sequential pause, B makes every worker compete for one locked counter, and C lets each worker count privately before combining the results.” Then use your own measured table in `RESULTS.md` to explain how each scaled.

The handout also requires an **in-person or remote instructor sign-off**. Running the scripts, checking the report and pushing Git commits do not complete that sign-off; it remains pending until the instructor verifies the work.

## AI assistance

AI assistance was used to implement, check and document this practice. You should understand the three programs and the formulas before presenting the results. The supplied practice handout identifies this as an ungraded exercise and does not state an AI-use rule; follow any additional course instructions the teacher gives you.
