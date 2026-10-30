# Handout constraints and measurement limits

The assignment PDF is the source of the required experiment names, files, formulas, and milestone tags. The following points explain where this implementation or this host differs from its assumptions.

The course is **CSS314**, as confirmed by the student and the teacher's whiteboard. The supplied PDF uses the heading "CS482: Performance Evaluation & Optimization"; that heading is a discrepancy in the source document, not the course code for this repository.

## Authorship and verification

The handout states “No AI code generation” and “No peer collaboration,” and describes a solo, in-lab practicum. This repository was created with AI assistance. It does not comply with that authorship rule unless the instructor explicitly permits an exception. Running real experiments and producing correct results does not remove this restriction.

The supplied workspace contained the assignment PDF but no instructor-provided `verify_outputs.py`, reference digest specification, or signing key. The verifier in this repository is a local self-check. Its receipt documents its own checks and hashes; the `.sig` filename follows the requested file structure and does not make the receipt an authentic instructor signature or prove independent authorship. An official course verifier, if supplied later, remains authoritative.

Git history and milestone tags record actual repository operations. They do not independently prove solo work, attendance, an authorized examination session, or compliance with a 180-minute in-lab requirement. Timestamps must not be backdated to imply those conditions.

The user originally supplied `230103059` and explicitly confirmed removing its first digit. The identifier used by the exact salting algorithm is therefore `30103059`, giving `N = 1536`, `M = 768`, and seed `91405`. It was not silently shortened.

## Hardware observations

This host's operating system reports an Apple M4 with four performance cores and six efficiency cores, ten physical cores and ten logical threads, and a 128-byte cache line. The handout assumes 64-byte lines in several places. Double-precision values occupy eight bytes, so this host has sixteen such values per line. A stride-16 effect and continued sharing with 64-byte counter spacing are consistent with the observed hardware.

The counter benchmark records both the literal 64-byte spacing as `padded_64` and hardware-aware 128-byte spacing as `padded`. The latter isolates counters on distinct lines. Unpadded counters use eight-byte spacing. The shared counter hot loop has no global Python lock: such a lock would measure lock contention and obscure the intended experiment. Private counters publish their final value under a lock once per worker.

The operating system does not expose every requested field through the queries used here. Base frequency, a microarchitecture codename, and L3 capacity remain unknown rather than being invented. Unknown L3 capacity does not mean the chip has no further shared cache. Cache hit rates and hardware performance counters were not collected. Wall-clock timings cannot substitute for those counters.

The timer returns integer nanoseconds, but the recorded clock resolution is about 41.7 nanoseconds. The output unit does not establish one-nanosecond measurement accuracy. Workers are not pinned to particular cores; scheduling, different core types, event wakeup, synchronization, temperature, and background load can affect results. Raw repeats and timing boundaries are saved so their effects remain inspectable.

Python and NumPy manage the experiments. Locally compiled C loops called through `ctypes` perform strided reads, matrix multiplication, and counter increments. The C sources, compilation settings, and hashes are recorded. This is a disclosed native implementation rather than a claim that Python's interpreted increment loop directly measured cache-coherence cost. Matrix builds disable fast floating-point reassociation and fused contraction.

## Formula differences

**Fixed counter iterations per worker change total work.** With `K = 5,000,000`, the total is `P*K`, rather than a fixed `K` divided between workers. Standard Karp–Flatt analysis assumes fixed total work. Applying the requested `S = T1/TP` and `e = (1/S - 1/P)/(1 - 1/P)` literally to these growing counter runs does not estimate a strong-scaling serial fraction. Perfect weak scaling with `TP = T1` gives `e = 1`. The results retain the requested expression, label it accordingly, and also report throughput speedup `P*T1/TP`. Requested values are not forced to match the handout's expected trend.

**The printed weak-scaling expression differs from conventional scaled throughput.** Task 3.2 specifies:

```text
assignment_scaled_speedup = P * Work(1) * T1 / (Work(P) * TP)
```

When `Work(P) = P*Work(1)`, this equals `T1/TP`, a weak-scaling efficiency ratio. Conventional throughput speedup is:

```text
conventional_throughput_speedup = Work(P) / Work(1) * T1 / TP
```

Both are saved under distinct field names. Actual work counts use the number of updated interior cells multiplied by the step count, accounting for fixed boundaries and rounded grid dimensions. This avoids treating `ceil(N*sqrt(P))` as an exactly proportional workload.

Amdahl fits describe effective strong-scaling behavior, including communication and synchronization. The output preserves an unconstrained fit, a bounded summary, and fit residuals. A fitted asymptotic ceiling is a model prediction rather than a guarantee about additional physical cores. Gustafson's scaled-work interpretation does not require weak-scaling runtime to remain constant on this machine.

## Roofline limits

Apple documents 120 GB/s memory bandwidth for the M4 with a ten-core CPU and a four-performance/six-efficiency core split. This is a vendor specification, not bandwidth measured by these programs. The supporting primary source is [Apple's M4 MacBook Air technical specification](https://support.apple.com/en-au/122209). The local CPU query identifies the chip; this citation does not assert that a chassis model was independently authenticated.

An exact documented peak for this CPU's double-precision arithmetic is unavailable in this work. A roofline boundary needs both the compute peak and the memory bandwidth. Therefore the project cannot make a definitive compute-bound or memory-bandwidth-bound classification from the vendor bandwidth and low arithmetic intensity alone.

Each stencil update performs five floating-point operations. The optimistic streaming model assumes sixteen DRAM bytes per update; a write-allocation model assumes twenty-four. The separate 112-byte NumPy array-traffic estimate counts logical loads and stores across its arithmetic passes. It is not a measurement of 112 bytes transferred from DRAM: caches can serve many of those accesses. Working-set sizes, cache groups, barriers, and process overhead also matter. No cache miss rate, DRAM traffic count, or achieved fraction of the hardware peak is fabricated.
