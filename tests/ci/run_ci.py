#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import selectors
import subprocess
import sys
import time
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = Path(__file__).with_name("feature_manifest.json")


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-") or "check"


def _json_dump(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _artifact_kind(path: Path) -> str:
    if path.name == "ci-summary.json":
        return "stage-summary"
    if path.name == "feature-coverage.json":
        return "feature-coverage"
    if path.name == "failure-summary.json":
        return "failure-summary"
    if path.name == "artifact-manifest.json":
        return "artifact-manifest"
    if path.name == "junit.xml" or path.name.startswith("pytest-") and path.suffix == ".xml":
        return "junit"
    if path.parent.name == "logs":
        return "command-log"
    return "artifact"


def _write_artifact_manifest(stage: str, artifact_dir: Path) -> None:
    manifest_path = artifact_dir / "artifact-manifest.json"
    artifacts = []
    for path in sorted(artifact_dir.rglob("*")):
        if not path.is_file() or path == manifest_path:
            continue
        artifacts.append(
            {
                "path": _rel(path),
                "kind": _artifact_kind(path),
                "size_bytes": path.stat().st_size,
            }
        )

    artifacts.append(
        {
            "path": _rel(manifest_path),
            "kind": "artifact-manifest",
            "size_bytes": None,
        }
    )
    manifest = {
        "schema": 1,
        "stage": stage,
        "generated_by": "tests/ci/run_ci.py",
        "artifacts": artifacts,
    }
    _json_dump(manifest_path, manifest)
    artifacts[-1]["size_bytes"] = manifest_path.stat().st_size
    _json_dump(manifest_path, manifest)


def _write_failure_summary(stage: str, checks: list[dict[str, Any]], artifact_dir: Path) -> None:
    failures = []
    skipped = []
    for check in checks:
        entry = {
            "name": check["name"],
            "message": check.get("message", ""),
            "log_path": check.get("log_path", ""),
            "features": check.get("features", []),
            "examples": check.get("examples", []),
            "command": check.get("command", []),
        }
        if check["status"] == "failed":
            entry["details_tail"] = _tail(check.get("details", ""), limit=1200)
            failures.append(entry)
        elif check["status"] == "skipped":
            skipped.append(entry)

    _json_dump(
        artifact_dir / "failure-summary.json",
        {
            "schema": 1,
            "stage": stage,
            "status": "failed" if failures else "passed",
            "failed_count": len(failures),
            "skipped_count": len(skipped),
            "failures": failures,
            "skipped": skipped,
        },
    )


def _tail(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def _example_flag(example: dict[str, Any], key: str) -> bool:
    value = example.get(key, False)
    if isinstance(value, dict):
        return bool(value.get("enabled", False))
    return bool(value)


def _example_timeout(example: dict[str, Any], key: str, default: int) -> int:
    value = example.get(key, {})
    if isinstance(value, dict):
        return int(value.get("timeout", example.get("timeout", default)))
    if key == "build":
        return int(example.get("build_timeout", default))
    return int(example.get("timeout", default))


def _example_outputs(example: dict[str, Any]) -> list[str]:
    compile_config = example.get("compile", {})
    if isinstance(compile_config, dict):
        return list(compile_config.get("outputs", example.get("expected", [])))
    return list(example.get("expected", []))


def _example_runtime_probes(example: dict[str, Any]) -> list[str]:
    runtime_config = example.get("runtime", {})
    if isinstance(runtime_config, dict):
        return list(runtime_config.get("probes", []))
    return []


def _example_compose_file(example: dict[str, Any]) -> str:
    build_config = example.get("build", {})
    if isinstance(build_config, dict):
        return str(
            build_config.get(
                "compose_file", example.get("compose_file", "output/docker-compose.yml")
            )
        )
    return str(example.get("compose_file", "output/docker-compose.yml"))


def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema") != 1:
        errors.append("manifest schema must be 1")

    features = manifest.get("features", {})
    unit_groups = manifest.get("unit_groups", {})
    runtime_groups = manifest.get("runtime_groups", {})
    runtime_probes = manifest.get("runtime_probes", {})
    examples = manifest.get("examples", {})
    coverage_policy = manifest.get("coverage_policy", {})
    required_features = set(coverage_policy.get("required_features", []))
    missing = sorted(required_features.difference(features))
    if missing:
        errors.append(f"missing required feature declarations: {', '.join(missing)}")

    for feature_id, feature in features.items():
        evidence = []
        for group_id in feature.get("unit_groups", []):
            if group_id not in unit_groups:
                errors.append(f"feature {feature_id} references missing unit group {group_id}")
            else:
                evidence.append(f"unit:{group_id}")
        for group_id in feature.get("runtime_groups", []):
            if group_id not in runtime_groups:
                errors.append(f"feature {feature_id} references missing runtime group {group_id}")
            else:
                evidence.append(f"runtime:{group_id}")
        for probe_id in feature.get("runtime_probes", []):
            if probe_id not in runtime_probes:
                errors.append(f"feature {feature_id} references missing runtime probe {probe_id}")
            elif feature_id not in runtime_probes[probe_id].get("features", []):
                errors.append(
                    f"feature {feature_id} references runtime probe {probe_id} "
                    "that does not link back to the feature"
                )
            else:
                evidence.append(f"runtime-probe:{probe_id}")
        for example_id in feature.get("compile_examples", []):
            if example_id not in examples:
                errors.append(
                    f"feature {feature_id} references missing compile example {example_id}"
                )
            elif not _example_flag(examples[example_id], "compile"):
                errors.append(f"feature {feature_id} references non-compile example {example_id}")
            else:
                evidence.append(f"compile:{example_id}")
        for example_id in feature.get("build_examples", []):
            if example_id not in examples:
                errors.append(
                    f"feature {feature_id} references missing build example {example_id}"
                )
            elif not _example_flag(examples[example_id], "build"):
                errors.append(f"feature {feature_id} references non-build example {example_id}")
            else:
                evidence.append(f"build:{example_id}")
        if feature.get("status") == "covered" and coverage_policy.get(
            "covered_requires_evidence", True
        ):
            if not evidence:
                errors.append(f"feature {feature_id} is covered but declares no evidence")

    for example_id, example in examples.items():
        script = REPO_ROOT / example.get("script", "")
        if not script.is_file():
            errors.append(f"example {example_id} script does not exist: {_rel(script)}")
        for feature_id in example.get("features", []):
            if feature_id not in features:
                errors.append(f"example {example_id} references missing feature {feature_id}")
        for probe_id in _example_runtime_probes(example):
            if probe_id not in runtime_probes:
                errors.append(f"example {example_id} references missing runtime probe {probe_id}")
            elif example_id not in runtime_probes[probe_id].get("examples", []):
                errors.append(
                    f"example {example_id} references runtime probe {probe_id} "
                    "that does not link back to the example"
                )
        for expected in _example_outputs(example):
            if Path(expected).is_absolute():
                errors.append(f"example {example_id} expected path must be relative: {expected}")
        for clean in example.get("clean", []):
            if Path(clean).is_absolute():
                errors.append(f"example {example_id} clean path must be relative: {clean}")
        compose_file = _example_compose_file(example)
        if Path(compose_file).is_absolute():
            errors.append(f"example {example_id} compose file must be relative: {compose_file}")

    for probe_id, probe in runtime_probes.items():
        group_id = probe.get("group")
        if group_id not in runtime_groups:
            errors.append(f"runtime probe {probe_id} references missing group {group_id}")
        if not probe.get("pytest_args"):
            errors.append(f"runtime probe {probe_id} must declare pytest_args")
        for feature_id in probe.get("features", []):
            if feature_id not in features:
                errors.append(f"runtime probe {probe_id} references missing feature {feature_id}")
        for example_id in probe.get("examples", []):
            if example_id not in examples:
                errors.append(f"runtime probe {probe_id} references missing example {example_id}")
            elif not _example_flag(examples[example_id], "runtime"):
                errors.append(
                    f"runtime probe {probe_id} references runtime-disabled example {example_id}"
                )
    return errors


def feature_coverage(manifest: dict[str, Any]) -> dict[str, Any]:
    features = {}
    for feature_id, feature in sorted(manifest["features"].items()):
        features[feature_id] = {
            "status": feature["status"],
            "description": feature.get("description", ""),
            "unit_groups": feature.get("unit_groups", []),
            "compile_examples": feature.get("compile_examples", []),
            "build_examples": feature.get("build_examples", []),
            "runtime_groups": feature.get("runtime_groups", []),
            "runtime_probes": feature.get("runtime_probes", []),
            "notes": feature.get("notes", ""),
        }
    examples = {}
    for example_id, example in sorted(manifest["examples"].items()):
        examples[example_id] = {
            "description": example.get("description", ""),
            "features": example.get("features", []),
            "tags": example.get("tags", []),
            "compile": _example_flag(example, "compile"),
            "build": _example_flag(example, "build"),
            "runtime": _example_flag(example, "runtime"),
            "runtime_probes": _example_runtime_probes(example),
            "outputs": _example_outputs(example),
            "compose_file": _example_compose_file(example),
        }
    runtime_probes = {}
    for probe_id, probe in sorted(manifest.get("runtime_probes", {}).items()):
        runtime_probes[probe_id] = {
            "description": probe.get("description", ""),
            "group": probe.get("group", ""),
            "features": probe.get("features", []),
            "examples": probe.get("examples", []),
            "pytest_args": probe.get("pytest_args", []),
            "evidence": probe.get("evidence", []),
        }
    return {
        "schema": manifest["schema"],
        "generated_by": "tests/ci/run_ci.py",
        "coverage_policy": manifest.get("coverage_policy", {}),
        "features": features,
        "examples": examples,
        "runtime_probes": runtime_probes,
    }


def _write_feature_coverage(manifest: dict[str, Any], artifact_dir: Path) -> None:
    _json_dump(artifact_dir / "feature-coverage.json", feature_coverage(manifest))


def _write_junit(stage: str, checks: list[dict[str, Any]], path: Path) -> None:
    tests = len(checks)
    failures = sum(1 for check in checks if check["status"] == "failed")
    skipped = sum(1 for check in checks if check["status"] == "skipped")
    suite = ET.Element(
        "testsuite",
        {
            "name": f"seedemu-ci-{stage}",
            "tests": str(tests),
            "failures": str(failures),
            "errors": "0",
            "skipped": str(skipped),
            "time": f"{sum(float(check.get('duration_s', 0.0)) for check in checks):.3f}",
        },
    )
    for check in checks:
        case = ET.SubElement(
            suite,
            "testcase",
            {
                "classname": f"seedemu.ci.{stage}",
                "name": check["name"],
                "time": f"{float(check.get('duration_s', 0.0)):.3f}",
            },
        )
        if check["status"] == "failed":
            failure = ET.SubElement(
                case,
                "failure",
                {
                    "message": check.get("message", "check failed"),
                    "type": "CommandFailure",
                },
            )
            failure.text = check.get("details", "")
        elif check["status"] == "skipped":
            skipped_node = ET.SubElement(
                case, "skipped", {"message": check.get("message", "skipped")}
            )
            skipped_node.text = check.get("details", "")
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def _stage_result(stage: str, checks: list[dict[str, Any]], artifact_dir: Path) -> int:
    summary = {
        "stage": stage,
        "status": "failed" if any(check["status"] == "failed" for check in checks) else "passed",
        "checks": checks,
    }
    _json_dump(artifact_dir / "ci-summary.json", summary)
    _write_junit(stage, checks, artifact_dir / "junit.xml")
    _write_failure_summary(stage, checks, artifact_dir)
    _write_artifact_manifest(stage, artifact_dir)

    print(f"[seed-ci] stage={stage} status={summary['status']} artifact_dir={_rel(artifact_dir)}")
    for check in checks:
        print(f"[seed-ci] {check['status']}: {check['name']} log={check.get('log_path', '')}")
        if check["status"] == "failed":
            command = check.get("command")
            if command:
                print(f"[seed-ci] failed-command: {' '.join(command)}")
            details = (check.get("stderr_tail") or check.get("details") or "").strip()
            if details:
                print("[seed-ci] failure-tail:")
                print(_tail(details, limit=1200))
    return 1 if summary["status"] == "failed" else 0


def _run_command(
    name: str,
    cmd: list[str],
    artifact_dir: Path,
    *,
    cwd: Path = REPO_ROOT,
    env: dict[str, str] | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    start = time.monotonic()
    log_path = artifact_dir / "logs" / f"{_slug(name)}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with log_path.open("w", encoding="utf-8") as log:
            log.write("COMMAND: {}\nCWD: {}\n\n".format(" ".join(cmd), _rel(cwd)))
            log.flush()
            process = subprocess.Popen(
                cmd,
                cwd=str(cwd),
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,
            )
            stdout_tail = ""
            stderr_tail = ""
            sel = selectors.DefaultSelector()
            assert process.stdout is not None
            assert process.stderr is not None
            sel.register(process.stdout, selectors.EVENT_READ, "stdout")
            sel.register(process.stderr, selectors.EVENT_READ, "stderr")
            timed_out = False
            deadline = None if timeout is None else start + timeout
            while sel.get_map():
                if deadline is None:
                    wait = 1.0
                else:
                    wait = max(0.0, min(1.0, deadline - time.monotonic()))
                    if wait == 0.0:
                        timed_out = True
                        process.kill()
                for key, _ in sel.select(wait):
                    line = key.fileobj.readline()
                    if not line:
                        sel.unregister(key.fileobj)
                        continue
                    stream_name = key.data
                    log.write(f"[{stream_name}] {line}")
                    if stream_name == "stdout":
                        stdout_tail = _tail(stdout_tail + line)
                    else:
                        stderr_tail = _tail(stderr_tail + line)
                if timed_out:
                    break
            returncode = process.wait()
            if timed_out:
                returncode = -1
            duration = time.monotonic() - start
            log.write(f"\nEXIT: {returncode}\n")
            if timed_out:
                log.write(f"TIMEOUT: {timeout}s\n")
        duration = time.monotonic() - start
        status = "passed" if returncode == 0 else "failed"
        message = "command passed"
        if timed_out:
            message = f"command timed out after {timeout}s"
        elif status == "failed":
            message = "command failed"
        return {
            "name": name,
            "status": status,
            "command": cmd,
            "cwd": _rel(cwd),
            "returncode": returncode,
            "duration_s": duration,
            "log_path": _rel(log_path),
            "stdout_tail": stdout_tail,
            "stderr_tail": stderr_tail,
            "message": message,
            "details": _tail(stdout_tail + "\n" + stderr_tail),
        }
    except (
        Exception
    ) as exc:  # pragma: no cover - defensive diagnostics for CI infrastructure failures.
        duration = time.monotonic() - start
        details = traceback.format_exc()
        log_path.write_text(details, encoding="utf-8")
        return {
            "name": name,
            "status": "failed",
            "command": cmd,
            "cwd": _rel(cwd),
            "returncode": None,
            "duration_s": duration,
            "log_path": _rel(log_path),
            "message": str(exc),
            "details": details,
        }


def _git_diff_check_command() -> list[str]:
    base_ref = os.environ.get("GITHUB_BASE_REF")
    if base_ref:
        candidates = [f"origin/{base_ref}", base_ref]
        for candidate in candidates:
            probe = subprocess.run(
                ["git", "rev-parse", "--verify", candidate],
                cwd=str(REPO_ROOT),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if probe.returncode == 0:
                return ["git", "diff", "--check", f"{candidate}...HEAD"]
    return ["git", "diff", "--check"]


def _docker_compose_command() -> list[str]:
    docker_compose = subprocess.run(
        ["docker", "compose", "version"],
        cwd=str(REPO_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if docker_compose.returncode == 0:
        return ["docker", "compose"]
    legacy_compose = shutil.which("docker-compose")
    if legacy_compose:
        return [legacy_compose]
    return ["docker", "compose"]


def _example_ids(manifest: dict[str, Any], key: str) -> list[str]:
    ids: list[str] = []
    for example_id, example in manifest["examples"].items():
        if _example_flag(example, key):
            ids.append(example_id)
    return ids


def _selected_unit_group_ids(
    manifest: dict[str, Any], groups: Sequence[str], features: Sequence[str]
) -> list[str]:
    selected = set(groups)
    for feature_id in features:
        if feature_id not in manifest["features"]:
            continue
        selected.update(manifest["features"][feature_id].get("unit_groups", []))
    ids = list(manifest["unit_groups"])
    if selected:
        ids = [group_id for group_id in ids if group_id in selected]
    return ids


def _selected_runtime_group_ids(
    manifest: dict[str, Any], groups: Sequence[str], features: Sequence[str]
) -> list[str]:
    selected = set(groups)
    for feature_id in features:
        if feature_id not in manifest["features"]:
            continue
        selected.update(manifest["features"][feature_id].get("runtime_groups", []))
    ids = list(manifest["runtime_groups"])
    if selected:
        ids = [group_id for group_id in ids if group_id in selected]
    return ids


def _selected_runtime_probe_ids(
    manifest: dict[str, Any],
    groups: Sequence[str],
    features: Sequence[str],
    examples: Sequence[str],
) -> list[str]:
    group_filter = set(groups)
    feature_filter = set(features)
    example_filter = set(examples)
    selected: list[str] = []
    for probe_id, probe in manifest.get("runtime_probes", {}).items():
        if group_filter and probe.get("group") not in group_filter:
            continue
        if feature_filter or example_filter:
            probe_features = set(probe.get("features", []))
            probe_examples = set(probe.get("examples", []))
            if feature_filter.isdisjoint(probe_features) and example_filter.isdisjoint(
                probe_examples
            ):
                continue
        selected.append(probe_id)
    return selected


def _selected_example_ids(
    manifest: dict[str, Any],
    key: str,
    examples: Sequence[str],
    features: Sequence[str],
) -> list[str]:
    selected = set(examples)
    feature_set = set(features)
    for feature_id in features:
        if feature_id not in manifest["features"]:
            continue
        feature = manifest["features"][feature_id]
        if key == "compile":
            selected.update(feature.get("compile_examples", []))
        elif key == "build":
            selected.update(feature.get("build_examples", []))
        elif key == "runtime":
            for probe_id in feature.get("runtime_probes", []):
                selected.update(
                    manifest.get("runtime_probes", {}).get(probe_id, {}).get("examples", [])
                )
    ids = _example_ids(manifest, key)
    if feature_set:
        ids = [
            example_id
            for example_id in ids
            if example_id in selected
            or feature_set.intersection(manifest["examples"][example_id].get("features", []))
        ]
    elif selected:
        ids = [example_id for example_id in ids if example_id in selected]
    return ids


def _validate_selectors(
    manifest: dict[str, Any],
    *,
    groups: Sequence[str],
    features: Sequence[str],
    examples: Sequence[str],
) -> list[str]:
    errors: list[str] = []
    for feature_id in features:
        if feature_id not in manifest["features"]:
            errors.append(f"unknown feature selector: {feature_id}")
    all_groups = set(manifest.get("unit_groups", {})) | set(manifest.get("runtime_groups", {}))
    for group_id in groups:
        if group_id not in all_groups:
            errors.append(f"unknown group selector: {group_id}")
    for example_id in examples:
        if example_id not in manifest["examples"]:
            errors.append(f"unknown example selector: {example_id}")
    return errors


def _selector_check(errors: list[str]) -> dict[str, Any] | None:
    if not errors:
        return None
    return {
        "name": "selectors",
        "status": "failed",
        "duration_s": 0.0,
        "message": "selector validation failed",
        "details": "\n".join(errors),
        "log_path": "",
    }


def _runtime_no_probe_check(
    *, features: Sequence[str], examples: Sequence[str], groups: Sequence[str]
) -> dict[str, Any]:
    return {
        "name": "runtime-probe-selection",
        "status": "skipped",
        "duration_s": 0.0,
        "message": "no runtime probe matches the selected feature/example/group",
        "details": json.dumps(
            {
                "features": list(features),
                "examples": list(examples),
                "groups": list(groups),
            },
            sort_keys=True,
        ),
        "features": list(features),
        "examples": list(examples),
        "log_path": "",
    }


def _pythonpath_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(REPO_ROOT) if not existing else f"{REPO_ROOT}:{existing}"
    env.setdefault("DOCKER_BUILDKIT", "0")
    env.setdefault("COMPOSE_BAKE", "false")
    env.setdefault("COMPOSE_PARALLEL_LIMIT", "1")
    if extra:
        env.update(extra)
    return env


def _pytest_env() -> dict[str, str]:
    return _pythonpath_env({"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"})


def _safe_clean(example_dir: Path, relative_paths: Iterable[str]) -> None:
    base = example_dir.resolve()
    for item in relative_paths:
        target = (example_dir / item).resolve()
        if target == base or base not in target.parents:
            raise ValueError(f"refusing to clean path outside example directory: {target}")
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()


def _compile_example(
    example_id: str,
    example: dict[str, Any],
    artifact_dir: Path,
    *,
    clean: bool,
    name_prefix: str = "compile",
) -> dict[str, Any]:
    script = REPO_ROOT / example["script"]
    example_dir = script.parent
    if clean:
        _safe_clean(example_dir, example.get("clean", []))
    cmd = [sys.executable, script.name] + list(example.get("args", []))
    check = _run_command(
        f"{name_prefix}:{example_id}",
        cmd,
        artifact_dir,
        cwd=example_dir,
        env=_pythonpath_env(example.get("env", {})),
        timeout=_example_timeout(example, "compile", 900),
    )
    if check["status"] != "passed":
        return check

    missing = [item for item in _example_outputs(example) if not (example_dir / item).exists()]
    if missing:
        check["status"] = "failed"
        check["message"] = "expected compile outputs are missing"
        check["details"] = "Missing outputs: " + ", ".join(missing)
    return check


def _import_smoke_code(manifest: dict[str, Any]) -> str:
    imports = manifest.get("static", {}).get("import_smoke", [])
    statements: list[str] = []
    for item in imports:
        if isinstance(item, str):
            statements.append(f"import {item}")
        elif "statement" in item:
            statements.append(item["statement"])
        else:
            module = item["module"]
            names = ", ".join(item.get("names", []))
            if names:
                statements.append(f"from {module} import {names}")
            else:
                statements.append(f"import {module}")
    return "; ".join(statements)


def run_static(
    artifact_dir: Path, *, features: Sequence[str], examples: Sequence[str], groups: Sequence[str]
) -> int:
    manifest = load_manifest()
    checks: list[dict[str, Any]] = []

    errors = _validate_manifest(manifest)
    errors.extend(
        _validate_selectors(manifest, groups=groups, features=features, examples=examples)
    )
    _write_feature_coverage(manifest, artifact_dir)
    checks.append(
        {
            "name": "manifest",
            "status": "failed" if errors else "passed",
            "duration_s": 0.0,
            "message": "manifest validation failed" if errors else "manifest validation passed",
            "details": "\n".join(errors),
            "log_path": _rel(artifact_dir / "feature-coverage.json"),
        }
    )

    checks.append(_run_command("whitespace", _git_diff_check_command(), artifact_dir))

    static_config = manifest.get("static", {})
    compile_targets = list(static_config.get("compile_targets", ["seedemu", "tests/ci"]))
    example_dirs = sorted(
        {
            str(Path(manifest["examples"][example_id]["script"]).parent)
            for example_id in _selected_example_ids(manifest, "compile", examples, features)
        }
    )
    compile_targets.extend(example_dirs)
    compile_exclude = static_config.get(
        "compile_exclude", "seedemu/services/EthereumService/EthTemplates/"
    )
    checks.append(
        _run_command(
            "compileall",
            [
                sys.executable,
                "-m",
                "compileall",
                "-q",
                "-x",
                compile_exclude,
            ]
            + compile_targets,
            artifact_dir,
        )
    )

    smoke = _import_smoke_code(manifest)
    checks.append(
        _run_command(
            "import-smoke", [sys.executable, "-c", smoke], artifact_dir, env=_pythonpath_env()
        )
    )
    return _stage_result("static", checks, artifact_dir)


def run_unit(
    artifact_dir: Path, *, features: Sequence[str], groups: Sequence[str], examples: Sequence[str]
) -> int:
    manifest = load_manifest()
    _write_feature_coverage(manifest, artifact_dir)
    checks: list[dict[str, Any]] = []
    selector_check = _selector_check(
        _validate_selectors(manifest, groups=groups, features=features, examples=examples)
    )
    if selector_check:
        checks.append(selector_check)
        return _stage_result("unit", checks, artifact_dir)
    for group_id in _selected_unit_group_ids(manifest, groups, features):
        group = manifest["unit_groups"][group_id]
        junit_path = artifact_dir / f"pytest-{_slug(group_id)}.xml"
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            f"--junitxml={junit_path}",
        ] + list(group["pytest_args"])
        checks.append(
            _run_command(f"pytest:{group_id}", cmd, artifact_dir, env=_pytest_env(), timeout=900)
        )
    return _stage_result("unit", checks, artifact_dir)


def run_example_compile(
    artifact_dir: Path, *, features: Sequence[str], examples: Sequence[str], groups: Sequence[str]
) -> int:
    manifest = load_manifest()
    _write_feature_coverage(manifest, artifact_dir)
    selector_check = _selector_check(
        _validate_selectors(manifest, groups=groups, features=features, examples=examples)
    )
    if selector_check:
        return _stage_result("example-compile", [selector_check], artifact_dir)
    checks = [
        _compile_example(example_id, manifest["examples"][example_id], artifact_dir, clean=True)
        for example_id in _selected_example_ids(manifest, "compile", examples, features)
    ]
    return _stage_result("example-compile", checks, artifact_dir)


def _missing_compose_check(example_id: str, compose_file: Path) -> dict[str, Any]:
    return {
        "name": f"compose:{example_id}",
        "status": "failed",
        "duration_s": 0.0,
        "message": "compose file is missing before docker build",
        "details": f"Missing compose file: {_rel(compose_file)}",
        "log_path": "",
    }


def run_example_build(
    artifact_dir: Path, *, features: Sequence[str], examples: Sequence[str], groups: Sequence[str]
) -> int:
    manifest = load_manifest()
    _write_feature_coverage(manifest, artifact_dir)
    checks: list[dict[str, Any]] = []
    selector_check = _selector_check(
        _validate_selectors(manifest, groups=groups, features=features, examples=examples)
    )
    if selector_check:
        checks.append(selector_check)
        return _stage_result("example-build", checks, artifact_dir)
    for example_id in _selected_example_ids(manifest, "build", examples, features):
        example = manifest["examples"][example_id]
        compile_check = _compile_example(
            example_id,
            example,
            artifact_dir,
            clean=True,
            name_prefix="compile-before-build",
        )
        checks.append(compile_check)
        if compile_check["status"] != "passed":
            continue

        script = REPO_ROOT / example["script"]
        compose_file = script.parent / _example_compose_file(example)
        if not compose_file.is_file():
            checks.append(_missing_compose_check(example_id, compose_file))
            continue
        checks.append(
            _run_command(
                f"docker-build:{example_id}",
                _docker_compose_command() + ["-f", str(compose_file), "build"],
                artifact_dir,
                env=_pythonpath_env(example.get("env", {})),
                timeout=_example_timeout(example, "build", 1800),
            )
        )
    return _stage_result("example-build", checks, artifact_dir)


def run_runtime_integration(
    artifact_dir: Path, *, features: Sequence[str], groups: Sequence[str], examples: Sequence[str]
) -> int:
    manifest = load_manifest()
    _write_feature_coverage(manifest, artifact_dir)
    checks: list[dict[str, Any]] = []
    selector_check = _selector_check(
        _validate_selectors(manifest, groups=groups, features=features, examples=examples)
    )
    if selector_check:
        checks.append(selector_check)
        return _stage_result("runtime-integration", checks, artifact_dir)

    probe_ids = _selected_runtime_probe_ids(manifest, groups, features, examples)
    for probe_id in probe_ids:
        probe = manifest["runtime_probes"][probe_id]
        junit_path = artifact_dir / f"pytest-{_slug(probe_id)}.xml"
        group = manifest["runtime_groups"][probe["group"]]
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            f"--junitxml={junit_path}",
        ] + list(probe["pytest_args"])
        check = _run_command(
            f"runtime-probe:{probe_id}",
            cmd,
            artifact_dir,
            env=_pytest_env(),
            timeout=int(probe.get("timeout", group.get("timeout", 7200))),
        )
        check["features"] = probe.get("features", [])
        check["examples"] = probe.get("examples", [])
        checks.append(check)
    if checks:
        return _stage_result("runtime-integration", checks, artifact_dir)
    if features or examples:
        checks.append(
            _runtime_no_probe_check(features=features, examples=examples, groups=groups)
        )
        return _stage_result("runtime-integration", checks, artifact_dir)

    for group_id in _selected_runtime_group_ids(manifest, groups, features):
        group = manifest["runtime_groups"][group_id]
        junit_path = artifact_dir / f"pytest-{_slug(group_id)}.xml"
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            f"--junitxml={junit_path}",
        ] + list(group["pytest_args"])
        checks.append(
            _run_command(f"runtime:{group_id}", cmd, artifact_dir, env=_pytest_env(), timeout=7200)
        )
    return _stage_result("runtime-integration", checks, artifact_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run feature-oriented SEED Emulator CI stages.")
    parser.add_argument(
        "stage",
        choices=["static", "unit", "example-compile", "example-build", "runtime-integration"],
    )
    parser.add_argument(
        "--artifact-dir",
        default="ci-artifacts",
        help="Directory for logs, JSON, and JUnit output.",
    )
    parser.add_argument(
        "--feature", action="append", default=[], help="Only run evidence linked to this feature."
    )
    parser.add_argument(
        "--example", action="append", default=[], help="Only run this example evidence."
    )
    parser.add_argument(
        "--group", action="append", default=[], help="Only run this unit or runtime group."
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifact_dir = (REPO_ROOT / args.artifact_dir).resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    if args.stage == "static":
        return run_static(
            artifact_dir, features=args.feature, examples=args.example, groups=args.group
        )
    if args.stage == "unit":
        return run_unit(
            artifact_dir, features=args.feature, groups=args.group, examples=args.example
        )
    if args.stage == "example-compile":
        return run_example_compile(
            artifact_dir, features=args.feature, examples=args.example, groups=args.group
        )
    if args.stage == "example-build":
        return run_example_build(
            artifact_dir, features=args.feature, examples=args.example, groups=args.group
        )
    if args.stage == "runtime-integration":
        return run_runtime_integration(
            artifact_dir, features=args.feature, groups=args.group, examples=args.example
        )
    raise AssertionError(f"unknown stage: {args.stage}")


if __name__ == "__main__":
    raise SystemExit(main())
