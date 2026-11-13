"""Phase 3: empirical roofline (3A) and progressive GEMM + tile sweep (3B)."""
import os
import random
from array import array
from multiprocessing import shared_memory
from harness import *

# ---------------- Part 3A workers ----------------
def copy_worker(na, nb, s, e, bar):
    a = shared_memory.SharedMemory(name=na)
    b = shared_memory.SharedMemory(name=nb)
    bar.wait()
    a.buf[s:e] = b.buf[s:e]
    a.close()
    b.close()


def fma_worker(iters, bar):
    c, d = 0.9999999, 1e-7
    a0, a1, a2, a3, a4, a5, a6, a7 = 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7
    a8, a9, a10, a11, a12, a13, a14, a15 = 1.8, 1.9, 2.0, 2.1, 2.2, 2.3, 2.4, 2.5
    bar.wait()
    for _ in range(iters):                 # 16 FMAs = 32 FLOPs per iteration
        a0 = a0 * c + d; a1 = a1 * c + d; a2 = a2 * c + d; a3 = a3 * c + d
        a4 = a4 * c + d; a5 = a5 * c + d; a6 = a6 * c + d; a7 = a7 * c + d
        a8 = a8 * c + d; a9 = a9 * c + d; a10 = a10 * c + d; a11 = a11 * c + d
        a12 = a12 * c + d; a13 = a13 * c + d; a14 = a14 * c + d; a15 = a15 * c + d


# ---------------- Part 3B ----------------
N = 256
NB = N * N * 8


def gemm_worker(variant, na, nb_, nc, r0, r1, BS, bar):
    sa = shared_memory.SharedMemory(name=na)
    sb = shared_memory.SharedMemory(name=nb_)
    sc = shared_memory.SharedMemory(name=nc)
    A = sa.buf[:NB].cast("d")
    B = sb.buf[:NB].cast("d")
    C = sc.buf[:NB].cast("d")
    bar.wait()
    if variant == 1:                       # naive i-j-k (strided B access)
        for i in range(r0, r1):
            ib = i * N
            for j in range(N):
                s = 0.0
                for k in range(N):
                    s += A[ib + k] * B[k * N + j]
                C[ib + j] = s
    elif variant == 2:                     # i-k-j, a_ik hoisted, unit-stride j
        for i in range(r0, r1):
            ib = i * N
            for k in range(N):
                a = A[ib + k]
                kb = k * N
                for j in range(N):
                    C[ib + j] += a * B[kb + j]
    else:                                  # 6-loop cache-blocked, (i,k,j) micro-kernel
        for ii in range(r0, r1, BS):
            i_hi = min(ii + BS, r1)
            for kk in range(0, N, BS):
                k_hi = min(kk + BS, N)
                for jj in range(0, N, BS):
                    j_hi = min(jj + BS, N)
                    for i in range(ii, i_hi):
                        ib = i * N
                        for k in range(kk, k_hi):
                            a = A[ib + k]
                            kb = k * N
                            for j in range(jj, j_hi):
                                C[ib + j] += a * B[kb + j]
    for v in (A, B, C):
        v.release()
    sa.close(); sb.close(); sc.close()


