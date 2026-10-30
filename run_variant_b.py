"""Run all Variant B defaults sequentially, generate the report, and verify it."""

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent


def main():
    for script in ("variant_b_support.py", "exp_a_granularity.py", "exp_b_queue.py",
                   "exp_c_buffered.py", "variant_b_report.py", "verify_variant_b.py"):
        print("\nRunning {}".format(script), flush=True)
        subprocess.run([sys.executable, script], cwd=ROOT, check=True)
    print("\nVariant B data checked. See RESULTS_B.md for observed performance; instructor sign-off is pending.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
