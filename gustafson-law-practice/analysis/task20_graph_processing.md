# Task 20 — Graph processing

BFS and PageRank on power-law graphs combine irregular memory access, skewed degrees, changing frontiers, remote gathers/scatters, and synchronization. Proportional growth in vertices does not ensure balanced edge work; a few hubs can dominate the makespan. BFS has level barriers, while PageRank repeats sparse updates and often global convergence reductions. Dense linear algebra is more regular and easier to block and schedule. Graph weak scaling therefore requires balance, communication volume, and convergence measurements in addition to graph size.