if __name__ == "__main__":
    p = PPHYS
    log(f"== PHASE 3 (p = P_phys = {p}) ==")

    # ---- 3A: DRAM bandwidth ----
    SZ = 64_000_000
    ba = shared_memory.SharedMemory(create=True, size=SZ)
    bb = shared_memory.SharedMemory(create=True, size=SZ)
    try:
        bb.buf[:SZ] = bytes(range(256)) * (SZ // 256) + bytes(SZ % 256)
        bounds = [(SZ * t // p, SZ * (t + 1) // p) for t in range(p)]
        st = run_benchmark_ms(lambda: run_parallel(
            copy_worker, [(ba.name, bb.name, s, e) for s, e in bounds]))
        bw = 2 * 64e6 / (st.median_ms / 1e3 * 1e9)
        log(f"BW_sustained = {bw:.3f} GB/s (median {st.median_ms:.1f} ms, IQR {st.iqr_ms:.1f})")
    finally:
        for s_ in (ba, bb):
            s_.close(); s_.unlink()

    # ---- 3A: compute ceiling ----
    flops_pw = 6.0e7 * SCALE
    iters = int(flops_pw / 32)
    st = run_benchmark_ms(lambda: run_parallel(fma_worker, [(iters,)] * p))
    psus = (iters * 32 * p) / (st.median_ms * 1e6)
    ridge = psus / bw
    log(f"P_sustained = {psus:.4f} GFLOP/s (median {st.median_ms:.1f} ms)")
    log(f"Ridge point I* = {ridge:.4f} FLOP/byte")

    # ---- 3B: GEMM ----
    rng = random.Random(1234)
    sa = shared_memory.SharedMemory(create=True, size=NB)
    sb = shared_memory.SharedMemory(create=True, size=NB)
    sc = shared_memory.SharedMemory(create=True, size=NB)
    try:
        sa.buf[:NB] = array("d", (rng.random() for _ in range(N * N))).tobytes()
        sb.buf[:NB] = array("d", (rng.random() for _ in range(N * N))).tobytes()
        rows = [(N * t // p, N * (t + 1) // p) for t in range(p)]

        def snapshot():
            a = array("d"); a.frombytes(bytes(sc.buf[:NB])); return a

        def gemm_ms(variant, BS=0):
            def fn():
                sc.buf[:NB] = bytes(NB)
                return run_parallel(gemm_worker, [(variant, sa.name, sb.name, sc.name, r0, r1, BS)
                                                  for r0, r1 in rows])
            st = run_benchmark_ms(fn)
            return st, 2 * N ** 3 / (st.median_ms * 1e6)

        st1, g1 = gemm_ms(1)
        log(f"Variant 1 (naive i-j-k)     : {st1.median_ms:9.1f} ms  {g1:.5f} GFLOP/s")
        st2, g2 = gemm_ms(2)
        c2 = snapshot()
        log(f"Variant 2 (i-k-j)           : {st2.median_ms:9.1f} ms  {g2:.5f} GFLOP/s")

        l1 = float(os.environ.get("L1D_KB", 0)); l2 = float(os.environ.get("L2_KB", 0))
        log("Variant 3 tile sweep:")
        log("  BS | median_ms | GFLOP/s | W_tile(KiB) | I_tiled | attainable(GFLOP/s) | max|C3-C2| | fits")
        best_g, best_bs = -1.0, None
        for BS in (8, 16, 32, 64, 96, 128):
            st3, g3 = gemm_ms(3, BS)
            c3 = snapshot()
            err = max(abs(x - y) for x, y in zip(c3, c2))
            assert err < 1e-9, f"verification failed for BS={BS}: {err}"
            w = 3 * BS * BS * 8 / 1024
            inten = BS / 12
            att = min(psus, bw * inten)
            fit = ("L1d" if l1 and w <= l1 else "L2" if l2 and w <= l2 else "?") if (l1 or l2) else "set L1D_KB/L2_KB"
            log(f"{BS:4d} | {st3.median_ms:9.1f} | {g3:7.5f} | {w:11.1f} | {inten:7.2f} | {att:19.3f} | {err:.2e} | {fit}")
            if g3 > best_g:
                best_g, best_bs = g3, BS
        log(f"BS* = {best_bs} (GFLOP/s {best_g:.5f}); speedup over Variant 1 = {best_g/g1:.2f}x")
        log(f"Roofline position: V1 {g1:.5f}, V2 {g2:.5f}, V3 {best_g:.5f} GFLOP/s vs "
            f"P_sustained {psus:.4f}, BW*I(BS*) = {bw*best_bs/12:.3f} GFLOP/s")
        log(emit_verify_tag("PHASE3", SEED, g1, best_g))
    finally:
        for s_ in (sa, sb, sc):
            s_.close(); s_.unlink()
