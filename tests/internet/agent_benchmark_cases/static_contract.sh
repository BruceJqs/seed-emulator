#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

cases=(
  "B52_aws_s3_control_plane b52ctl.sh b52"
  "B53_fastly_edge_config_bug b53ctl.sh b53"
  "B54_cloudflare_feature_file_proxy b54ctl.sh b54"
  "B55_verizon_bgp_route_leak b55ctl.sh b55"
  "B56_dyn_authoritative_dns_ddos b56ctl.sh b56"
  "B57_google_network_congestion b57ctl.sh b57"
)

for entry in "${cases[@]}"; do
  read -r dir ctl case_id <<< "$entry"
  case_dir="$ROOT_DIR/examples/internet/$dir"
  cd "$case_dir"
  export AGENT_BENCH_EXERCISE_ID="static-contract-$case_id"
  bash "$ctl" exercise-init-runtime S0 >/dev/null
  bash "$ctl" exercise-phase-runtime S0 baseline >/dev/null
  if bash "$ctl" exercise-gate-runtime S0 baseline >/dev/null 2>&1; then
    echo "$case_id baseline gate unexpectedly passed without observations" >&2
    exit 1
  fi
  set +e
  bash "$ctl" exercise-action-runtime S0 kill-dns >/dev/null 2>&1
  rc=$?
  set -e
  if [ "$rc" -ne 3 ]; then
    echo "$case_id forbidden kill-dns returned $rc, expected 3" >&2
    exit 1
  fi
  for file in README.md case_metadata.json agent_policy.json scoring_stub.json "$ctl"; do
    test -f "$file"
  done
done

python3 - "$ROOT_DIR" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1])
scan_roots = [
    root / "design_notes",
    root / "examples/internet/B51_meta_style_cascade",
    root / "examples/internet/B52_aws_s3_control_plane",
    root / "examples/internet/B53_fastly_edge_config_bug",
    root / "examples/internet/B54_cloudflare_feature_file_proxy",
    root / "examples/internet/B55_verizon_bgp_route_leak",
    root / "examples/internet/B56_dyn_authoritative_dns_ddos",
    root / "examples/internet/B57_google_network_congestion",
    root / "examples/internet/_agent_benchmark_common",
    root / "tests/internet/agent_benchmark_cases",
    root / "tests/internet/meta_style_cascade",
]
skip_dirs = {"output", "test_log", "__pycache__"}
bad = []

for scan_root in scan_roots:
    if not scan_root.exists():
        continue
    for path in scan_root.rglob("*"):
        if path.is_dir() or any(part in skip_dirs for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if any("\u4e00" <= ch <= "\u9fff" for ch in line):
                bad.append(f"{path.relative_to(root)}:{lineno}")

if bad:
    print("CJK text is not allowed in benchmark source documentation/config/test files:", file=sys.stderr)
    for item in bad:
        print(f"  {item}", file=sys.stderr)
    sys.exit(1)
PY

echo "agent benchmark static contract passed"
