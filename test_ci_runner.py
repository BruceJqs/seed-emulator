from __future__ import annotations

import copy
import importlib.util
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


def test_docker_compose_command_falls_back_to_legacy_binary(monkeypatch) -> None:
    class Result:
        returncode = 1

    monkeypatch.setattr(run_ci.subprocess, "run", lambda *args, **kwargs: Result())
    monkeypatch.setattr(run_ci.shutil, "which", lambda name: "/usr/local/bin/docker-compose")

    assert run_ci._docker_compose_command() == ["/usr/local/bin/docker-compose"]
