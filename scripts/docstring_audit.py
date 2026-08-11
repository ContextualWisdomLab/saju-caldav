"""Fail when a public Python definition under ``app`` lacks a docstring."""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path


def missing_docstrings(root: Path) -> list[str]:
    """Return stable ``path:line:name`` entries for undocumented public definitions."""

    missing: list[str] = []
    for path in sorted((root / "app").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("_") or ast.get_docstring(node) is not None:
                continue
            missing.append(f"{path.relative_to(root)}:{node.lineno}:{node.name}")
    return missing


def main(argv: list[str] | None = None) -> int:
    """Print missing public docstrings and return a verifier-friendly exit code."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    missing = missing_docstrings(args.root.resolve())
    if missing:
        print("\n".join(missing), file=sys.stderr)
        return 1
    print("public docstrings: pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
