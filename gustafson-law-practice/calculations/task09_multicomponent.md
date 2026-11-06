# Task 09 — Multi-component workload

Assume I/O/broadcast 2% and boundary synchronization 6% are serial/nonparallel: aggregate α=0.08; flux computation is 92% parallel.

| P | S=P−0.08(P−1) | E=S/P |
|---:|---:|---:|
| 512 | 471.12 | 92.015625% |
| 2,048 | 1,884.24 | 92.003906% |

The result assumes phase shares remain constant as P grows.
