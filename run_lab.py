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
    ]
    for command in commands:
        print("\nRunning " + " ".join(command), flush=True)
        subprocess.run([sys.executable, *command], cwd=root, env=environment, check=True)
    print("\nRunning the unchanged teacher verifier through check_teacher.py", flush=True)
    teacher = subprocess.run([sys.executable, "check_teacher.py"], cwd=root, env=environment)
    # Keep the stronger numerical check independent, including when the teacher
    # script rejects this host's actual hardware. Run it last so its file hashes
    # include the saved teacher-check report.
    subprocess.run([sys.executable, "verify_numerics.py", "--student-id", args.student_id],
                   cwd=root, env=environment, check=True)
    if teacher.returncode:
        print("\nLocal numerical checks passed. The teacher verifier failed; see results/teacher_verification.json.")
        return teacher.returncode
    print("\nReal measurements regenerated. Teacher and local checks passed. Existing Git milestone tags were not changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
