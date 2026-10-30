# Understanding and running the lab

This lab asks why using more CPU cores does not always make a program faster. It measures three things: how memory access order changes speed, how workers interfere when they write nearby memory, and how much a real calculation benefits from additional workers. The numbers come from this computer's runs, so they will change when the programs run again.

The student identifier used here is `30103059`. The original identifier was `230103059`; the user explicitly confirmed removing its first digit to obtain the eight digits required by the handout. The specified SHA-256 rule gives `N = 1536`, matrix sub-block size `M = 768`, and random seed `91405`. The seed makes the numerical inputs repeatable; it cannot make operating-system timing repeatable.

This work was created with AI assistance. The handout prohibits AI code generation and requires solo work. Read [HANDOUT_NOTES.md](HANDOUT_NOTES.md) before treating this repository as a course submission.

## Run the programs

Use a terminal in the repository directory. Python 3.10 or later, NumPy, and a C compiler are needed. On macOS, the compiler normally comes with Apple's Command Line Tools. The `.venv` directory keeps this project's Python packages together.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

The full sequence is below. Run one command at a time and wait for it to finish. Simultaneous benchmarks compete for the same CPU and memory and make the results harder to interpret.

```bash
.venv/bin/python src/profile_env.py --student-id 30103059
.venv/bin/python src/stride_bench.py
.venv/bin/python src/dense_kernel.py
.venv/bin/python src/false_sharing.py
.venv/bin/python src/scaling_study.py
.venv/bin/python verify_outputs.py
```

These commands replace the relevant files under `results/`. After rerunning an experiment, rerun verification so its receipt describes the current outputs. A verification receipt reports local consistency checks; it does not certify compliance with the course's rules.

After setup, `.venv/bin/python run_lab.py` runs the same full sequence for this identifier. It does not change the existing milestone tags.

