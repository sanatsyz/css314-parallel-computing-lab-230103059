#!/usr/bin/env python3
"""Run the unchanged supplied verifier on isolated copies of measured metadata.

The milestone runs are diagnostics only. Only a successful complete teacher run
can publish the receipt written by that run. This wrapper does not authenticate
the hardware, inspect the saved numerical arrays, or repair verifier assumptions.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent
# SHA-256 of the exact verify_outputs.py.txt uploaded by the teacher/student.
PROVIDED_SCRIPT_SHA256 = "bce8d586fd800f888d5001cb6919fd915590f9ec25dab1ab62bd703a502ebb21"
INPUT_FILES = (
    "host_profile.json",
    "salted_params.json",
    "stride_results.tsv",
    "loop_interchange.json",
    "false_sharing_karp_flatt.tsv",
    "scaling_metrics.tsv",
    "roofline_summary.json",
)
ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
DIAGNOSTIC_CODE = (
    "import runpy, sys; "
    "namespace = runpy.run_path(sys.argv[1], run_name='teacher_diagnostic'); "
    "namespace[sys.argv[2]]()"
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def clean_output(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return ANSI_ESCAPE.sub("", value or "")


def isolated_run(
    script_bytes: bytes,
    inputs: dict[str, bytes],
    timeout_seconds: float,
    milestone: int | None = None,
) -> tuple[dict, bytes | None]:
    """Execute exact checked bytes with only metadata copies in a temporary cwd."""
    with tempfile.TemporaryDirectory(prefix="css314-teacher-check-") as temporary:
        sandbox = Path(temporary)
        copied_results = sandbox / "results"
        copied_results.mkdir()
        for name, contents in inputs.items():
            (copied_results / name).write_bytes(contents)
        script_path = sandbox / "verify_outputs.py"
        script_path.write_bytes(script_bytes)
        command = [sys.executable, str(script_path)]
        if milestone is not None:
            command = [sys.executable, "-c", DIAGNOSTIC_CODE, str(script_path),
                       f"verify_milestone_{milestone}"]
        try:
            completed = subprocess.run(
                command, cwd=sandbox, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=timeout_seconds,
                check=False,
            )
            result = {
                "status": "pass" if completed.returncode == 0 else "fail",
                "exit_code": completed.returncode,
                "stdout": clean_output(completed.stdout),
                "stderr": clean_output(completed.stderr),
            }
        except subprocess.TimeoutExpired as error:
            result = {"status": "timeout", "exit_code": None,
                      "stdout": clean_output(error.stdout),
                      "stderr": clean_output(error.stderr),
                      "error": f"Teacher subprocess exceeded {timeout_seconds:g} seconds"}
        except OSError as error:
            result = {"status": "error", "exit_code": None,
                      "stdout": "", "stderr": "", "error": str(error)}
        receipt = copied_results / "verification_receipt.sig"
        return result, receipt.read_bytes() if receipt.is_file() else None


def validate_receipt(receipt: bytes | None, inputs: dict[str, bytes]) -> dict:
    """Check the teacher-emitted receipt against the actual copied student data."""
    if receipt is None:
        raise ValueError("Teacher exited successfully without emitting a receipt")
    params = json.loads(inputs["salted_params.json"])
    sid = str(params["student_id"]).strip()
    dimension = params["N"]
    fields = {}
    for line in receipt.decode("utf-8").splitlines():
        key, separator, value = line.partition("=")
        if not separator or key in fields:
            raise ValueError("Teacher receipt contains malformed or duplicate fields")
        fields[key] = value
    if set(fields) != {"STUDENT_ID", "SALTED_N", "SIGNATURE"}:
        raise ValueError("Teacher receipt does not contain the expected fields")
    if fields["STUDENT_ID"] != sid or fields["SALTED_N"] != str(dimension):
        raise ValueError("Teacher receipt does not match the measured student parameters")
    expected_token = sha256(
        f"CS482-PRACTICUM-VERIFIED-{sid}-{dimension}-HASH-SOLO-LAB".encode("utf-8")
    )
    if fields["SIGNATURE"] != expected_token:
        raise ValueError("Teacher receipt does not match its documented public hash formula")
    return {"status": "pass", "student_id": sid, "salted_n": dimension,
            "receipt_sha256": sha256(receipt)}


def write_report(report: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "teacher_verification.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "CSS314: unchanged teacher verifier report",
        f"Created at UTC: {report['created_at_utc']}",
        f"Teacher source: {report['teacher_script']}",
        f"Provided source: {report['provided_source_path']}",
        f"Original script SHA-256: {report['original_script_sha256']}",
        f"Source integrity: {report['source_integrity']['status']}",
        f"Overall result: {report['status']}",
        "",
        "Full teacher main (the only run that can authorize a receipt):",
    ]
    for label, result in [("FULL", report["full_run"])] + [
        (entry["milestone"], entry) for entry in report["milestone_diagnostics"]
    ]:
        lines.append(f"[{label}] status={result['status']} exit_code={result['exit_code']}")
        for stream in ("stdout", "stderr"):
            if result.get(stream):
                lines.extend([f"{stream}:", result[stream].rstrip()])
        if result.get("error"):
            lines.append(f"error: {result['error']}")
        if label == "FULL":
            lines.extend(["", "Individual milestones (diagnostics only; cannot override full failure):"])
    if report.get("error"):
        lines.extend(["", f"Runner error: {report['error']}"])
    lines.extend(["", f"Official receipt generated: {report['official_receipt_generated']}"])
    lines.extend(report["notes"])
    (output_dir / "teacher_verification.log").write_text(
        clean_output("\n".join(lines)) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=ROOT / "results",
                        help="Directory containing the actual measured metadata")
    parser.add_argument("--output-dir", type=Path,
                        help="Report/receipt destination (defaults to --results-dir)")
    parser.add_argument("--teacher-script", type=Path, default=ROOT / "verify_outputs.py")
    parser.add_argument("--provided-source", type=Path, default=ROOT / "verify_outputs.py.txt")
    parser.add_argument("--timeout-seconds", type=float, default=30)
    args = parser.parse_args(argv)
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be positive")
    results_dir = args.results_dir.resolve()
    output_dir = (args.output_dir or results_dir).resolve()
    teacher_script = args.teacher_script.resolve()
    provided_source = args.provided_source.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    official_receipt = output_dir / "verification_receipt.sig"
    # Never leave a previous success alongside a newly failed check.
    official_receipt.unlink(missing_ok=True)
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "error",
        "teacher_script": str(teacher_script),
        "provided_source_path": str(provided_source),
        "original_script_sha256": PROVIDED_SCRIPT_SHA256,
        "teacher_script_sha256": None,
        "provided_source_sha256": None,
        "results_dir": str(results_dir),
        "inputs_hashes": {},
        "source_integrity": {"status": "not_checked"},
        "full_run": {"status": "not_run", "exit_code": None, "stdout": "", "stderr": ""},
        "milestone_diagnostics": [],
        "official_receipt_generated": False,
        "notes": [
            "The teacher script is executed unchanged from a byte-for-byte temporary copy; each run reads isolated copies of the seven listed metadata files.",
            "Individual milestone runs are diagnostics only; they cannot override a failing full teacher run.",
            "No hardware measurements, classifications, or teacher checks are changed by this runner.",
            "Teacher verification checks metadata and is not hardware authentication or independent numerical-array verification.",
            "The teacher receipt is a deterministic public SHA-256 token; its formula contains no secret and does not authenticate hardware or results.",
        ],
    }
    return_code = 2
    try:
        script_bytes = teacher_script.read_bytes()
        report["teacher_script_sha256"] = sha256(script_bytes)
        if report["teacher_script_sha256"] != PROVIDED_SCRIPT_SHA256:
            report["source_integrity"]["status"] = "fail"
            raise ValueError("Teacher script differs from the exact supplied verifier; refusing execution")
        if provided_source.exists():
            supplied_bytes = provided_source.read_bytes()
            report["provided_source_sha256"] = sha256(supplied_bytes)
            if script_bytes != supplied_bytes:
                report["source_integrity"]["status"] = "fail"
                raise ValueError("Teacher script differs from the original uploaded .txt; refusing execution")
        report["source_integrity"] = {
            "status": "pass", "matched_pinned_sha256": True,
            "matched_provided_source": True if provided_source.exists() else None,
        }
        inputs = {}
        for name in INPUT_FILES:
            source = results_dir / name
            if source.is_file():
                inputs[name] = source.read_bytes()
                report["inputs_hashes"][name] = sha256(inputs[name])
            else:
                report["inputs_hashes"][name] = None
        full_run, receipt = isolated_run(script_bytes, inputs, args.timeout_seconds)
        report["full_run"] = full_run
        for milestone in range(4):
            diagnostic, _ = isolated_run(script_bytes, inputs, args.timeout_seconds, milestone)
            report["milestone_diagnostics"].append({"milestone": f"M{milestone}",
                                                      "diagnostic_only": True, **diagnostic})
        if full_run["status"] == "pass":
            report["receipt_validation"] = validate_receipt(receipt, inputs)
            official_receipt.write_bytes(receipt)
            report["official_receipt_generated"] = True
            report["status"] = "pass"
            return_code = 0
        else:
            report["status"] = "fail"
            return_code = full_run["exit_code"] if isinstance(full_run["exit_code"], int) and full_run["exit_code"] > 0 else 1
    except (OSError, ValueError, KeyError, TypeError) as error:
        report["error"] = str(error)
        official_receipt.unlink(missing_ok=True)
    write_report(report, output_dir)
    print(f"Teacher full verification: {report['status']}")
    if report.get("error"):
        print(report["error"])
    for milestone in report["milestone_diagnostics"]:
        print(f"{milestone['milestone']} diagnostic only: {milestone['status']}")
    print(f"Official receipt generated: {report['official_receipt_generated']}")
    print(f"Report: {output_dir / 'teacher_verification.json'}")
    print(f"Log: {output_dir / 'teacher_verification.log'}")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
