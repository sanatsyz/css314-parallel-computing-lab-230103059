"""harness.py - timing, verification, and shared helpers (standard library only)."""
from dataclasses import dataclass
import multiprocessing as mp
import os
import time
from typing import Callable

# ---- configuration (override via environment variables) ----
SEED = "230103059"                                          # your Student ID
PLOG = mp.cpu_count()                                       # logical threads
PPHYS = int(os.environ.get("PPHYS", max(1, PLOG // 2)))     # physical cores from Phase 0
SCALE = float(os.environ.get("SCALE", "1"))                 # <1 shrinks workloads (smoke tests only)
RUNS = int(os.environ.get("RUNS", "7"))
WARMUP = int(os.environ.get("WARMUP", "2"))


@dataclass
class BenchStats:
    min_ms: float
    median_ms: float
    iqr_ms: float


def fnv1a_hash(s: str) -> int:
    h = 14695981039346656037
    for b in s.encode("utf-8"):
        h = ((h ^ b) * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return h


def _stats(samples):
    samples = sorted(samples)
    n = len(samples)
    return BenchStats(samples[0], samples[n // 2], samples[(3 * n) // 4] - samples[n // 4])


def run_benchmark(fn: Callable[[], None], warmup: int = WARMUP, runs: int = RUNS) -> BenchStats:
    for _ in range(warmup):
        fn()
    samples = []
    for _ in range(runs):
        t0 = time.perf_counter_ns()
        fn()
        samples.append((time.perf_counter_ns() - t0) / 1e6)
    return _stats(samples)


def run_benchmark_ms(fn: Callable[[], float], warmup: int = WARMUP, runs: int = RUNS) -> BenchStats:
    """Like run_benchmark, but fn returns its own measured time in ms
    (used with run_parallel so process start-up is excluded)."""
    for _ in range(warmup):
        fn()
    return _stats([fn() for _ in range(runs)])


def emit_verify_tag(phase: str, seed, m1: float, m2: float) -> str:
    hw = mp.cpu_count()
    sig = fnv1a_hash(f"{phase}|{seed}|{hw}|{m1:.4f}|{m2:.4f}")
    return f"VERIFY_HASH[{phase}]: {sig:016X} (P_log={hw})"


def run_parallel(target, arglists) -> float:
    """Start one OS process per args tuple. Each target receives its args plus a
    Barrier as the LAST argument and must call barrier.wait() after its setup.
    Returns wall ms from barrier release until every process has joined."""
    p = len(arglists)
    bar = mp.Barrier(p + 1)
    procs = [mp.Process(target=target, args=tuple(a) + (bar,)) for a in arglists]
    for pr in procs:
        pr.start()
    bar.wait()
    t0 = time.perf_counter_ns()
    for pr in procs:
        pr.join()
    return (time.perf_counter_ns() - t0) / 1e6


def p_list():
    ps, p = [], 1
    while p <= PLOG:
        ps.append(p)
        p *= 2
    if ps[-1] != PLOG:
        ps.append(PLOG)
    return ps


def karp_flatt(sp: float, p: int) -> float:
    return (1 / sp - 1 / p) / (1 - 1 / p)


def log(line: str = "") -> None:
    print(line, flush=True)
    with open("results.log", "a") as f:
        f.write(line + "\n")
