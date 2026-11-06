#!/usr/bin/env python3
"""Multiprocessing weak-scaling benchmark: fixed numerical integration samples per worker."""
import argparse, math, multiprocessing as mp, os, platform, statistics, time, csv

def integrate(job):
    worker, samples=job
    # Deterministic worker-specific interval of the midpoint rule for integral 4/(1+x*x).
    start=worker*samples
    acc=0.0
    for i in range(start,start+samples):
        # A bounded, nontrivial kernel; deterministic per global index.
        x=((i*2654435761)%1000003)/1000003
        acc += 4.0/(1.0+x*x)
    return acc

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--samples-per-worker',type=int,default=200000); ap.add_argument('--threads',type=int,nargs='+',default=[1,2,4,6,10]); ap.add_argument('--runs',type=int,default=5); ap.add_argument('--csv',default='results_raw.csv'); a=ap.parse_args()
    rows=[]
    for n in a.threads:
        for run in range(1,a.runs+1):
            t=time.perf_counter()
            with mp.Pool(n) as pool: result=pool.map(integrate,[(i,a.samples_per_worker) for i in range(n)])
            elapsed=time.perf_counter()-t
            rows.append((n,run,a.samples_per_worker,n*a.samples_per_worker,elapsed,sum(result)))
            print(f'threads={n} run={run} seconds={elapsed:.6f}',flush=True)
    with open(a.csv,'w',newline='') as f:
        w=csv.writer(f); w.writerow(['threads','run','samples_per_worker','total_samples','wall_seconds','checksum']); w.writerows(rows)
if __name__=='__main__': main()
