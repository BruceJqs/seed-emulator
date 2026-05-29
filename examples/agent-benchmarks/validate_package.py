#!/usr/bin/env python3
"""Validate SEED Agent benchmark package contracts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _common.benchmark_package import BenchmarkPackage


def iter_packages(root: Path) -> list[Path]:
    if (root / "package.yaml").exists():
        return [root]
    return sorted(path.parent for path in root.rglob("package.yaml"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate SEED Agent benchmark packages")
    parser.add_argument(
        "path",
        nargs="?",
        default=Path(__file__).resolve().parent,
        type=Path,
        help="package directory or benchmark root",
    )
    parser.add_argument("--run-scorer", action="store_true", help="execute each package scorer")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args()

    package_dirs = iter_packages(args.path.resolve())
    if not package_dirs:
        print(f"No benchmark packages found under {args.path}", file=sys.stderr)
        return 1

    results = [BenchmarkPackage(path).validate(run_scorer=args.run_scorer) for path in package_dirs]
    payload = {
        "ok": all(result.ok for result in results),
        "package_count": len(results),
        "results": [result.as_dict() for result in results],
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for result in results:
            status = "ok" if result.ok else "failed"
            print(f"{status}: {result.package_dir}")
            for warning in result.warnings:
                print(f"  warning: {warning}")
            for error in result.errors:
                print(f"  error: {error}")
            if result.scorer_result is not None:
                score = result.scorer_result.get("score_total")
                max_score = result.scorer_result.get("score_max")
                scorer_status = result.scorer_result.get("status")
                print(f"  scorer: {score}/{max_score} {scorer_status}")

    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
