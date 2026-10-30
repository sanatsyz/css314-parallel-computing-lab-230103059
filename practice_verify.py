"""Independently check the saved Karp–Flatt practice data, not performance targets.

This is a local verifier, not an instructor-provided checker or sign-off.  It
does not import the benchmark implementations or their metric helpers.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys


WORKERS = [1, 2, 4]
SUMMARY_FIELDS = [
    "workers", "repeats", "median_seconds", "minimum_seconds", "maximum_seconds",
    "speedup", "efficiency_percent", "karp_flatt",
]


class VerificationError(ValueError):
    """Saved data are incomplete or inconsistent with the practice experiment."""


def require(condition, message):
    if not condition:
        raise VerificationError(message)


def is_integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def number(value, label, positive=False):
    require(isinstance(value, (int, float)) and not isinstance(value, bool),
            f"{label}: expected a number")
    require(math.isfinite(value), f"{label}: expected a finite number")
    if positive:
        require(value > 0, f"{label}: expected a positive number")
    return float(value)


def close(actual, expected, label, *, abs_tol=1e-12, rel_tol=1e-9):
    value = number(actual, label)
    require(math.isclose(value, expected, abs_tol=abs_tol, rel_tol=rel_tol),
            f"{label}: saved {value!r}, independently calculated {expected!r}")


def load_json(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise VerificationError(f"{path.name}: cannot read JSON: {exc}") from exc
    require(isinstance(value, dict), f"{path.name}: expected a JSON object")
    return value


def serial_reference(chunk_size):
    """Use an accurate independent reduction of the stated heavy_math formula."""
    return math.fsum(math.sin(i) * math.cos(i) for i in range(1, chunk_size))


def expected_partition(total, workers):
    quotient, remainder = divmod(total, workers)
    return [quotient + (index < remainder) for index in range(workers)]


def independent_summary(samples):
    """Recalculate medians and metrics directly from raw elapsed times."""
    groups = {p: [s["runtime_seconds"] for s in samples if s["workers"] == p]
              for p in WORKERS}
    baseline = statistics.median(groups[1])
    rows = []
    for p in WORKERS:
        times = groups[p]
        median = statistics.median(times)
        speedup = baseline / median
        rows.append({
            "workers": p, "repeats": len(times), "median_seconds": median,
            "minimum_seconds": min(times), "maximum_seconds": max(times),
            "speedup": speedup, "efficiency_percent": 100.0 * speedup / p,
            "karp_flatt": None if p == 1 else (p * median / baseline - 1) / (p - 1),
        })
    return rows


def verify_summary(saved, expected, label):
    require(isinstance(saved, list) and len(saved) == len(WORKERS),
            f"{label}: expected three summary rows")
    for row, reference in zip(saved, expected):
        require(isinstance(row, dict), f"{label}: summary row must be an object")
        for field in SUMMARY_FIELDS:
            require(field in row, f"{label}: missing {field}")
            value = row[field]
            target = reference[field]
            if field in ("workers", "repeats"):
                require(is_integer(value) and value == target,
                        f"{label}: incorrect {field}")
            elif target is None:
                require(value is None, f"{label}: P=1 karp_flatt must be null")
            else:
                close(value, target, f"{label}: P={reference['workers']} {field}")


def verify_tsv(path, expected):
    try:
        with path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream, delimiter="\t")
            require(reader.fieldnames == SUMMARY_FIELDS,
                    f"{path.name}: unexpected TSV columns")
            rows = list(reader)
    except OSError as exc:
        raise VerificationError(f"{path.name}: cannot read TSV: {exc}") from exc
    require(len(rows) == len(WORKERS), f"{path.name}: expected three TSV rows")
    for row, reference in zip(rows, expected):
        require(set(row) == set(SUMMARY_FIELDS), f"{path.name}: extra TSV cells")
        for field in SUMMARY_FIELDS:
            value = row.get(field)
            target = reference[field]
            if target is None:
                require(value == "", f"{path.name}: P=1 karp_flatt must be empty")
            else:
                try:
                    numeric = float(value)
                except (TypeError, ValueError) as exc:
                    raise VerificationError(f"{path.name}: invalid {field}") from exc
                close(numeric, target, f"{path.name}: P={reference['workers']} {field}")


def verify_experiment(payload, letter, output_dir, *, supplemental=False):
    require(not supplemental or letter == "C",
            "Only C's explicitly labelled 200M supplemental experiment is supported")
    label = f"Supplemental experiment {letter} (200M)" if supplemental else f"Experiment {letter}"
    require(is_integer(payload.get("schema_version")) and payload["schema_version"] == 1,
            f"{label}: unsupported schema")
    require(payload.get("experiment") == letter, f"{label}: wrong experiment label")
    require(isinstance(payload.get("created_at_utc"), str)
            and payload["created_at_utc"], f"{label}: missing recording timestamp")
    try:
        timestamp = datetime.fromisoformat(payload["created_at_utc"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise VerificationError(f"{label}: invalid recording timestamp") from exc
    require(timestamp.utcoffset() is not None and timestamp.utcoffset().total_seconds() == 0,
            f"{label}: recording timestamp must include UTC timezone")
    config = payload.get("config")
    require(isinstance(config, dict), f"{label}: missing config")
    require(config.get("workers") == WORKERS
            and all(is_integer(p) for p in config["workers"]),
            f"{label}: workers must be [1, 2, 4]")
    require(config.get("quick") is False,
            f"{label}: quick/smoke data cannot satisfy the full handout verification")
    repeats = config.get("repeats")
    require(is_integer(repeats) and repeats >= 3,
            f"{label}: require at least three recorded repeats")
    require(config.get("start_method") == "spawn", f"{label}: expected spawn start method")
    if letter == "A":
        require(is_integer(config.get("total_chunks")) and config["total_chunks"] == 16,
                f"{label}: expected 16 chunks")
        require(is_integer(config.get("chunk_size")) and config["chunk_size"] == 2_000_000,
                f"{label}: expected chunk_size=2,000,000")
        close(config.get("serial_pause_seconds"), 0.40, f"{label}: serial pause")
        reference_result = serial_reference(config["chunk_size"])
    else:
        total = 2_000_000 if letter == "B" else (200_000_000 if supplemental else 20_000_000)
        require(is_integer(config.get("total_increments")) and config["total_increments"] == total,
                f"{label}: expected {total:,} increments")
    samples = payload.get("samples")
    require(isinstance(samples, list) and len(samples) == len(WORKERS) * repeats,
            f"{label}: wrong raw sample count")
    repeat_indices = {p: set() for p in WORKERS}
    for index, sample in enumerate(samples):
        item = f"{label} sample {index}"
        require(isinstance(sample, dict), f"{item}: expected an object")
        p = sample.get("workers")
        require(is_integer(p) and p in WORKERS, f"{item}: unexpected worker count")
        repeat = sample.get("repeat")
        require(is_integer(repeat) and repeat >= 0, f"{item}: invalid repeat index")
        require(repeat not in repeat_indices[p], f"{item}: duplicate repeat index")
        repeat_indices[p].add(repeat)
        runtime = number(sample.get("runtime_seconds"), f"{item}: runtime", positive=True)
        if letter == "A":
            require(runtime >= config["serial_pause_seconds"],
                    f"{item}: runtime omits the required serial pause")
            chunks = sample.get("chunk_results")
            require(isinstance(chunks, list) and len(chunks) == config["total_chunks"],
                    f"{item}: wrong number of math chunk results")
            for chunk_index, result in enumerate(chunks):
                close(result, reference_result, f"{item}: chunk {chunk_index}",
                      abs_tol=1e-10, rel_tol=1e-10)
            close(sample.get("total_result"), math.fsum(chunks), f"{item}: total_result",
                  abs_tol=1e-10, rel_tol=1e-10)
        else:
            for field in ("expected_total", "total_count"):
                require(is_integer(sample.get(field)) and sample[field] == total,
                        f"{item}: incorrect {field}")
            partition = expected_partition(total, p)
            iterations = sample.get("worker_iterations")
            require(isinstance(iterations, list)
                    and all(is_integer(n) for n in iterations)
                    and iterations == partition,
                    f"{item}: incorrect worker_iterations partition")
            if letter == "C":
                counts = sample.get("worker_counts")
                require(isinstance(counts, list)
                        and all(is_integer(n) for n in counts) and counts == partition,
                        f"{item}: incorrect private worker_counts")
    for p, indices in repeat_indices.items():
        valid = indices in (set(range(repeats)), set(range(1, repeats + 1)))
        require(valid, f"{label}: incomplete repeat indices for P={p}")
    expected = independent_summary(samples)
    verify_summary(payload.get("summary"), expected, f"{label} JSON")
    verify_tsv(output_dir / f"experiment_{letter.lower()}.tsv", expected)
    result = {"status": "pass", "samples_verified": len(samples),
              "summary": expected, "full_handout_parameters": not supplemental}
    if supplemental:
        result.update(total_increments=total,
                      interpretation="Supplemental workload only; does not replace the primary 20M experiment")
    return result


def assess_rubric(loaded_experiments):
    """Report performance observations separately from data correctness.

    The handout does not quantify B's ``>>``.  We report its exact growth and
    test only the weaker increasing-e observation, leaving sign-off pending.
    """
    summaries = {letter: {row["workers"]: row for row in payload["summary"]}
                 for letter, payload in loaded_experiments.items()}
    a, b, c = (summaries[letter] for letter in "ABC")
    a2, a4 = a[2]["karp_flatt"], a[4]["karp_flatt"]
    ratio = a4 / a2 if a2 != 0 else None
    if ratio is not None and not math.isfinite(ratio):
        ratio = None
    a_pass = ratio is not None and 0.80 <= ratio <= 1.25
    b_slower = b[4]["median_seconds"] > b[1]["median_seconds"]
    b_growing = b[4]["karp_flatt"] > b[2]["karp_flatt"]
    c_faster = c[4]["median_seconds"] < c[1]["median_seconds"]
    c_efficiency = c[4]["efficiency_percent"] > 70.0
    return {
        "A": {"meets_numeric_condition": a_pass, "e4_over_e2": ratio,
              "condition": "0.80 <= e(4)/e(2) <= 1.25"},
        "B": {"meets_numeric_condition": b_slower and b_growing,
              "t4_greater_than_t1": b_slower, "e4_greater_than_e2": b_growing,
              "e2": b[2]["karp_flatt"], "e4": b[4]["karp_flatt"],
              "e4_minus_e2": b[4]["karp_flatt"] - b[2]["karp_flatt"],
              "condition": "T4 > T1 and increasing e; instructor interprets '>>'",
              "instructor_judgment_required": True},
        "C": {"meets_numeric_condition": c_faster and c_efficiency,
              "t4_less_than_t1": c_faster, "efficiency_4_percent": c[4]["efficiency_percent"],
              "condition": "T4 < T1 and E4 > 70%"},
    }


def verify_host_profile(profile):
    for field in ("cpu_model", "architecture", "os"):
        require(isinstance(profile.get(field), str) and profile[field],
                f"host_profile.json: missing {field}")
    for field in ("physical_cores", "logical_threads"):
        require(is_integer(profile.get(field)) and profile[field] > 0,
                f"host_profile.json: invalid {field}")
    require(profile["logical_threads"] >= 4,
            "host_profile.json: fewer than four logical execution cores")
    python = profile.get("python")
    require(isinstance(python, dict) and isinstance(python.get("version"), str),
            "host_profile.json: missing Python version")
    timer = profile.get("timer")
    require(isinstance(timer, dict) and timer.get("monotonic") is True,
            "host_profile.json: missing monotonic timer details")
    number(timer.get("resolution_seconds"), "host_profile.json: timer resolution", positive=True)


def file_manifest(repo_root, output_dir):
    """Bind practice source, report, handout, tests and data; exclude this receipt."""
    repo_root, output_dir = Path(repo_root).resolve(), Path(output_dir).resolve()
    names = ["practice_support.py", "practice_verify.py", "practice_report.py", "run_practice.py", "exp_a_serial.py",
             "exp_b_contention.py", "exp_c_fixed.py", "Practice Lab Handout.pdf",
             "RESULTS.md", "PRACTICE_GUIDE.md", "GUIDE.md", "README.md"]
    sources = {repo_root / name for name in names if (repo_root / name).is_file()}
    sources.update(repo_root.glob("tests/test_practice*.py"))
    files = sources | {path for path in output_dir.rglob("*")
                       if path.is_file() and path != output_dir / "verification.json"}
    manifest = []
    for path in sorted(files):
        content = path.read_bytes()
        try:
            display = str(path.relative_to(repo_root))
        except ValueError:
            display = str(path)
        manifest.append({"path": display, "bytes": len(content),
                         "sha256": hashlib.sha256(content).hexdigest()})
    return manifest


def verify_results(output_dir, *, repo_root=None):
    output_dir = Path(output_dir)
    loaded, checks = {}, {}
    profile = load_json(output_dir / "host_profile.json")
    verify_host_profile(profile)
    for letter in "ABC":
        loaded[letter] = load_json(output_dir / f"experiment_{letter.lower()}.json")
        checks[letter] = verify_experiment(loaded[letter], letter, output_dir)
    # Use the independently recalculated values even after saved metrics agree.
    recalculated = {letter: {"summary": checks[letter]["summary"]} for letter in "ABC"}
    supplemental = {}
    supplemental_dir = output_dir / "supplemental_c_200m"
    if supplemental_dir.exists():
        payload = load_json(supplemental_dir / "experiment_c.json")
        check = verify_experiment(payload, "C", supplemental_dir, supplemental=True)
        # Reuse the same numeric C condition while keeping the primary rubric intact.
        supplemental_metrics = {**recalculated, "C": {"summary": check["summary"]}}
        check["performance_observation"] = assess_rubric(supplemental_metrics)["C"]
        supplemental["C_200m"] = check
    return {
        "schema_version": 1,
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "correctness_status": "pass",
        "verification_kind": "local independent schema, arithmetic and numerical checks",
        "official_instructor_checker": False,
        "cryptographically_signed": False,
        "instructor_signoff": "pending",
        "checks": checks,
        "rubric": assess_rubric(recalculated),
        "supplemental": supplemental,
        "manifest": file_manifest(repo_root or Path(__file__).resolve().parent, output_dir),
        "limitations": [
            "Saved samples are checked and source hashes are recorded; this does not independently prove how timings were captured.",
            "Performance rubric observations do not determine the numerical/schema verification exit status.",
            "Karp–Flatt growth does not by itself identify a specific hardware bottleneck.",
            "Instructor sign-off and interpretation of B's unquantified '>>' remain pending.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("practice_results"))
    parser.add_argument("--no-receipt", action="store_true",
                        help="check inputs without writing or removing a receipt")
    args = parser.parse_args(argv)
    receipt = args.output_dir / "verification.json"
    if not args.no_receipt:
        receipt.unlink(missing_ok=True)
    try:
        report = verify_results(args.output_dir)
        if not args.no_receipt:
            receipt.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    except (VerificationError, OSError) as exc:
        print(f"Practice data verification FAILED: {exc}", file=sys.stderr)
        return 1
    print("Practice numerical/schema verification: PASS (local verifier; instructor sign-off pending)")
    for letter, observation in report["rubric"].items():
        result = "met" if observation["meets_numeric_condition"] else "not met"
        print(f"Experiment {letter}: performance rubric numeric condition {result}")
    for name, supplemental in report["supplemental"].items():
        result = "met" if supplemental["performance_observation"]["meets_numeric_condition"] else "not met"
        print(f"Supplemental {name}: data checks PASS; numeric condition {result} (primary rubric unchanged)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
