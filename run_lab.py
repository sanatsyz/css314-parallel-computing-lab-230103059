#!/usr/bin/env python3
"""Re-run the entire empirical lab sequentially on the current physical host."""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--student-id", default="30103059", help="exactly eight digits")
    parser.add_argument("--steps", type=int, default=100)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    environment = dict(os.environ)
    # Avoid nested BLAS threading. The measured matrix hot loops are scalar C;
    # the stencil uses NumPy elementwise operations, not matrix multiplication.
    environment.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", VECLIB_MAXIMUM_THREADS="1")
    commands = [
        ["src/profile_env.py", "--student-id", args.student_id],
        ["src/stride_bench.py"],
        ["src/dense_kernel.py"],
        ["src/false_sharing.py"],
        ["src/scaling_study.py", "--steps", str(args.steps)],
        ["verify_outputs.py", "--student-id", args.student_id],
    ]
    for command in commands:
        print("\nRunning " + " ".join(command), flush=True)
        subprocess.run([sys.executable, *command], cwd=root, env=environment, check=True)
    print("\nReal measurements regenerated and locally verified. Existing Git milestone tags were not changed.")


if __name__ == "__main__":
    main()
