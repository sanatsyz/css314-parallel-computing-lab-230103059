# Task 05 — Historical nCUBE/10 result

Gustafson, Montry, and Benner's 1988 paper studied wave mechanics, fluid dynamics, and structural analysis on a 1,024-processor MIMD hypercube. It reported fixed-size speedups of 502–637 and scaled speedups of 1,009–1,020 when work per processor was held fixed. The greater-than-1,000 figure is scaled speedup, not a breach of the P bound for fixed work. The measurements remain below 1,024, as expected.

From `α=(P−S)/(P−1)`, those scaled results imply effective α values about 1.47% at S=1009 and 0.39% at S=1020. Expanding problem size kept substantial useful work on each processor and exposed throughput; implementation work reduced non-overlapped communication, message startup, dependencies, and imbalance. This does not mean every application will scale similarly.

Primary source: Gustafson, Montry & Benner, “Development of Parallel Methods for a 1024-Processor Hypercube,” SIAM J. Sci. Stat. Comput. 9(4), 609–638 (1988), [paper PDF](https://rsim.cs.illinois.edu/arch/qual_papers/systems/6.pdf).
