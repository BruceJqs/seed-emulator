from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path


RUN_CI_PATH = Path(__file__).parent / "tests" / "ci" / "run_ci.py"
SPEC = importlib.util.spec_from_file_location("seedemu_ci_runner_under_test", RUN_CI_PATH)
assert SPEC is not None
assert SPEC.loader is not None
run_ci = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(run_ci)


def test_feature_selector_uses_manifest_examples() -> None:
    manifest = run_ci.load_manifest()

    assert run_ci._selected_example_ids(manifest, "compile", [], ["routing-bird-frr"]) == [
        "basic-a12-bgp-mixed-backend"
    ]
    assert run_ci._selected_example_ids(manifest, "compile", ["basic-a00-simple-as"], []) == [
        "basic-a00-simple-as"
    ]


def test_runtime_probe_selector_uses_manifest_features_and_examples() -> None:
    manifest = run_ci.load_manifest()

    assert run_ci._selected_runtime_probe_ids(manifest, [], ["looking-glass"], []) == [
        "a14-looking-glass"
    ]
    assert run_ci._selected_runtime_probe_ids(
        manifest, [], [], ["basic-a13-exabgp-control-plane"]
    ) == ["a13-exabgp-service"]
    assert run_ci._selected_example_ids(manifest, "runtime", [], ["routing-bird-frr"]) == [
        "basic-a12-bgp-mixed-backend"
    ]


def test_covered_feature_requires_declared_evidence() -> None:
    manifest = copy.deepcopy(run_ci.load_manifest())
    manifest["coverage_policy"]["required_features"].append("empty-covered-feature")
    manifest["features"]["empty-covered-feature"] = {
        "status": "covered",
        "description": "Invalid covered feature without evidence.",
        "unit_groups": [],
        "compile_examples": [],
        "build_examples": [],
        "runtime_groups": [],
    }

    assert (
        "feature empty-covered-feature is covered but declares no evidence"
        in run_ci._validate_manifest(manifest)
    )


def test_run_command_streams_output_to_log(tmp_path) -> None:
    check = run_ci._run_command(
        "stream-smoke",
        [sys.executable, "-c", "print('hello from stdout')"],
        tmp_path,
    )

    assert check["status"] == "passed"
    log_path = run_ci.REPO_ROOT / check["log_path"]
    assert "[stdout] hello from stdout" in log_path.read_text(encoding="utf-8")


def test_stage_result_writes_ai_ready_artifacts(tmp_path) -> None:
    result = run_ci._stage_result(
        "unit",
        [
            {
                "name": "failing-check",
                "status": "failed",
                "duration_s": 0.0,
                "message": "intentional failure",
                "details": "failure details",
                "features": ["example-feature"],
                "examples": ["example-id"],
                "command": ["false"],
                "log_path": "logs/failing-check.log",
            }
        ],
        tmp_path,
    )

    assert result == 1
    failure_summary = json.loads((tmp_path / "failure-summary.json").read_text())
    assert failure_summary["failed_count"] == 1
    assert failure_summary["failures"][0]["features"] == ["example-feature"]

    artifact_manifest = json.loads((tmp_path / "artifact-manifest.json").read_text())
    kinds = {artifact["kind"] for artifact in artifact_manifest["artifacts"]}
    assert {"stage-summary", "junit", "failure-summary", "artifact-manifest"}.issubset(kinds)


def test_docker_compose_command_falls_back_to_legacy_binary(monkeypatch) -> None:
    class Result:
        returncode = 1

    monkeypatch.setattr(run_ci.subprocess, "run", lambda *args, **kwargs: Result())
    monkeypatch.setattr(run_ci.shutil, "which", lambda name: "/usr/local/bin/docker-compose")

    assert run_ci._docker_compose_command() == ["/usr/local/bin/docker-compose"]
