# Task 23 — Measurement protocol

The requested 25 measurements were collected with five runs at each process count (1, 2, 4, 6, 10) using 100,000 kernel iterations per process. Raw observations are in `benchmarks/results_raw.csv`; `benchmarks/results.csv` contains mean, sample standard deviation, standard error, and derived speedup. Speedup is estimated as `P × mean(T₁)/T_P`, with the single-process mean as baseline. OLS fits `P−S=α(P−1)` through the P=1 anchor. Process startup is included, and the fitted α should be treated only as an effective value for this benchmark and machine.
