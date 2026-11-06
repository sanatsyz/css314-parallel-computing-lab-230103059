# Task 08 — Amdahl versus Gustafson

For s=α=0.08, P=128:

- Amdahl: `1/[0.08+0.92/128]=1/0.0871875=11.469534`.
- Gustafson: `128−0.08×127=117.84`.
- Difference relative to Amdahl: `(117.84−11.469534)/11.469534×100 = 927.1%`. Gustafson predicts 10.27 times the Amdahl speedup.

They diverge because Amdahl fixes total work and Gustafson expands parallel work at approximately fixed elapsed time.
