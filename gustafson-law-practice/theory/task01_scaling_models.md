# Task 01 — Strong scaling and weak scaling

Amdahl's 1967 model holds total work fixed. With serial fraction s, normalized runtime on P processors is `s+(1−s)/P`, speedup is `1/[s+(1−s)/P]`, and as P→∞ the fixed problem dimension remains unchanged (for a grid, side length N remains fixed). Work per processor shrinks toward zero. This is fixed-size or strong scaling.

Gustafson's 1988 model holds elapsed parallel time approximately fixed while expanding useful parallel work as processors are added. If the observed run has serial fraction α and parallel fraction 1−α, the equivalent one-processor workload is `α+P(1−α)`. Total work grows with P. For a d-dimensional grid, total unknown count may grow as P and side length as `P^(1/d)`, while each worker's local subdomain remains roughly fixed. This is fixed-time or weak scaling, assuming adequate memory and no increasing overhead.

The philosophical and physical distinction is the workload family: Amdahl divides one fixed job among more processors; Gustafson uses more processors to solve a proportionally larger job in similar time. Their formulas answer different questions, so neither invalidates the other.
