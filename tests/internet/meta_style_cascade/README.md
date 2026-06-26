# Meta-style Cascade Smoke Entry

The first-round B51 benchmark uses a controller-based smoke path instead of the
repository's `SeedEmuTestCase` dynamic harness. The shell path matches the P0-P3
scope and avoids depending on the Python Docker SDK harness, which is currently
not reliable in the local Python 3.12 venv because `docker` imports fail on
missing `distutils`.

Run from the repository root:

```bash
COMPOSE_PROJECT_NAME=seed_meta_cascade_s0 tests/internet/meta_style_cascade/smoke.sh
```

The local first-round smoke used:

```bash
COMPOSE_PROJECT_NAME=seed_meta_cascade_s0 \
  PLATFORM=amd \
  SEED_PYTHON="$PWD/.venv/bin/python" \
  tests/internet/meta_style_cascade/smoke.sh
```

This is the P0-P3 smoke gate. A `SeedEmuTestCase` integration can be added once
the dependency path is stable.

Static validation for the interactive S1.5 exercise ledger does not start
containers and is not runtime acceptance:

```bash
tests/internet/meta_style_cascade/exercise_static.sh
```

It checks controller syntax around `exercise-init`, `exercise-phase`,
`exercise-note`, `exercise-status`, `exercise-gate`, and invalid role/action
rejection. It also checks that a forbidden action reaches the policy-deny path.
Live exercise observations and allowed recovery actions still require the S1.5
Docker runtime and the 225-container gate.

Ordered runtime validation runs S0, then the corrected S1 hundreds-container
Docker topology. It does not use telemetry fixtures as tier acceptance:

```bash
COMPOSE_PROJECT_NAME=seed_meta_cascade_runtime \
  PLATFORM=amd \
  SEED_PYTHON="$PWD/.venv/bin/python" \
  tests/internet/meta_style_cascade/scale_smoke.sh
```

`full_sequence.sh` currently uses the same ordered runtime ladder:

```bash
COMPOSE_PROJECT_NAME=seed_meta_cascade_runtime \
  PLATFORM=amd \
  SEED_PYTHON="$PWD/.venv/bin/python" \
  tests/internet/meta_style_cascade/full_sequence.sh
```
