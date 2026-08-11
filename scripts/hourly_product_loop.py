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

    name: str
    status: str
    detail: str
    seconds: float


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


def _run(root: Path, name: str, command: list[str]) -> CheckResult:
    """Run one bounded command and return a redacted summary."""

    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        seconds = round(time.monotonic() - started, 3)
        return CheckResult(name, "fail", "command timed out", seconds)
    seconds = round(time.monotonic() - started, 3)
    if completed.returncode == 0:
        return CheckResult(name, "pass", "command completed", seconds)
    return CheckResult(name, "fail", f"command failed (exit {completed.returncode})", seconds)


def _file_contract(root: Path) -> CheckResult:
    """Check that buyer-facing and governance documents exist."""

    started = time.monotonic()
    missing = [path for path in REQUIRED_FILES if not (root / path).is_file()]
    seconds = round(time.monotonic() - started, 3)
    if missing:
        return CheckResult("document-contract", "fail", "missing: " + ", ".join(missing), seconds)
    return CheckResult("document-contract", "pass", f"{len(REQUIRED_FILES)} files present", seconds)


def run(root: Path) -> list[CheckResult]:
    """Run documentation, lock, lint, coverage, and JavaScript syntax checks."""

    results = [_file_contract(root)]
    if results[0].status != "pass":
        return results
    commands = (
        ("lock", ["uv", "lock", "--check"]),
        ("ruff", ["uv", "run", "ruff", "check", "."]),
        ("public-docstrings", ["uv", "run", "python", "scripts/docstring_audit.py"]),
        ("coverage", ["uv", "run", "coverage", "run", "-m", "pytest", "-q"]),
        ("coverage-report", ["uv", "run", "coverage", "report"]),
        ("javascript-syntax", ["node", "--check", "app/static/app.js"]),
    )
    for name, command in commands:
        result = _run(root, name, list(command))
        results.append(result)
        if result.status != "pass":
            break
    return results


def main(argv: list[str] | None = None) -> int:
    """Run the sentinel and print a machine-readable, PII-free result."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--format", choices=("json", "text"), default="text")
    args = parser.parse_args(argv)
    results = run(args.root.resolve())
    payload = {
        "status": "pass" if all(item.status == "pass" for item in results) else "fail",
        "checks": [asdict(item) for item in results],
    }
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        for result in results:
            print(f"{result.status.upper():4} {result.name}: {result.detail}")
        print(f"STATUS {payload['status'].upper()}")
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
