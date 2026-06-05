# Example-First CI

The pull-request workflow is organized around feature evidence, with examples as
the primary reusable test unit for both agents and GitHub Actions. The manifest
in `feature_manifest.json` is the source of truth for feature coverage, example
compile outputs, Docker compose files, import smoke checks, and selected runtime
groups.

The runner executes the manifest. It should not hard-code the project feature
set, import smoke surface, or compose output layout.

## Artifacts

Every stage writes human-readable logs and machine-readable evidence:

- `ci-summary.json` records every check, command, return code, duration, and log
  path.
- `junit.xml` records the same stage in a format GitHub and review tooling can
  ingest.
- `feature-coverage.json` records manifest-derived feature and example evidence,
  including declared gaps.
- `logs/*.log` contains streamed command output, so large Docker build/runtime
  logs do not have to be kept in memory.

## Local Entry Points

Run the default PR gates from the repository root:

```bash
python3 tests/ci/run_ci.py static --artifact-dir ci-artifacts/static
python3 tests/ci/run_ci.py unit --artifact-dir ci-artifacts/unit
python3 tests/ci/run_ci.py example-compile --artifact-dir ci-artifacts/example-compile
```

Use selectors when an agent or reviewer only needs the evidence for one feature,
example, or test group:

```bash
python3 tests/ci/run_ci.py example-compile --feature routing-bird-frr --artifact-dir ci-artifacts/example-routing
python3 tests/ci/run_ci.py example-compile --example basic-a00-simple-as --artifact-dir ci-artifacts/example-a00
python3 tests/ci/run_ci.py unit --group control-plane-unit --artifact-dir ci-artifacts/unit-control-plane
```

Docker image builds and runtime integration are explicit entry points. They are
available for manual workflow dispatch or local review, but they are not default
pull-request gates:

```bash
python3 tests/ci/run_ci.py example-build --artifact-dir ci-artifacts/example-build
python3 tests/ci/run_ci.py runtime-integration --artifact-dir ci-artifacts/runtime-integration
```

## Manifest Contract

`coverage_policy.required_features` declares the feature ids that must be
tracked by this integration line. Adding or removing a required feature is a
manifest change, not a Python runner change.

Each `covered` feature must declare at least one evidence source: a unit group,
compile example, build example, or runtime group. Use `declared-gap` for work
that is intentionally tracked but not yet covered by this line. Do not mark a
feature `covered` until its evidence is present and runnable.

Each example declares:

- `script`, `args`, `env`, and `clean` for reproducible generation.
- `features` and `tags` for agent/reviewer discovery.
- `compile.enabled` and `compile.outputs` for generated-file evidence.
- `build.enabled` and `build.compose_file` for Docker build evidence.
- `runtime.enabled` for future runtime probe wiring.

The static stage compiles importable Python source plus the selected example
directories. It intentionally excludes embedded payload templates under
`seedemu/services/EthereumService/EthTemplates/`, where some historical `.py`
filenames contain shell script content copied into containers.
