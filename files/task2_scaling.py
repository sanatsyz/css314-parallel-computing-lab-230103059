"""Phase 2: strong vs weak scaling with a serial Stage A + parallel Stage B."""
import math
import time
import multiprocessing as mp
from harness import *

sin, sqrt = math.sin, math.sqrt


def stage_a(n):                      # 10 ops/element: 5 sin + 5 sqrt
    acc = 0.0
    for i in range(n):
        x = i * 1e-3
        for _ in range(5):
            x = sqrt(abs(sin(x)) + 1.0)
        acc += x
    return acc


def stage_b_chunk(se):               # 30 ops/element: 10 x (FMA, sin, FMA); no shared writes
    s, e = se
    acc = 0.0
    for i in range(s, e):
        x = i * 1e-6
        for _ in range(10):
            x = x * 0.999 + 0.001
            x = sin(x)
            x = x * 1.001 + 0.0005
        acc += x
    return acc


def chunks(n, p):
    k = max(1, p * 4)
    return [(n * c // k, n * (c + 1) // k) for c in range(k)]


def trial(pool, n, p):
    t0 = time.perf_counter_ns()
    stage_a(int(0.05 * n))
    t_a = (time.perf_counter_ns() - t0) / 1e6
    pool.map(stage_b_chunk, chunks(n, p))
    return (time.perf_counter_ns() - t0) / 1e6, t_a


def median_trial(n, p):
    pool = mp.Pool(processes=p)               # persistent, created outside the timed loop
    try:
        for _ in range(WARMUP):
            trial(pool, n, p)
        res = sorted(trial(pool, n, p) for _ in range(RUNS))
        return res[len(res) // 2]             # (total_ms, stageA_ms) of the median run
    finally:
        pool.close()
        pool.join()


if __name__ == "__main__":
    log(f"== PHASE 2 (P_phys={PPHYS}, P_log={PLOG}) ==")
    N = int(1.2e6 * SCALE)
    log(f"-- Strong scaling, N={N} --")
    log("  p |   T_ms |    Sp |    Ep")
    T, S = {}, {}
    for p in range(1, PLOG + 1):
        T[p], tA = median_trial(N, p)
        if p == 1:
            s_frac = tA / T[1]
        S[p] = T[1] / T[p]
        log(f"{p:3d} | {T[p]:6.0f} | {S[p]:5.2f} | {S[p]/p:5.2f}")
    cap = 1 / s_frac
    amd = 1 / (s_frac + (1 - s_frac) / PLOG)
    log(f"serial fraction s = {s_frac:.4f}; Amdahl cap 1/s = {cap:.2f}; "
        f"Amdahl prediction at P_log = {amd:.2f}; observed S(P_log) = {S[PLOG]:.2f}")
    if 2 <= PPHYS < PLOG:
        d1 = S[PPHYS] - S[PPHYS - 1]
        d2 = S[PPHYS + 1] - S[PPHYS]
        log(f"marginal speedup: p={PPHYS-1}->{PPHYS}: {d1:+.3f}; p={PPHYS}->{PPHYS+1}: {d2:+.3f}; "
            f"drop = {100*(1 - d2/d1) if d1 else float('nan'):.0f}%")

    N0 = int(2.0e5 * SCALE)
    log(f"-- Weak scaling, N0={N0} per worker --")
    log("  p |   T_ms |  E_weak | alpha | S_Gustafson")
    Tw1, g_last = None, 0.0
    for p in range(1, PLOG + 1):
        tw, tA = median_trial(p * N0, p)
        if p == 1:
            Tw1 = tw
        alpha = tA / tw
        g_last = p - alpha * (p - 1)
        log(f"{p:3d} | {tw:6.0f} | {Tw1/tw:7.2f} | {alpha:5.3f} | {g_last:6.2f}")
    log(emit_verify_tag("PHASE2", SEED, S[PLOG], g_last))
