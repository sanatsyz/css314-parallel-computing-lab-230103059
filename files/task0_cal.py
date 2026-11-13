"""Phase 0 checkpoint: logical cores + perf_counter_ns call latency."""
import time
import multiprocessing as mp
from harness import emit_verify_tag, log, SEED

if __name__ == "__main__":
    n = 10 ** 6
    pc = time.perf_counter_ns
    t0 = pc()
    for _ in range(n):
        pc()
    avg_ns = (pc() - t0) / n
    log(f"P_log = {mp.cpu_count()}")
    log(f"avg perf_counter_ns call latency = {avg_ns:.2f} ns")
    log(emit_verify_tag("PHASE0", SEED, float(mp.cpu_count()), avg_ns))
