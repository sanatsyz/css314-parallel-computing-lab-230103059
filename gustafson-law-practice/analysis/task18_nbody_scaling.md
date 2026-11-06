# Task 18 — N-body algorithm scaling

Direct all-pairs is Θ(N²); keeping ideal work per processor constant requires N²∝P, or N∝√P. Barnes–Hut is approximately Θ(N log N); requiring N log N∝P gives `N≈P/W(P)` (Lambert W, constants omitted). Direct interactions can incur global communication; tree codes add irregular tree construction and traversal traffic. Complexity alone does not determine α: partitioning, setup, and communication measurements are needed to assess serial/parallel ratio.
