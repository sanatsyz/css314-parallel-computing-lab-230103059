"""Independently verify Variant B data; empirical targets do not gate correctness.

This standard-library checker imports no benchmark or metric implementation.
It is a local check, not an instructor-supplied checker or sign-off.
"""

import argparse
import csv
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys


WORKERS = [1, 2, 4, 8]
CASES = ("a_micro", "a_coarse", "b_queue", "c_buffered")
TOTALS = {"a_micro": 1_000_000, "a_coarse": 1_000_000,
          "b_queue": 400_000, "c_buffered": 10_000_000}
SUMMARY_FIELDS = ["workers", "repeats", "median_seconds", "minimum_seconds",
                  "maximum_seconds", "speedup", "efficiency_percent", "karp_flatt"]


class VerificationError(ValueError):
    """Saved evidence is incomplete or inconsistent."""


def require(condition, message):
    if not condition:
        raise VerificationError(message)


def is_integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def number(value, label, positive=False):
    require(isinstance(value, (int, float)) and not isinstance(value, bool),
            "{}: expected a number".format(label))
    require(math.isfinite(value), "{}: expected a finite number".format(label))
    require(not positive or value > 0, "{}: expected a positive number".format(label))
    return float(value)


def close(actual, expected, label):
    require(math.isclose(number(actual, label), expected, rel_tol=1e-9, abs_tol=1e-12),
            "{}: differs from independently recomputed value {!r}".format(label, expected))


def exact(actual, expected, label):
    require(is_integer(actual) and actual == expected,
            "{}: expected exact integer {}".format(label, expected))


def load_json(path):
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise VerificationError("{}: cannot read JSON: {}".format(Path(path).name, exc)) from exc
    require(isinstance(payload, dict), "{}: expected an object".format(Path(path).name))
    return payload


@lru_cache(maxsize=2)
def collatz_reference(total_items):
    """Independent bounded memoization with two-step compression for odd terms.

    The benchmark instead executes the handout's naive one-step loop for each
    input.  Only this out-of-timer oracle caches trajectories.
    """
    require(is_integer(total_items) and total_items >= 0, "invalid Collatz input count")
    cache = [0] * (total_items + 1)
    for initial in range(2, total_items + 1):
        value, path = initial, []
        while value != 1 and (value > total_items or cache[value] == 0):
            if value & 1:
                path.append((value, 2))
                value = (3 * value + 1) // 2
            else:
                path.append((value, 1))
                value //= 2
        steps = cache[value] if value <= total_items else 0
        for node, distance in reversed(path):
            steps += distance
            if node <= total_items:
                cache[node] = steps
    return sum(cache)


def expected_partition(total_items, workers):
    quotient, remainder = divmod(total_items, workers)
    return [quotient + (index < remainder) for index in range(workers)]


def pattern_reference(count):
    """Exact sum of worker-local values i % 7 without replaying its loop."""
    groups, tail = divmod(count, 7)
    return groups * 21 + tail * (tail - 1) // 2


def independent_summary(samples):
    groups = {p: [s["runtime_seconds"] for s in samples if s["workers"] == p]
              for p in WORKERS}
    baseline = statistics.median(groups[1])
    rows = []
    for p in WORKERS:
        values = groups[p]
        median = statistics.median(values)
        speedup = baseline / median
        rows.append({"workers": p, "repeats": len(values), "median_seconds": median,
                     "minimum_seconds": min(values), "maximum_seconds": max(values),
                     "speedup": speedup, "efficiency_percent": 100 * speedup / p,
                     "karp_flatt": None if p == 1 else (p * median / baseline - 1) / (p - 1)})
    return rows


def verify_summary(saved, expected, label):
    require(isinstance(saved, list) and len(saved) == len(WORKERS),
            "{}: expected four summary rows".format(label))
    for row, reference in zip(saved, expected):
        require(isinstance(row, dict), "{}: summary row must be an object".format(label))
        for field in SUMMARY_FIELDS:
            require(field in row, "{}: missing {}".format(label, field))
            if field in ("workers", "repeats"):
                exact(row[field], reference[field], "{} {}".format(label, field))
            elif reference[field] is None:
                require(row[field] is None, "{}: P=1 karp_flatt must be null".format(label))
            else:
                close(row[field], reference[field], "{} P={} {}".format(label, reference["workers"], field))


