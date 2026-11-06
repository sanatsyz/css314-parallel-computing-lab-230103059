# Task 13 — Two failures of weak scaling

**Global reduction in an iterative solver.** Fixed local arithmetic combined with an all-reduce for convergence does not retain fixed runtime: a tree needs O(log P) stages, with latency and contention. The communication fraction rises as local work remains fixed. Pipelining or communication-avoiding methods can help but alter implementation and possibly numerical behavior.

**BFS on a power-law graph.** Growing vertices and edges proportionally to P does not ensure balanced frontiers. Hubs cause skewed adjacency scans, remote messages, and barriers; runtime is set by the slowest partition. Replication and partitioning trade memory and redundant work for lower imbalance. The fixed-per-worker average workload assumption therefore fails. These are failures of the premise, not of the conditional Gustafson algebra.
