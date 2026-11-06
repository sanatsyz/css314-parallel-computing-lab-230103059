# Task 04 — Asymptotic efficiency

For constant α, `S_G=P−α(P−1)` and `E_G=S_G/P=1−α+α/P`. Since α/P→0, `lim(P→∞) E_G=1−α`.

Amdahl speedup is `S_A=1/[s+(1−s)/P]`, so efficiency is `E_A=1/[Ps+(1−s)]`. For fixed s>0 the denominator diverges and the limit is 0. For s=0 it is 1. The distinct limits follow from workload assumptions: weak scaling adds work with processors, while strong scaling divides fixed work ever more finely.
