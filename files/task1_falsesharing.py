"""Phase 1: false-sharing stride sweep + Karp-Flatt diagnostics."""
import ctypes
from multiprocessing import shared_memory
from harness import *

M = int(1.6e7 * SCALE)


def fs_worker(shm_name, slot_idx, iters, bar):
    shm = shared_memory.SharedMemory(name=shm_name)
    arr = (ctypes.c_uint64 * 512).from_buffer(shm.buf)
    acc = arr[slot_idx]
    bar.wait()
    for i in range(iters):
        acc = (acc * 6364136223846793005 + (i | 1)) & 0xFFFFFFFFFFFFFFFF
        arr[slot_idx] = acc  # store to the (possibly shared) cache line
    del arr
    shm.close()


def measure(shm, p, stride):
    if p * stride > 512:
        return None
    fn = lambda: run_parallel(fs_worker, [(shm.name, t * stride, M // p) for t in range(p)])
    return run_benchmark_ms(fn)


if __name__ == "__main__":
    shm = shared_memory.SharedMemory(create=True, size=4096)
    try:
        log(f"== PHASE 1 (M={M}, P_phys={PPHYS}, P_log={PLOG}) ==")
        log("-- Stride sweep at p = P_phys --")
        log("stride | bytes | median_ms |  IQR_ms | Mops/s")
        med = {}
        prev = None
        for stride in (1, 2, 4, 8, 16, 32):
            st = measure(shm, PPHYS, stride)
            if st is None:
                log(f"{stride:6d} | skipped (p*stride > 512 slots)")
                continue
            med[stride] = st.median_ms
            mops = M / (st.median_ms * 1e3)
            note = ""
            if prev and prev / st.median_ms > 1.3:
                note = f"  <-- {prev / st.median_ms:.2f}x faster than previous stride"
            prev = st.median_ms
            log(f"{stride:6d} | {stride*8:5d} | {st.median_ms:9.1f} | {st.iqr_ms:7.1f} | {mops:7.2f}{note}")

        for stride in (1, 16):
            log(f"-- Process scaling, stride={stride} --")
            log("  p | median_ms |    Sp |    Ep | Karp-Flatt e(p)")
            t1 = None
            for p in p_list():
                st = measure(shm, p, stride)
                if st is None:
                    log(f"{p:3d} | skipped"); continue
                if p == 1:
                    t1 = st.median_ms
                sp = t1 / st.median_ms
                e = f"{karp_flatt(sp, p):.4f}" if p >= 2 else "  n/a"
                log(f"{p:3d} | {st.median_ms:9.1f} | {sp:5.2f} | {sp/p:5.2f} | {e}")
        log(emit_verify_tag("PHASE1", SEED, med.get(1, 0.0), med.get(16, 0.0)))
    finally:
        shm.close()
        shm.unlink()
