#!/usr/bin/env python3
"""Compare ideal Amdahl strong scaling and Gustafson weak scaling."""
import argparse, csv

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--alpha',type=float,default=.04)
    ap.add_argument('--max-p',type=int,default=65536)
    ap.add_argument('--csv',default='scaling.csv')
    ap.add_argument('--plot',default='scaling.png')
    a=ap.parse_args()
    if not 0.001 <= a.alpha <= .20 or not 1 <= a.max_p <= 65536: ap.error('require alpha in [.001,.20], max-p in [1,65536]')
    ps=[]; p=1
    while p<a.max_p: ps.append(p); p=min(p*2,a.max_p)
    ps.append(a.max_p); ps=sorted(set(ps))
    with open(a.csv,'w',newline='') as f:
        w=csv.writer(f); w.writerow(['processors','alpha','amdahl_strong_speedup','gustafson_weak_speedup','amdahl_efficiency','gustafson_efficiency'])
        for p in ps:
            sa=1/(a.alpha+(1-a.alpha)/p); sg=p-a.alpha*(p-1)
            w.writerow([p,a.alpha,sa,sg,sa/p,sg/p])
    try:
        import matplotlib.pyplot as plt
    except ImportError as e: raise SystemExit('Install matplotlib to generate the overlay plot: python3 -m pip install matplotlib') from e
    x=[p for p in range(1,a.max_p+1) if p==1 or p&(p-1)==0]
    if x[-1]!=a.max_p:x.append(a.max_p)
    plt.figure(figsize=(8,5)); plt.plot(x,[1/(a.alpha+(1-a.alpha)/p) for p in x],label='Amdahl strong scaling'); plt.plot(x,[p-a.alpha*(p-1) for p in x],label='Gustafson weak scaling'); plt.plot(x,x,'k--',alpha=.5,label='Ideal linear')
    plt.xscale('log',base=2); plt.xlabel('Processors'); plt.ylabel('Speedup'); plt.title(f'Scaling models (α={a.alpha:g})'); plt.grid(True,which='both',alpha=.25); plt.legend(); plt.tight_layout(); plt.savefig(a.plot,dpi=180)
if __name__=='__main__': main()
