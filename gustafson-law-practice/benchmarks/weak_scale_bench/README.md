# Weak-scaling benchmark

Run `python3 weak_scale_bench.py --samples-per-worker 200000 --threads 1 2 4 6 10 --runs 5 --csv ../results_raw.csv`. Requires Python 3. The same number of kernel evaluations is assigned per process, so total work grows with process count. Results include process startup and reduction of checksums; this small Python workload is illustrative and likely startup-bound. Do not interpret process count as physical cores on every platform.