def verify_tsv(path, expected):
    try:
        with Path(path).open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream, delimiter="\t")
            require(reader.fieldnames == SUMMARY_FIELDS, "{}: unexpected TSV columns".format(path.name))
            rows = list(reader)
    except OSError as exc:
        raise VerificationError("{}: cannot read TSV: {}".format(path.name, exc)) from exc
    require(len(rows) == len(WORKERS), "{}: expected four TSV rows".format(path.name))
    for row, reference in zip(rows, expected):
        require(set(row) == set(SUMMARY_FIELDS), "{}: unexpected extra TSV cells".format(path.name))
        for field in SUMMARY_FIELDS:
            if reference[field] is None:
                require(row[field] == "", "{}: P=1 karp_flatt must be empty".format(path.name))
            else:
                try:
                    value = float(row[field])
                except (TypeError, ValueError) as exc:
                    raise VerificationError("{}: invalid {}".format(path.name, field)) from exc
                close(value, reference[field], "{} {}".format(path.name, field))


def verify_case(payload, case_id, output_dir):
    require(case_id in CASES, "unknown case ID")
    label = case_id
    exact(payload.get("schema_version"), 1, label + " schema_version")
    require(payload.get("case_id") == case_id, label + ": incorrect case_id")
    stamp = payload.get("created_at_utc")
    require(isinstance(stamp, str), label + ": missing UTC timestamp")
    try:
        recorded = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise VerificationError(label + ": invalid UTC timestamp") from exc
    require(recorded.utcoffset() is not None and recorded.utcoffset().total_seconds() == 0,
            label + ": timestamp must include UTC offset")
    config = payload.get("config")
    require(isinstance(config, dict), label + ": missing config")
    require(config.get("workers") == WORKERS and all(is_integer(p) for p in config["workers"]),
            label + ": workers must be [1, 2, 4, 8]")
    require(config.get("quick") is False, label + ": quick/smoke data cannot replace full measurements")
    repeats = config.get("repeats")
    require(is_integer(repeats) and repeats >= 3, label + ": require at least three repeats")
    require(config.get("start_method") == "spawn", label + ": expected spawn")
    total = TOTALS[case_id]
    exact(config.get("total_items"), total, label + " total_items")
    if case_id.startswith("a_"):
        chunk_size = 1 if case_id == "a_micro" else 10_000
        exact(config.get("chunk_size"), chunk_size, label + " chunk_size")
        oracle = collatz_reference(total)
    elif case_id == "c_buffered":
        exact(config.get("batch_size"), 10_000, label + " batch_size")
    samples = payload.get("samples")
    require(isinstance(samples, list) and len(samples) == len(WORKERS) * repeats,
            label + ": wrong sample count")
    observed_repeats = {p: set() for p in WORKERS}
    for index, sample in enumerate(samples):
        item = "{} sample {}".format(label, index)
        require(isinstance(sample, dict), item + ": expected object")
        p = sample.get("workers")
        require(is_integer(p) and p in WORKERS, item + ": invalid workers")
        repeat = sample.get("repeat")
        require(is_integer(repeat) and 1 <= repeat <= repeats, item + ": invalid repeat")
        require(repeat not in observed_repeats[p], item + ": duplicate repeat")
        observed_repeats[p].add(repeat)
        number(sample.get("runtime_seconds"), item + " runtime", positive=True)
        exact(sample.get("total_items"), total, item + " total_items")
        exact(sample.get("result_count"), total, item + " result_count")
        require(sample.get("start_method") == "spawn", item + ": expected spawn")
        if case_id.startswith("a_"):
            exact(sample.get("chunk_size"), chunk_size, item + " chunk_size")
            exact(sample.get("result_sum"), oracle, item + " result_sum")
        else:
            partition = expected_partition(total, p)
            actual = sample.get("worker_items")
            require(isinstance(actual, list) and all(is_integer(v) for v in actual)
                    and actual == partition, item + ": incorrect worker_items")
            exitcodes = sample.get("worker_exitcodes")
            require(isinstance(exitcodes, list) and len(exitcodes) == p
                    and all(is_integer(code) and code == 0 for code in exitcodes),
                    item + ": incorrect worker_exitcodes")
            oracle = sum(pattern_reference(count) for count in partition)
            exact(sample.get("result_sum"), oracle, item + " result_sum")
            exact(sample.get("expected_sum"), oracle, item + " expected_sum")
            if case_id == "b_queue":
                exact(sample.get("received_messages"), total, item + " received_messages")
            else:
                batch = config["batch_size"]
                exact(sample.get("batch_size"), batch, item + " batch_size")
                messages = sum((count + batch - 1) // batch for count in partition)
                exact(sample.get("received_messages"), messages, item + " received_messages")
                exact(sample.get("sentinels_received"), p, item + " sentinels_received")
                if "received_batches" in sample:
                    exact(sample["received_batches"], messages, item + " received_batches")
                if "total_received_messages" in sample:
                    exact(sample["total_received_messages"], messages + p, item + " total_received_messages")
    expected_repeats = set(range(1, repeats + 1))
    require(all(indices == expected_repeats for indices in observed_repeats.values()),
            label + ": incomplete repeats")
    summary = independent_summary(samples)
    verify_summary(payload.get("summary"), summary, label + " JSON")
    verify_tsv(Path(output_dir) / (case_id + ".tsv"), summary)
    return {"status": "pass", "samples_verified": len(samples),
            "full_handout_parameters": True, "total_items": total, "summary": summary}


def assess_rubric(checks):
    """Keep observations distinct from numerical correctness and causal proof."""
    rows = {case: {row["workers"]: row for row in checks[case]["summary"]} for case in CASES}
    micro, coarse, b, c = (rows[case] for case in CASES)
    ratios = {str(p): micro[p]["median_seconds"] / coarse[p]["median_seconds"] for p in WORKERS}
    slower = all(ratio > 1 for ratio in ratios.values())
    b_negative = b[8]["median_seconds"] > b[1]["median_seconds"]
    e_values = [b[p]["karp_flatt"] for p in (2, 4, 8)]
    e_increasing = all(left < right for left, right in zip(e_values, e_values[1:]))
    times_increasing = all(b[left]["median_seconds"] < b[right]["median_seconds"]
                           for left, right in zip(WORKERS, WORKERS[1:]))
    throughputs = {str(p): (TOTALS["c_buffered"] / c[p]["median_seconds"])
                         / (TOTALS["b_queue"] / b[p]["median_seconds"]) for p in WORKERS}
    s8, e8 = c[8]["speedup"], c[8]["karp_flatt"]
    return {
        "A": {"meets_numeric_condition": slower,
              "micro_over_coarse_runtime_ratio": ratios,
              "micro_slower_at_all_worker_counts": slower,
              "condition": "Micro-task runtime exceeds coarse-chunk runtime at each P",
              "causal_proof_from_timings_alone": False},
        "B": {"meets_numeric_condition": b_negative and e_increasing,
              "t8_greater_than_t1": b_negative, "runtime_monotonically_increases": times_increasing,
              "e2_e4_e8_strictly_increase": e_increasing,
              "e2": e_values[0], "e4": e_values[1], "e8": e_values[2],
              "table_s8_below_half": b[8]["speedup"] < 0.5,
              "table_e2_above_half": e_values[0] > 0.5,
              "table_e8_above_two": e_values[2] > 2.0,
              "condition": "T8 > T1 and e(2) < e(4) < e(8) (final sign-off criteria)"},
        "C": {"meets_numeric_condition": s8 > 5 and e8 <= 0.05 and throughputs["8"] > 10,
              "speedup_8": s8, "karp_flatt_8": e8,
              "throughput_gain_over_unbuffered": throughputs,
              "eight_worker_throughput_gain_over_ten": throughputs["8"] > 10,
              "all_worker_throughput_gains_over_ten": all(value > 10 for value in throughputs.values()),
              "runtime_below_unbuffered_all_p": all(c[p]["median_seconds"] < b[p]["median_seconds"] for p in WORKERS),
              "task_e8_below_004": e8 < 0.04,
              "table_e2_below_005": c[2]["karp_flatt"] < 0.05,
              "table_e8_below_005": e8 < 0.05,
              "condition": "At P=8: normalized throughput gain > 10, S8 > 5, e(8) <= 0.05",
              "threshold_note": "Task text uses e < 0.04; final sign-off uses e(8) <= 0.05; both observations are retained."},
    }


def verify_environment(profile, config):
    for field in ("cpu_model", "architecture", "os"):
        require(isinstance(profile.get(field), str) and profile[field], "host_profile.json: missing " + field)
    for field in ("physical_cores", "logical_threads"):
        require(is_integer(profile.get(field)) and profile[field] > 0, "host_profile.json: invalid " + field)
    require(profile["logical_threads"] >= max(WORKERS), "host_profile.json: fewer than eight logical CPUs")
    require(isinstance(profile.get("python"), dict) and isinstance(profile["python"].get("version"), str),
            "host_profile.json: missing Python version")
    timer = profile.get("timer")
    require(isinstance(timer, dict) and timer.get("monotonic") is True, "host_profile.json: invalid timer")
    number(timer.get("resolution_seconds"), "host_profile.json timer resolution", positive=True)
    require(config.get("student_id") == "230103059", "configuration.json: wrong student_id")
    require(config.get("branch") == "variant-b-230103059", "configuration.json: wrong branch")
    require(config.get("workers") == WORKERS and all(is_integer(p) for p in config["workers"]),
            "configuration.json: wrong workers")
    require(is_integer(config.get("repeats")) and config["repeats"] >= 3, "configuration.json: invalid repeats")
    require(config.get("start_method") == "spawn", "configuration.json: expected spawn")
    require(config.get("course", "CSS314") == "CSS314", "configuration.json: wrong course")


def file_manifest(repo_root, output_dir):
    repo_root, output_dir = Path(repo_root).resolve(), Path(output_dir).resolve()
    names = ["variant_b_support.py", "practice_support.py", "verify_variant_b.py", "run_variant_b.py",
             "variant_b_report.py", "VARIANT_B_GUIDE.md", "RESULTS_B.md",
             "CS482 Practice Lab Handout (Variant B).pdf", "exp_a_granularity.py", "exp_b_queue.py", "exp_c_buffered.py"]
    files = {repo_root / name for name in names if (repo_root / name).is_file()}
    files.update(repo_root.glob("tests/test_variant_b*.py"))
    files.update(path for path in output_dir.rglob("*") if path.is_file()
                 and path != output_dir / "verification.json")
    manifest = []
    for path in sorted(files):
        content = path.read_bytes()
        try:
            name = str(path.relative_to(repo_root))
        except ValueError:
            name = str(path)
        manifest.append({"path": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
    return manifest


def verify_results(output_dir, repo_root=None):
    directory = Path(output_dir)
    profile = load_json(directory / "host_profile.json")
    config = load_json(directory / "configuration.json")
    verify_environment(profile, config)
    checks = {case: verify_case(load_json(directory / (case + ".json")), case, directory) for case in CASES}
    return {"schema_version": 1, "verified_at_utc": datetime.now(timezone.utc).isoformat(),
            "correctness_status": "pass", "checks": checks, "rubric": assess_rubric(checks),
            "verification_kind": "independent local schema, arithmetic and numerical checks",
            "official_instructor_checker": False, "cryptographically_signed": False,
            "instructor_signoff": "pending", "manifest": file_manifest(repo_root or Path(__file__).resolve().parent, directory),
            "limitations": ["Source hashes are recorded; they are not a signed proof of how elapsed times were captured.",
                            "Empirical performance targets do not determine the numerical/schema verification exit status.",
                            "Karp-Flatt trajectories alone cannot establish specific bus, cache-coherence, or lock-wait mechanisms.",
                            "Instructor review and sign-off remain pending."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("variant_b_results"))
    parser.add_argument("--no-receipt", action="store_true", help="read-only check; preserve existing receipt")
    args = parser.parse_args(argv)
    receipt = args.output_dir / "verification.json"
    if not args.no_receipt:
        receipt.unlink(missing_ok=True)
    try:
        report = verify_results(args.output_dir)
        if not args.no_receipt:
            receipt.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    except (VerificationError, OSError) as exc:
        print("Variant B verification FAILED: {}".format(exc), file=sys.stderr)
        return 1
    print("Variant B numerical/schema verification: PASS (local; instructor sign-off pending)")
    for case, rubric in report["rubric"].items():
        print("Experiment {}: empirical condition {}".format(case, "met" if rubric["meets_numeric_condition"] else "not met"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
