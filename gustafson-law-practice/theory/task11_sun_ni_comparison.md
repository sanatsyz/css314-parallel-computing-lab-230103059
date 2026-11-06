# Task 11 — Gustafson and Sun–Ni

Amdahl fixes problem size; Gustafson fixes approximate runtime and expands parallel work; Sun–Ni memory-bounded speedup ties problem growth to usable aggregate memory. Their model generalizes fixed-size and fixed-time speedups, with the latter two appearing as special cases in simplified formulations. If memory per processor is constant and the data fit, aggregate memory grows with P and can support expanded workloads.

Gustafson may overestimate throughput when memory capacity does not grow, the working set exceeds memory, communication/imbalance rises, or bandwidth is saturated. It may underestimate throughput when added memory permits a larger-than-linear useful workload at a fixed time. The applicable model depends on both compute and memory constraints.

Sun & Ni, “Scalable Problems and Memory-Bounded Speedup,” JPDC 19 (1993), 27–37, [paper and publication details](https://grc.iit.edu/gnosis/publications/sun-1993-scalable-problems-ec6f/).