To run the small correctness tests separately from performance measurements:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests -q
```

Tests use small arrays and short loops to catch incorrect answers. They do not replace the full assignment experiments. The benchmark scripts also have `--quick` modes for smoke checks; those reduced workloads are not the final measured submission.

## What each experiment does

**Milestone 0 records the machine and selects the inputs.** `profile_env.py` asks the operating system about the CPU, caches, Python, and clock. This machine reports an Apple M4 with ten physical cores and ten logical threads: four performance cores and six efficiency cores. The two core types have different cache sizes, which are listed separately in `host_profile.json`. An unavailable value is recorded as `null`.

**Milestone 1 first reads memory with different gaps.** A cache is a small, fast store close to the CPU. When the CPU fetches data, it moves a block called a cache line. This M4 reports 128-byte lines. Each double-precision number occupies eight bytes, so a line holds sixteen numbers. The handout's 64-byte example holds eight numbers and does not describe this machine's line size.

`stride_bench.py` allocates 16,777,216 numbers, or 128 MiB. With stride 1, it reads every number in order. With stride 16, it reads one number out of each sixteen. The latter pattern uses less of each fetched line. The program records five warmups and five measured runs for each stride, then reports median time divided by the number of elements actually read. These are wall-clock nanoseconds per element, rather than direct measurements of individual cache misses.

The same milestone multiplies two matrices using two loop orders. A matrix is stored row by row. The `i-j-k` order repeatedly jumps between rows of the second matrix. The `i-k-j` order walks along its rows and reuses one value from the first matrix. Both compute the same answer. The reported speedup is `time_ijk / time_ikj`; a value greater than one means the interchanged version was faster. The full run uses the specified 768-by-768 sub-block and records three trials per order.

**Milestone 2 makes workers write to nearby counters.** Each worker has its own counter and performs 5,000,000 increments. Even though the counters are different, several can occupy the same cache line. Different cores then need to exchange ownership of that line to write their counters. This effect is called false sharing.

The program compares four arrangements on this host:

| Variant | Counter arrangement |
| --- | --- |
| `unpadded` | Counters are eight bytes apart and share a line. |
| `padded` | Counters are 128 bytes apart, matching the detected hardware line. |
| `padded_64` | Counters are 64 bytes apart, preserving the handout's example; neighboring pairs still share a 128-byte line. |
| `privatized` | Each worker counts in its own private memory and publishes once at the end. |

Every run checks that each counter equals 5,000,000. Adding workers also adds work: eight workers perform 40,000,000 increments altogether. This matters when interpreting the speedup formulas below. The operating system chooses where processes run, and the M4's two core types can affect timings.

**Milestone 3 updates a grid repeatedly.** Each interior cell becomes the average of itself and its four immediate neighbors. The outside edge stays zero. Workers update separate row ranges, then wait for each other before starting the next step. Without that wait, some workers could use old neighboring values while others use new ones.

Strong scaling keeps the grid at 1536 by 1536 while changing the worker count. Weak scaling increases the grid dimension to `ceil(1536 * sqrt(P))`, so there is roughly the same amount of work per worker. The full study includes 1, 2, 4, 8, and 10 workers. It saves both the numerical output and timings, and compares every output with a serial reference.

Python controls allocation, worker processes, timing, output files, and verification. The stride, matrix multiplication, and counter hot loops use the readable C sources in `src/native/`, compiled locally and called through Python's standard-library `ctypes` module. This prevents interpreter overhead from hiding the memory effects. The stencil uses NumPy operations in Python worker processes. Compiler details and source hashes are recorded with the measurements.

## Reading the formulas

Let `P` mean the number of workers, `T1` the one-worker time, and `TP` the time with `P` workers.

For a fixed amount of work, speedup is `S = T1 / TP`, and efficiency is `100 * S / P` percent. For example, using more workers without reducing elapsed time increases neither fixed-work speedup nor efficiency.

Amdahl's law models fixed-work speedup as `S = 1 / (s + (1-s)/P)`. The fitted `s` summarizes the part that does not shrink with additional workers, including synchronization costs. Its ideal model ceiling is `1/s` when `s > 0`. A poor fit or a fitted value outside zero to one warns that this simple model does not describe the measurements well.

The handout requests the Karp–Flatt expression `e = (1/S - 1/P) / (1 - 1/P)` for counter runs. It normally describes fixed work, but these runs give each worker a full counter workload. The repository therefore labels the requested value and separately reports counter throughput speedup `P * T1 / TP`. If elapsed time stayed constant as counter workers were added, that would be ideal weak scaling, and the requested `e` would be one rather than zero.

For the grid, let `W1` and `WP` mean the actual numbers of interior cell updates. Conventional throughput speedup is `(WP/W1) * (T1/TP)`, with efficiency `100 * throughput_speedup / P`. Task 3.2 instead prints `(P * W1 * T1) / (WP * TP)`. Both quantities appear under distinct names in the results. See [HANDOUT_NOTES.md](HANDOUT_NOTES.md) for the difference. Gustafson's law, `S_scaled = P - alpha*(P-1)`, describes why increasing the workload can make parallel execution more useful; its serial fraction `alpha` is defined for the scaled run.

The roofline calculation asks how much arithmetic is done for each byte moved. One stencil update performs four additions and one multiplication. Under an optimistic memory model, it moves sixteen bytes, giving `5/16 = 0.3125` floating-point operations per byte. Actual NumPy operations can move more data, and some accesses can be served from cache. The JSON file records these assumptions. Low arithmetic intensity suggests sensitivity to memory traffic; it alone does not establish a definitive memory-bound or compute-bound classification.

## Find the evidence

| File | What to look for |
| --- | --- |
| `results/host_profile.json` | Observed hardware, cache sizes, timer details, and unavailable fields. |
| `results/salted_params.json` | Confirmed identifier, dimension, buffer size, and seed. |
| `results/stride_results.tsv` | Median time per element at each stride. |
| `results/stride_raw.json` | All stride warmup and measured timings. |
| `results/loop_interchange.json` | Three timings per matrix loop order, speedup, and numerical errors. |
| `results/false_sharing_karp_flatt.tsv` | Median counter timings, requested metric, and throughput. |
| `results/false_sharing_raw.json` | Per-trial counts, worker timestamps, layout, and compiler details. |
| `results/scaling_metrics.tsv` | Strong and weak speedups, efficiency, and work sizes. |
| `results/scaling_raw.json` | Individual scaling trials and model fit details. |
| `results/roofline_summary.json` | Arithmetic counts, traffic assumptions, cache context, and classification limits. |
| `results/arrays/` | Numerical matrices and stencil outputs, including lossless split files with manifests. |
| `results/verification_receipt.sig` | Locally generated verification receipt; no instructor signature. |

The `.tsv` files are plain-text tables that a spreadsheet application can open. JSON files contain named fields and lists. A `.npy` file stores a NumPy array; the stencil's `.npz` parts store complete row sections, and their manifest records how to reconstruct the full array.
