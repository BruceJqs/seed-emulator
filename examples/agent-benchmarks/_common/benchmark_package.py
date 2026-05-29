"""Shared loader and validator for SEED Agent benchmark packages."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - dependency error path
    yaml = None
    YAML_IMPORT_ERROR = exc
else:
    YAML_IMPORT_ERROR = None


REQUIRED_DECLARED_FILES = {
    "case",
    "topology",
    "normal_state",
    "fault_injection",
    "agent_policy",
    "oracle",
    "scorer",
    "runbook",
    "replay_dir",
}

REQUIRED_STAGES = ["baseline", "inject", "observe", "propose", "gate", "act", "verify", "score"]


@dataclass
class ValidationResult:
    package_dir: Path
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    loaded_files: list[str] = field(default_factory=list)
    scorer_result: dict[str, Any] | None = None

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "package_dir": str(self.package_dir),
            "ok": self.ok,
            "errors": self.errors,
            "warnings": self.warnings,
            "loaded_files": self.loaded_files,
            "scorer_result": self.scorer_result,
        }


class BenchmarkPackage:
    def __init__(self, package_dir: Path):
        self.package_dir = package_dir.resolve()
        self.package_path = self.package_dir / "package.yaml"
        self.package = self._load_yaml(self.package_path)

    @staticmethod
    def _load_yaml(path: Path) -> dict[str, Any]:
        if yaml is None:
            raise RuntimeError(f"PyYAML is required: {YAML_IMPORT_ERROR}")
        with path.open("r", encoding="utf-8") as infile:
            loaded = yaml.safe_load(infile) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"{path} must contain a YAML mapping")
        return loaded

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as infile:
            loaded = json.load(infile)
        if not isinstance(loaded, dict):
            raise ValueError(f"{path} must contain a JSON object")
        return loaded

    def declared_files(self) -> dict[str, Path]:
        files = self.package.get("files") or {}
        if not isinstance(files, dict):
            return {}
        return {key: self.package_dir / str(value) for key, value in files.items()}

    def validate(self, run_scorer: bool = False) -> ValidationResult:
        result = ValidationResult(package_dir=self.package_dir)

        if not self.package_path.exists():
            result.errors.append("missing package.yaml")
            return result

        self._validate_package_metadata(result)
        self._validate_declared_files(result)
        self._validate_oracle_consistency(result)
        self._validate_policy(result)

        if run_scorer:
            self._run_scorer(result)

        return result

    def _validate_package_metadata(self, result: ValidationResult) -> None:
        scenario = self.package.get("scenario") or {}
        if not isinstance(scenario, dict):
            result.errors.append("scenario must be a mapping")
            return

        scenario_id = scenario.get("id")
        family = scenario.get("family")
        if not scenario_id:
            result.errors.append("scenario.id is required")
        if not family:
            result.errors.append("scenario.family is required")
        if scenario_id and family and not str(scenario_id).startswith(f"{family}."):
            result.errors.append("scenario.id must start with '<family>.'")

        stages = self.package.get("stages") or []
        if stages != REQUIRED_STAGES:
            result.errors.append(f"stages must be exactly {REQUIRED_STAGES}")

    def _validate_declared_files(self, result: ValidationResult) -> None:
        declared = self.declared_files()
        missing_keys = sorted(REQUIRED_DECLARED_FILES - set(declared))
        if missing_keys:
            result.errors.append(f"files missing keys: {missing_keys}")

        for key, path in sorted(declared.items()):
            if key == "replay_dir":
                if not path.is_dir():
                    result.errors.append(f"declared replay_dir does not exist: {path}")
                continue

            if not path.is_file():
                result.errors.append(f"declared file missing for {key}: {path}")
                continue

            result.loaded_files.append(str(path.relative_to(self.package_dir)))
            try:
                if path.suffix in {".yaml", ".yml"}:
                    self._load_yaml(path)
                elif path.suffix == ".json":
                    self._load_json(path)
            except Exception as exc:
                result.errors.append(f"failed to parse {path.name}: {exc}")

    def _validate_oracle_consistency(self, result: ValidationResult) -> None:
        declared = self.declared_files()
        oracle_path = declared.get("oracle")
        if not oracle_path or not oracle_path.exists():
            return

        try:
            oracle = self._load_json(oracle_path)
        except Exception:
            return

        scenario_id = (self.package.get("scenario") or {}).get("id")
        if oracle.get("scenario_id") != scenario_id:
            result.errors.append("oracle.scenario_id must match package scenario.id")

        for key in ["required_findings", "valid_repairs", "postchecks", "forbidden_actions"]:
            value = oracle.get(key)
            if not isinstance(value, list) or not value:
                result.errors.append(f"oracle.{key} must be a non-empty list")

    def _validate_policy(self, result: ValidationResult) -> None:
        declared = self.declared_files()
        policy_path = declared.get("agent_policy")
        if not policy_path or not policy_path.exists():
            return

        try:
            policy = self._load_yaml(policy_path)
        except Exception:
            return

        default_variant = policy.get("default_variant")
        variants = policy.get("variants") or {}
        if default_variant not in variants:
            result.errors.append("agent_policy.default_variant must exist in variants")
        if not policy.get("global_forbidden_actions"):
            result.errors.append("agent_policy.global_forbidden_actions must be non-empty")
        if not policy.get("evidence_requirements"):
            result.errors.append("agent_policy.evidence_requirements must be non-empty")

    def _run_scorer(self, result: ValidationResult) -> None:
        scorer_path = self.declared_files().get("scorer")
        if not scorer_path or not scorer_path.exists():
            result.errors.append("cannot run scorer: scorer file missing")
            return

        completed = subprocess.run(
            [sys.executable, "-B", str(scorer_path)],
            check=False,
            cwd=str(self.package_dir),
            text=True,
            capture_output=True,
        )
        if completed.returncode != 0:
            result.errors.append(f"scorer failed with exit code {completed.returncode}: {completed.stderr}")
            return

        try:
            result.scorer_result = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            result.errors.append(f"scorer output is not JSON: {exc}")
