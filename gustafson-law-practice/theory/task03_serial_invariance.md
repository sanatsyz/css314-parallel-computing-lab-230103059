# Task 03 — Serial fraction and reference frame

Amdahl's serial fraction is measured for a fixed workload on one processor. The fixed-work speedup is `1/[s+(1−s)/P]`, which tends to `1/s`; therefore the serial path caps strong scaling.

Gustafson's α is the serial share observed in the parallel execution of the scaled workload. Normalize this run to one time unit: serial time α, parallel time 1−α. The equivalent serial time for the same expanded work is `α+P(1−α)`, hence `S=P−α(P−1)`. This avoids the apparent paradox because the comparison includes a larger workload in the numerator; it does not remove serial overhead. Constant α yields asymptotic efficiency 1−α. If α grows with P, efficiency can fall. Always state which problem and machine define the fraction.
