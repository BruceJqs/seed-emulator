#!/usr/bin/env python3
"""Minimal scorer skeleton for the BGP route leak benchmark package.

The first implementation should replace the placeholder evidence reader with
SeedOps replay artifacts. Keeping this file executable now lets package tooling
validate that a scenario has a deterministic scoring entry point.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCENARIO_DIR = Path(__file__).resolve().parent
ORACLE_PATH = SCENARIO_DIR / "oracle.json"
REPLAY_DIR = SCENARIO_DIR / "replay"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as infile:
        return json.load(infile)


def artifact_exists(name: str) -> bool:
    return (REPLAY_DIR / name).exists()


def score() -> dict[str, Any]:
    oracle = load_json(ORACLE_PATH)
    required_artifacts = [
        "route_summary.before.json",
        "client_probe.before.json",
        "route_summary.during.json",
        "client_probe.during.json",
        "route_summary.after.json",
        "client_probe.after.json",
        "rollback_event.json",
    ]
    present = [name for name in required_artifacts if artifact_exists(name)]
    missing = [name for name in required_artifacts if name not in present]

    # This is intentionally conservative until route artifacts have a stable
    # schema. A package with no replay data should never look successful.
    replay_completeness = int(30 * len(present) / len(required_artifacts))
    total = replay_completeness

    return {
        "scenario_id": oracle.get("scenario_id", "incident.bgp_route_leak_optimizer.v1"),
        "score_total": total,
        "score_max": 100,
        "status": "incomplete" if missing else "needs_semantic_route_checks",
        "artifact_score": replay_completeness,
        "present_artifacts": present,
        "missing_artifacts": missing,
        "next_required_implementation": [
            "parse route summaries for origin ASN and AS path",
            "parse client probe success before/during/after",
            "apply forbidden-action penalties from action log",
            "grade evidence chain from agent report",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(score(), indent=2, sort_keys=True))
