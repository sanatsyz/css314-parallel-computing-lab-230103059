"""Run the practice handout sequentially using only the Python standard library."""

import argparse
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--supplemental-c", action="store_true",
                        help="also measure 200 million increments separately from required C")
    args = parser.parse_args(argv)
    commands = [["practice_support.py"], ["exp_a_serial.py"],
                ["exp_b_contention.py"], ["exp_c_fixed.py"]]
    if args.supplemental_c:
        commands.append(["exp_c_fixed.py", "--total-increments", "200000000",
                         "--output-dir", "practice_results/supplemental_c_200m"])
    commands.extend([["practice_report.py"], ["practice_verify.py"]])
    for command in commands:
        print("\nRunning {}".format(" ".join(command)), flush=True)
        subprocess.run([sys.executable] + command, cwd=ROOT, check=True)
    print("\nAll practice data verified. See RESULTS.md for actual performance conditions; instructor sign-off remains pending.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
