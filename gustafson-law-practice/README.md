# Gustafson's Law practice repository

Practice solutions for the 25-task assignment on scaled speedup and weak scaling. The derivations distinguish fixed-size Amdahl scaling from fixed-time Gustafson scaling; numerical examples, algorithm discussions, simulator, and measured multiprocessing exercise are indexed below.

## Contents

- `theory/task01_scaling_models.md` — strong vs weak scaling
- `theory/task02_derivation.md` — scaled speedup derivation
- `theory/task03_serial_invariance.md` — serial fraction frame of reference
- `theory/task04_asymptotic_limits.md` — efficiency limits
- `theory/task05_historical_ncube.md` — nCUBE historical result and source
- `theory/task10_memory_growth.md` — memory capacity limits
- `theory/task11_sun_ni_comparison.md` — memory-bounded model
- `theory/task12_communication_penalty.md` — communication extension
- `theory/task13_failure_cases.md` — two failure cases
- `theory/task14_isoefficiency.md` — isoefficiency
- `theory/task15_energy_scaling.md` — energy model
- `calculations/task06_parametric_table.md` through `task09_multicomponent.md` — numeric tasks
- `calculations/task16_gemm_scaling.md`, `task17_stencil_scaling.md` — domain calculations
- `analysis/task18_nbody_scaling.md` through `task20_graph_processing.md` — algorithm analyses
- `benchmarks/simulator.py` — CSV simulator and model overlay
- `benchmarks/weak_scale_bench/` — multiprocessing benchmark and usage notes
- `benchmarks/results_raw.csv`, `results.csv`, `fit_gustafson.py`, `fit_summary.md` — raw and summarized measurements
- `analysis/task23_measurement_notes.md`, `analysis/task24_hardware_audit.md` — experimental method and hardware limitations
- `plots/model_overlay.png`, `plots/model_overlay.pdf`, `plots/scaling_comparison.png`, `plots/scaling_comparison.pdf` — model and empirical plots

## Equations

`S_G=P−α(P−1)`, `E_G=1−α+α/P`; `S_A=1/[s+(1−s)/P]`. Gustafson applies when useful work expands with resources while elapsed time remains approximately fixed. Validate the premise against communication, imbalance, memory, and setup costs.

## Run

From this directory:

```sh
python3 benchmarks/simulator.py --alpha 0.04 --max-p 65536 --csv plots/sim.csv --plot plots/sim.png
python3 benchmarks/weak_scale_bench/weak_scale_bench.py --samples-per-worker 100000 --threads 1 2 4 6 10 --runs 5 --csv benchmarks/results_raw.csv
(cd benchmarks && python3 fit_gustafson.py)
```

Python 3 is required. The simulator plot needs matplotlib. The benchmark uses the standard library. The recorded empirical result is specific to an Apple M4/macOS host; its small Python kernel is startup-bound, so treat it as a measurement exercise rather than a performance claim.
