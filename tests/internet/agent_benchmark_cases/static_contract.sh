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

echo "agent benchmark static contract passed"
