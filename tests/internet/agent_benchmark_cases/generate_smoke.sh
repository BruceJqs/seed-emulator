#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
: "${SEED_PYTHON:=$ROOT_DIR/.venv/bin/python}"
export SEED_PYTHON

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
  bash "$ctl" generate-runtime S0
  test -f output/docker-compose.yml
  bash "$ctl" panel-snapshot-runtime S0
  test -s test_log/runtime/S0/showcase_panel/index.html
  grep -q "Runtime Readiness" test_log/runtime/S0/showcase_panel/index.html
  case "$case_id" in
    b55)
      find output -type f -exec grep -l 'b55-dqe-control.sh' '{}' + | grep -q .
      ;;
    b56)
      find output -type f -exec grep -l 'b56-dyn-ddos-control.sh' '{}' + | grep -q .
      ;;
  esac
done

echo "agent benchmark generate smoke passed"
