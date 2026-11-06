# Task 10 — Memory capacity and grid dimension

Assume decimal GB, one 8-byte scalar per grid cell, and no solver overhead. Capacity for n nodes is `32×10⁹n` bytes and `8N³≤32×10⁹n`; hence `N_max=floor[(32×10⁹n/8)^(1/3)]`.

| Nodes | Aggregate memory | Ideal one-field N_max |
|---:|---:|---:|
| 64 | 2,048 GB | 6,349 |
| 512 | 16,384 GB | 12,699 |

The second dimension doubles because capacity increases eightfold. Multiple fields, halos, metadata, and reserved memory reduce these ceilings. With q fields, use 8q bytes per cell. (Earlier draft's 32 GB × 64/512 arithmetic is corrected here.)
