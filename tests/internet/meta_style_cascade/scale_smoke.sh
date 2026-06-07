#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
CASE_DIR="$ROOT_DIR/examples/internet/B51_meta_style_cascade"

cd "$CASE_DIR"

: "${SEED_PYTHON:=$ROOT_DIR/.venv/bin/python}"

export SEED_PYTHON

bash b51ctl.sh runtime-ladder-smoke
