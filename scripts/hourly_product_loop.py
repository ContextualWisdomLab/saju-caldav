"""Run the deterministic quality sentinel used by the hourly product loop."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Record one sentinel check without including source or user data."""

    check_name: str
    check_status: str
    check_detail: str
    elapsed_seconds: float


REQUIRED_FILES = (
    "AGENTS.md",
    "CLAUDE.md",
    "CHANGELOG.md",
    "README.md",
    "docs/TRACEABILITY.md",
    "docs/adr/README.md",
    "docs/product/PRD.md",
    "docs/technical/TRD.md",
    "docs/security/THREAT_MODEL.md",
    "docs/testing/TEST_STRATEGY.md",
    "docs/operations/OPERABILITY.md",
    "docs/operations/HOURLY_PRODUCT_LOOP.md",
    "docs/doctoring/README.md",
)

COMMAND_TIMEOUT_SECONDS = 30 * 60


def _run_sentinel_command(
    repository_root: Path, check_name: str, command_arguments: list[str]
) -> CheckResult:
    """Run one bounded sentinel command and return a redacted check result."""

    start_time = time.monotonic()
    try:
        completed_process = subprocess.run(
            command_arguments,
            cwd=repository_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        elapsed_seconds = round(time.monotonic() - start_time, 3)
        return CheckResult(check_name, "fail", "command timed out", elapsed_seconds)
    elapsed_seconds = round(time.monotonic() - start_time, 3)
    if completed_process.returncode == 0:
        return CheckResult(check_name, "pass", "command completed", elapsed_seconds)
    return CheckResult(
        check_name,
        "fail",
        f"command failed (exit {completed_process.returncode})",
        elapsed_seconds,
    )


def _file_contract(repository_root: Path) -> CheckResult:
    """Check that buyer-facing and governance documents exist."""

    start_time = time.monotonic()
    missing_paths = [
        required_path
        for required_path in REQUIRED_FILES
        if not (repository_root / required_path).is_file()
    ]
    elapsed_seconds = round(time.monotonic() - start_time, 3)
    if missing_paths:
        return CheckResult(
            "document-contract",
            "fail",
            "missing: " + ", ".join(missing_paths),
            elapsed_seconds,
        )
    return CheckResult(
        "document-contract",
        "pass",
        f"{len(REQUIRED_FILES)} files present",
        elapsed_seconds,
    )


def run_quality_sentinel(repository_root: Path) -> list[CheckResult]:
    """Run documentation, lock, lint, coverage, and JavaScript syntax checks."""

    check_results = [_file_contract(repository_root)]
    if check_results[0].check_status != "pass":
        return check_results
    sentinel_commands = (
        ("lock", ["uv", "lock", "--check"]),
        ("ruff", ["uv", "run", "ruff", "check", "."]),
        ("public-docstrings", ["uv", "run", "python", "scripts/docstring_audit.py"]),
        ("coverage", ["uv", "run", "coverage", "run", "-m", "pytest", "-q"]),
        ("coverage-report", ["uv", "run", "coverage", "report"]),
        ("javascript-syntax", ["node", "--check", "app/static/app.js"]),
    )
    for check_name, command_arguments in sentinel_commands:
        check_result = _run_sentinel_command(
            repository_root, check_name, list(command_arguments)
        )
        check_results.append(check_result)
        if check_result.check_status != "pass":
            break
    return check_results


def main(command_line_arguments: list[str] | None = None) -> int:
    """Run the sentinel and print a machine-readable, PII-free result."""

    argument_parser = argparse.ArgumentParser(description=__doc__)
    argument_parser.add_argument(
        "--repository-root", type=Path, default=Path.cwd(), dest="repository_root"
    )
    argument_parser.add_argument(
        "--output-format",
        choices=("json", "text"),
        default="text",
        dest="output_format",
    )
    cli_arguments = argument_parser.parse_args(command_line_arguments)
    check_results = run_quality_sentinel(cli_arguments.repository_root.resolve())
    sentinel_payload = {
        "sentinel_status": (
            "pass"
            if all(check_result.check_status == "pass" for check_result in check_results)
            else "fail"
        ),
        "check_results": [asdict(check_result) for check_result in check_results],
    }
    if cli_arguments.output_format == "json":
        print(json.dumps(sentinel_payload, ensure_ascii=False, sort_keys=True))
    else:
        for check_result in check_results:
            print(
                f"{check_result.check_status.upper():4} "
                f"{check_result.check_name}: {check_result.check_detail}"
            )
        print(f"SENTINEL_STATUS {sentinel_payload['sentinel_status'].upper()}")
    return 0 if sentinel_payload["sentinel_status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
