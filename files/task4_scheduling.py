"""Phase 4: skewed triangular workload - static block/cyclic vs dynamic chunk queue."""
import math
import time
import multiprocessing as mp
from harness import *

sin, cos, sqrt = math.sin, math.cos, math.sqrt
N = max(40, int(8000 * SCALE))


def item(i):
    x = 0.0
    for _ in range(1 + (i // 40) ** 2):
        x += sqrt(abs(sin(i + x) * cos(x))) + 1e-9
    return x


def sched_worker(mode, t, p, n, C, cnt, tw, bar):
    bar.wait()
    t0 = time.perf_counter()
    acc = 0.0
    if mode == "block":
        for i in range(t * n // p, (t + 1) * n // p):
            acc += item(i)
    elif mode == "cyclic":
        for i in range(t, n, p):
            acc += item(i)
    else:
        while True:
            with cnt.get_lock():
                s = cnt.value
                cnt.value = s + C
            if s >= n:
                break
            for i in range(s, min(s + C, n)):
                acc += item(i)
    tw[t] = time.perf_counter() - t0


def run_cfg(mode, C, p, runs):
    cnt = mp.Value("i", 0)
    tw = mp.Array("d", p)
    res = []
    for r in range(runs + 1):                     # first run is warm-up
        cnt.value = 0
        for t in range(p):
            tw[t] = 0.0
        twall = run_parallel(sched_worker, [(mode, t, p, N, C, cnt, tw) for t in range(p)])
        times = list(tw)
        lam = max(times) / (sum(times) / p)
        if r:
            res.append((twall, lam))
    res.sort()
    return res[len(res) // 2]                     # (T_wall_ms, lambda) at median T_wall


if __name__ == "__main__":
    p = PPHYS
    runs = min(RUNS, 5)
    log(f"== PHASE 4 (N={N}, p={p}) ==")
    log("strategy            | T_wall_ms | lambda")
    twb, lb = run_cfg("block", 0, p, runs)
    log(f"{'block static':19s} | {twb:9.1f} | {lb:.3f}")
    twc, lc = run_cfg("cyclic", 0, p, runs)
    log(f"{'cyclic static':19s} | {twc:9.1f} | {lc:.3f}")
    best = None
    for C in (1, 8, 64, 512):
        tw_, l_ = run_cfg("dynamic", C, p, runs)
        log(f"{'dynamic C=' + str(C):19s} | {tw_:9.1f} | {l_:.3f}")
        if best is None or tw_ < best[1]:
            best = (C, tw_)
    log(f"C* = {best[0]} (T_wall {best[1]:.1f} ms)")
    log(emit_verify_tag("PHASE4", SEED, twb, best[1]))
