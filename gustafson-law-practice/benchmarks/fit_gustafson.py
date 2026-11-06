#!/usr/bin/env python3
"""OLS fit of empirical scaled speedup to S=P-alpha(P-1)."""
import argparse,csv
ap=argparse.ArgumentParser(); ap.add_argument('--input',default='results.csv'); ap.add_argument('--output',default='fit_summary.md'); a=ap.parse_args()
r=list(csv.DictReader(open(a.input))); x=[int(z['threads'])-1 for z in r]; y=[int(z['threads'])-float(z['mean_scaled_speedup']) for z in r]
den=sum(v*v for v in x); alpha=sum(u*v for u,v in zip(x,y))/den if den else 0.0
pred=[p-alpha*(p-1) for p in [int(z['threads']) for z in r]]
with open(a.output,'w') as f:
 f.write(f'# Regression fit\n\nOLS through the P=1 anchor, fitting `P-S=α(P-1)` from the weak-scale benchmark summary.\n\n- Fitted α: **{alpha:.6f}** ({alpha*100:.3f}%)\n- Model: `S=P−{alpha:.6f}(P−1)`\n\nThis fitted effective parameter is based on a Python process-startup-bound microbenchmark and has no general hardware interpretation.\n')
print(f'alpha={alpha:.6f}')
