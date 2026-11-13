"""Assemble lab_report_<ID>.md from results.log + your Phase 0 notes + all scripts.
Usage: python3 make_report.py <YourID>"""
import re, sys, pathlib

sid = sys.argv[1] if len(sys.argv) > 1 else "ID"
log = pathlib.Path("results.log").read_text() if pathlib.Path("results.log").exists() else "(run the tasks first)"
tags = "\n".join(re.findall(r"^VERIFY_HASH\[PHASE\d\].*$", log, re.M))
scripts = ["harness.py", "task0_cal.py", "task1_falsesharing.py", "task2_scaling.py",
           "task3_roofline_gemm.py", "task4_scheduling.py"]
code = "\n\n".join(f"### {s}\n```python\n{pathlib.Path(s).read_text()}\n```" for s in scripts)

md = f"""# Lab Report - {sid}

## 1. Phase 0 hardware table (FILL IN from your terminal output)
| Item | Value |
|---|---|
| CPU model | |
| Physical cores (Pphys) | |
| Logical threads (Plog) | |
| Cache line (bytes) | |
| L1d / L2 / L3 | |

### Verbatim VERIFY_HASH lines
```
{tags}
```

## 2. Measured results (raw output of all tasks)
```
{log}
```

## 3. Diagnostic answers (edit using YOUR numbers above)
**Phase 1.** Contention should vanish once adjacent slots are >= one cache line apart
(stride 8 = 64 B on most laptops; 128 B on Apple Silicon, so look at stride 16). With stride=1
all workers write the same line, so coherence invalidations serialise them: Sp stays near 1 and
Karp-Flatt e(p) is large and *grows* with p (overhead, not a fixed serial part). With stride=16
the lines are private: Sp ~ p and e(p) is small and roughly flat.

**Phase 2.** Strong scaling is capped by Amdahl at 1/s (s = Stage A share of T1); report observed
S(Plog) vs. that cap. Weak scaling: Stage A grows with N(p) (it is 5% of N), so alpha rises and
Gustafson speedup falls below p. Past Pphys the marginal gain drops sharply because SMT siblings
(or E-cores) share execution units/caches.

**Phase 3.** Compare V1 -> V2 -> V3 GFLOP/s: V2 gets unit-stride B access; V3 helps if
3*BS^2*8 B fits in L1d/L2 (BS* usually 32-64 for a 32-48 KiB L1d). Note: pure Python is
interpreter-bound, so all points sit far below the roofline ceiling and gains from blocking are
small - say so honestly and point to P_sustained / BW*I as the hardware limit.

**Phase 4.** Block static suffers high lambda (the last block holds the heaviest items, K grows
quadratically). Cyclic static is far better. Dynamic with C=1 pays lock contention per item;
C=512 leaves a tail where one worker holds the last big chunk. C* is the mid-range minimum of Twall.

## 4. Scripts
{code}
"""
out = f"lab_report_{sid}.md"
pathlib.Path(out).write_text(md)
print("wrote", out)
