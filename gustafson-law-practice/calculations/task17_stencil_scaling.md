# Task 17 — 3-D stencil surface to volume

A cubic subdomain of side n has Θ(n³) updates and Θ(n²) halo elements, so surface/volume is Θ(1/n). Under weak scaling, fixed n per node means each node's ratio stays constant; adding nodes alone does not improve local communication fraction. Global dimension grows as `N=nP^(1/3)`. If instead one expands a single global cube, its ratio improves as 1/N, but that changes local work and is not the standard fixed-local-work weak scaling case.
