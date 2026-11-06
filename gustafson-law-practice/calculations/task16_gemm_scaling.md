# Task 16 — GEMM scaling

Total arithmetic work is Θ(N³). If processor count scales with work to maintain constant work per processor and time, `N³∝P`, so `N∝P^(1/3)`. Matrix storage is Θ(N²) and therefore grows as P^(2/3) globally.

| P | N/N₁ | Operations ratio | Storage ratio |
|---:|---:|---:|---:|
| 8 | 2 | 8 | 4 |
| 64 | 4 | 64 | 16 |
| 512 | 8 | 512 | 64 |
| 4096 | 16 | 4096 | 256 |

Communication lower bounds and data distribution may prevent this ideal compute scaling.
