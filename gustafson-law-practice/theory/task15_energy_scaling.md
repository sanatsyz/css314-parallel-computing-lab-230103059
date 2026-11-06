# Task 15 — Energy and weak scaling

For P nodes running for wall time T with per-node idle power P_idle and active power P_active, approximate energy is `E_P=P(P_idle+P_active)T`; one node for the same time uses `E_1=(P_idle+P_active)T`. Thus `E_P/E_1=P`. The P-node run also completes roughly P times the expanded work, so this is equal-time throughput comparison, not equal-work energy efficiency.

A better accounting is `E=P P_idle T + Σ∫P_dyn,i(t)dt + E_network + E_memory`. DVFS, utilization, sleep states and network power affect measurements. Gustafson's performance formula alone cannot predict energy.
