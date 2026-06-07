#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
CASE_DIR="$ROOT_DIR/examples/internet/B51_meta_style_cascade"

cd "$CASE_DIR"

: "${COMPOSE_PROJECT_NAME:=seed_meta_cascade_exercise_static}"
: "${SEED_PYTHON:=$ROOT_DIR/.venv/bin/python}"

export TIER=S1.5
export COMPOSE_PROJECT_NAME
export SEED_PYTHON
export B51_EXERCISE_ID=static-ledger-check

bash b51ctl.sh exercise-init-runtime S1.5
bash b51ctl.sh exercise-phase-runtime S1.5 baseline
bash b51ctl.sh exercise-note-runtime S1.5 facilitator "static ledger note"
bash b51ctl.sh exercise-status-runtime S1.5 >/dev/null

if bash b51ctl.sh exercise-gate-runtime S1.5 baseline >/dev/null 2>&1; then
  echo "baseline gate unexpectedly passed without observations" >&2
  exit 1
fi

if bash b51ctl.sh exercise-observe-runtime S1.5 not-a-role >/dev/null 2>&1; then
  echo "invalid exercise role unexpectedly accepted" >&2
  exit 1
fi

set +e
bash b51ctl.sh exercise-action-runtime S1.5 not-an-action >/dev/null 2>&1
rc=$?
set -e
if [ "$rc" -ne 2 ]; then
  echo "invalid exercise action returned $rc, expected 2" >&2
  exit 1
fi

set +e
bash b51ctl.sh exercise-action-runtime S1.5 kill-dns >/dev/null 2>&1
rc=$?
set -e
if [ "$rc" -ne 3 ]; then
  echo "forbidden exercise action returned $rc, expected policy-deny rc 3" >&2
  exit 1
fi

set +e
bash b51ctl.sh exercise-action-runtime S1.5 validate-recovery >/dev/null 2>&1
rc=$?
set -e
if [ "$rc" -eq 0 ]; then
  echo "validate-recovery unexpectedly passed without S1.5 runtime" >&2
  exit 1
fi

validate_result_dir="$(
  find test_log/runtime/S1_5/exercise/static-ledger-check/actions \
    -maxdepth 1 -type d -name '*_validate-recovery' \
    -exec test -f '{}/result.env' ';' -print -quit
)"
if [ -z "$validate_result_dir" ]; then
  echo "validate-recovery preflight failure did not leave an action result ledger" >&2
  exit 1
fi

echo "exercise static ledger check passed"
