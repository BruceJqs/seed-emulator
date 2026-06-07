#!/usr/bin/env bash
set -euo pipefail

CASE_ID="b52"
CASE_SLUG="aws_s3_control_plane"
CASE_GENERATOR="aws_s3_control_plane.py"
CONTAINER_PREFIX="${B52_CONTAINER_PREFIX:-b52-}"

source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../_agent_benchmark_common" && pwd)/agent_case_ctl_common.sh"
ab_init

SERVICE_IP="10.52.10.80"
OBJECT_SHARD_IP="10.54.10.80"
CAPACITY_REGISTRY_IP="10.53.10.40"
STATUS_DASHBOARD_IP="10.53.10.60"

B52_INDEX_IPS=(10.53.10.11 10.53.10.12 10.53.10.13 10.53.10.14 10.53.10.15)
B52_PLACEMENT_IPS=(10.53.10.21 10.53.10.22 10.53.10.23)

case_runtime_min_containers() {
  case "$1" in
    S0) printf '%s\n' 20 ;;
    S1) printf '%s\n' 145 ;;
    S1_5) printf '%s\n' 180 ;;
    S2) printf '%s\n' 240 ;;
    *) ab_require_tier "$1" ;;
  esac
}

b52_name_ip() {
  printf '%s' "$1" | tr '.' '_'
}

b52_container_for_role() {
  case "$1" in
    api)
      printf '%sas52brd-S3_Public_API_Router-10.52.10.254\n' "$CONTAINER_PREFIX"
      ;;
    object-shard)
      printf '%sas54h-Object_Storage_Shard-10.54.10.80\n' "$CONTAINER_PREFIX"
      ;;
    capacity-registry)
      printf '%sas53h-Capacity_Registry-10.53.10.40\n' "$CONTAINER_PREFIX"
      ;;
    maintenance-tool)
      printf '%sas53h-Maintenance_Tool-10.53.10.50\n' "$CONTAINER_PREFIX"
      ;;
    status-dashboard)
      printf '%sas53h-Status_Dashboard-10.53.10.60\n' "$CONTAINER_PREFIX"
      ;;
    ops)
      case "$(ab_canonical_tier "$TIER")" in
        S0) printf '%sas120brd-Observer_Ops_Router_120-10.120.0.254\n' "$CONTAINER_PREFIX" ;;
        S1) printf '%sas140brd-Observer_Ops_Router_140-10.140.0.254\n' "$CONTAINER_PREFIX" ;;
        S1_5) printf '%sas155brd-Observer_Ops_Router_155-10.155.0.254\n' "$CONTAINER_PREFIX" ;;
        S2) printf '%sas180brd-Observer_Ops_Router_180-10.180.0.254\n' "$CONTAINER_PREFIX" ;;
      esac
      ;;
    *)
      echo "unknown B52 role $1" >&2
      return 2
      ;;
  esac
}

b52_index_container() {
  local ip="$1" idx
  idx="${ip##*.}"
  idx="$((idx - 10))"
  printf '%sas53h-Index_Subsystem_%s-%s\n' "$CONTAINER_PREFIX" "$idx" "$ip"
}

b52_placement_container() {
  local ip="$1" idx
  idx="${ip##*.}"
  idx="$((idx - 20))"
  printf '%sas53h-Placement_Subsystem_%s-%s\n' "$CONTAINER_PREFIX" "$idx" "$ip"
}

b52_client_asns() {
  case "$(ab_canonical_tier "$TIER")" in
    S0) seq 80 83 ;;
    S1) { seq 80 99; seq 101 139; printf '250\n'; } ;;
    S1_5) { seq 80 99; seq 101 154; printf '250\n'; } ;;
    S2) { seq 80 99; seq 101 179; } ;;
  esac
}

b52_client_router() {
  local asn="$1"
  printf '%sas%sbrd-Client_Probe_Router_%s-10.%s.0.254\n' "$CONTAINER_PREFIX" "$asn" "$asn" "$asn"
}

b52_set_node_state() {
  local container="$1" state="$2"
  docker exec "$container" /usr/local/bin/b52-subsystem-node.sh "$state" >/dev/null
}

b52_set_capacity_phase() {
  local phase="$1"
  docker exec "$(b52_container_for_role capacity-registry)" /usr/local/bin/b52-capacity-registry.sh "$phase" >/dev/null
}

b52_wait_http_code() {
  local container="$1" url="$2" expected="$3" out="$4" attempts="${5:-$(ab_runtime_attempts "$TIER")}"
  docker exec "$container" sh -lc "for i in \$(seq 1 $attempts); do code=\$(curl -sS --max-time 3 -o /tmp/b52-body.txt -w '%{http_code}' '$url' 2>$out.err || true); printf '%s\n' \"\$code\" | tee $out; [ \"\$code\" = '$expected' ] && exit 0; sleep 1; done; echo 'expected HTTP $expected from $url' >&2; cat $out >&2; cat $out.err >&2 || true; cat /tmp/b52-body.txt >&2 || true; exit 1"
}

b52_copy_tmp() {
  local container="$1" src="$2" dest="$3"
  docker cp "$container:$src" "$dest" >/dev/null
}

b52_capture_control_state() {
  local phase out
  phase="$1"
  out="$ARTIFACT_DIR/${phase}_control_state.txt"
  {
    printf '== maintenance ==\n'
    docker exec "$(b52_container_for_role maintenance-tool)" /usr/local/bin/b52-maintenance-tool.sh status 2>&1 || true
    printf '\n== capacity_registry ==\n'
    docker exec "$(b52_container_for_role capacity-registry)" /usr/local/bin/b52-capacity-registry.sh status 2>&1 || true
    printf '\n== api_frontend ==\n'
    docker exec "$(b52_container_for_role api)" /usr/local/bin/b52-api-frontend.sh status 2>&1 || true
    printf '\n== index_nodes ==\n'
    local ip
    for ip in "${B52_INDEX_IPS[@]}"; do
      printf -- '-- %s --\n' "$ip"
      docker exec "$(b52_index_container "$ip")" /usr/local/bin/b52-subsystem-node.sh status 2>&1 || true
    done
    printf '\n== placement_nodes ==\n'
    for ip in "${B52_PLACEMENT_IPS[@]}"; do
      printf -- '-- %s --\n' "$ip"
      docker exec "$(b52_placement_container "$ip")" /usr/local/bin/b52-subsystem-node.sh status 2>&1 || true
    done
  } > "$out"
}

case_normal_check() {
  local asn container
  for ip in "${B52_INDEX_IPS[@]}"; do
    b52_set_node_state "$(b52_index_container "$ip")" active
  done
  for ip in "${B52_PLACEMENT_IPS[@]}"; do
    b52_set_node_state "$(b52_placement_container "$ip")" active
  done
  b52_set_capacity_phase normal
  docker exec "$(b52_container_for_role api)" /usr/local/bin/b52-api-frontend.sh normal >/dev/null

  docker exec "$(b52_container_for_role object-shard)" sh -lc "curl -fsS --max-time 2 http://127.0.0.1/" > "$ARTIFACT_DIR/normal_object_shard_health.txt"
  docker exec "$(b52_container_for_role maintenance-tool)" /usr/local/bin/b52-maintenance-tool.sh dry-run > "$ARTIFACT_DIR/normal_maintenance_dry_run.txt"
  docker exec "$(b52_container_for_role status-dashboard)" sh -lc "curl -fsS --max-time 2 http://127.0.0.1/" > "$ARTIFACT_DIR/normal_status_dashboard.txt"

  while read -r asn; do
    container="$(b52_client_router "$asn")"
    b52_wait_http_code "$container" "http://$SERVICE_IP/" 200 "/tmp/b52-normal-http-$asn.txt"
    b52_copy_tmp "$container" /tmp/b52-normal-http-$asn.txt "$ARTIFACT_DIR/normal_client_http_$asn.txt"
  done < <(b52_client_asns)

  b52_capture_control_state normal
  grep -q 'index_quorum=5/5' "$ARTIFACT_DIR/normal_control_state.txt"
  grep -q 'placement_quorum=3/3' "$ARTIFACT_DIR/normal_control_state.txt"
  ab_log "normal-runtime passed"
}

case_inject_fault() {
  docker exec "$(b52_container_for_role maintenance-tool)" /usr/local/bin/b52-maintenance-tool.sh inject >/dev/null
  b52_set_node_state "$(b52_index_container 10.53.10.11)" removed
  b52_set_node_state "$(b52_index_container 10.53.10.12)" removed
  b52_set_node_state "$(b52_index_container 10.53.10.13)" removed
  b52_set_node_state "$(b52_placement_container 10.53.10.21)" removed
  b52_set_node_state "$(b52_placement_container 10.53.10.22)" removed
  b52_set_capacity_phase fault
  docker exec "$(b52_container_for_role api)" /usr/local/bin/b52-api-frontend.sh fault >/dev/null
  sleep 3
}

case_fault_check() {
  local asn container
  docker exec "$(b52_container_for_role object-shard)" sh -lc "curl -fsS --max-time 2 http://127.0.0.1/" > "$ARTIFACT_DIR/fault_object_shard_still_healthy.txt"
  docker exec "$(b52_container_for_role status-dashboard)" sh -lc "curl -fsS --max-time 2 http://127.0.0.1/" > "$ARTIFACT_DIR/fault_status_dashboard_delayed.txt"
  while read -r asn; do
    container="$(b52_client_router "$asn")"
    b52_wait_http_code "$container" "http://$SERVICE_IP/" 503 "/tmp/b52-fault-http-$asn.txt"
    b52_copy_tmp "$container" /tmp/b52-fault-http-$asn.txt "$ARTIFACT_DIR/fault_client_http_$asn.txt"
  done < <(b52_client_asns)
  b52_capture_control_state fault
  grep -q 'root_cause=maintenance_selector_removed_index_and_placement_capacity' "$ARTIFACT_DIR/fault_control_state.txt"
  grep -q 'index_quorum=2/5' "$ARTIFACT_DIR/fault_control_state.txt"
  grep -q 'placement_quorum=1/3' "$ARTIFACT_DIR/fault_control_state.txt"
  grep -q 'status=removed' "$ARTIFACT_DIR/fault_control_state.txt"
  ab_log "fault-runtime passed"
}

case_recovery_check() {
  local asn container ip
  docker exec "$(b52_container_for_role maintenance-tool)" /usr/local/bin/b52-maintenance-tool.sh recover >/dev/null
  for ip in "${B52_INDEX_IPS[@]}"; do
    b52_set_node_state "$(b52_index_container "$ip")" active
  done
  b52_set_capacity_phase normal
  sleep 2
  b52_set_capacity_phase recovery
  for ip in "${B52_PLACEMENT_IPS[@]}"; do
    b52_set_node_state "$(b52_placement_container "$ip")" active
  done
  docker exec "$(b52_container_for_role api)" /usr/local/bin/b52-api-frontend.sh recovery >/dev/null
  sleep 3
  while read -r asn; do
    container="$(b52_client_router "$asn")"
    b52_wait_http_code "$container" "http://$SERVICE_IP/" 200 "/tmp/b52-recovery-http-$asn.txt"
    b52_copy_tmp "$container" /tmp/b52-recovery-http-$asn.txt "$ARTIFACT_DIR/recovery_client_http_$asn.txt"
  done < <(b52_client_asns)
  docker exec "$(b52_container_for_role status-dashboard)" sh -lc "curl -fsS --max-time 2 http://127.0.0.1/" > "$ARTIFACT_DIR/recovery_status_dashboard.txt"
  b52_capture_control_state recovery
  grep -q 'maintenance_selector=frozen' "$ARTIFACT_DIR/recovery_control_state.txt"
  grep -q 'integrity_check=passed' "$ARTIFACT_DIR/recovery_control_state.txt"
  grep -q 'canary_put=passed' "$ARTIFACT_DIR/recovery_control_state.txt"
  grep -q 'recovery_complete=yes' "$ARTIFACT_DIR/recovery_control_state.txt"
  ab_log "recovery-runtime passed"
}

case_collect() {
  local ip
  b52_capture_control_state collect
  docker exec "$(b52_container_for_role api)" sh -lc "cat /var/log/b52-api-frontend.log 2>/dev/null || true; printf '\n== last request ==\n'; cat /var/lib/b52/last_request.txt 2>/dev/null || true" > "$ARTIFACT_DIR/api_frontend_collect.txt" 2>&1 || true
  docker exec "$(b52_container_for_role maintenance-tool)" /usr/local/bin/b52-maintenance-tool.sh status > "$ARTIFACT_DIR/maintenance_tool_collect.txt" 2>&1 || true
  docker exec "$(b52_container_for_role capacity-registry)" sh -lc "cat /var/log/b52-capacity-registry.log 2>/dev/null || true; printf '\n== state ==\n'; /usr/local/bin/b52-capacity-registry.sh status" > "$ARTIFACT_DIR/capacity_registry_collect.txt" 2>&1 || true
  for ip in "${B52_INDEX_IPS[@]}"; do
    docker exec "$(b52_index_container "$ip")" sh -lc "cat /var/log/b52-index-* 2>/dev/null || true; /usr/local/bin/b52-subsystem-node.sh status" > "$ARTIFACT_DIR/index_$(b52_name_ip "$ip")_collect.txt" 2>&1 || true
  done
  for ip in "${B52_PLACEMENT_IPS[@]}"; do
    docker exec "$(b52_placement_container "$ip")" sh -lc "cat /var/log/b52-placement-* 2>/dev/null || true; /usr/local/bin/b52-subsystem-node.sh status" > "$ARTIFACT_DIR/placement_$(b52_name_ip "$ip")_collect.txt" 2>&1 || true
  done
  docker exec "$(b52_container_for_role ops)" sh -lc "birdc show route 10.52.10.0/24 all 2>&1 || true; printf '\n== api curl ==\n'; curl -sS --max-time 3 -i http://$SERVICE_IP/ 2>&1 || true; printf '\n== status dashboard ==\n'; curl -sS --max-time 3 -i http://$STATUS_DASHBOARD_IP/ 2>&1 || true" > "$ARTIFACT_DIR/ops_view_collect.txt" 2>&1 || true
}

case_exercise_observe_one() {
  local role="$1" dir="$2" asn container
  mkdir -p "$dir"
  case "$role" in
    public-users)
      for asn in "$(b52_client_asns | ab_first_line)" "$(b52_client_asns | ab_last_line)"; do
        container="$(b52_client_router "$asn")"
        docker exec "$container" sh -lc "curl -sS --max-time 3 -i http://$SERVICE_IP/ 2>&1 || true" > "$dir/as${asn}_s3_api.txt" 2>&1 || true
      done
      ;;
    provider-ops|service-ops)
      docker exec "$(b52_container_for_role object-shard)" sh -lc "curl -fsS --max-time 2 http://127.0.0.1/ 2>&1 || true" > "$dir/object_shard_health.txt" 2>&1 || true
      docker exec "$(b52_container_for_role api)" /usr/local/bin/b52-api-frontend.sh status > "$dir/api_frontend_status.txt" 2>&1 || true
      docker exec "$(b52_container_for_role status-dashboard)" sh -lc "curl -sS --max-time 2 -i http://127.0.0.1/ 2>&1 || true" > "$dir/status_dashboard.txt" 2>&1 || true
      ;;
    network-ops|route-collectors)
      docker exec "$(b52_container_for_role ops)" sh -lc "birdc show route 10.52.10.0/24 all 2>&1 || true; printf '\n== protocols ==\n'; birdc show protocols 2>&1 || true" > "$dir/route_view.txt" 2>&1 || true
      ;;
    control-plane|change-audit)
      b52_capture_control_state observe
      cp "$ARTIFACT_DIR/observe_control_state.txt" "$dir/control_state.txt"
      docker exec "$(b52_container_for_role maintenance-tool)" /usr/local/bin/b52-maintenance-tool.sh dry-run > "$dir/maintenance_dry_run.txt" 2>&1 || true
      ;;
    *)
      echo "role $role has no B52 observation mapping" > "$dir/unsupported.txt"
      ;;
  esac
}

case_exercise_action() {
  case "$1" in
    inject-fault)
      case_inject_fault
      ;;
    mitigate|rollback|recover)
      docker exec "$(b52_container_for_role maintenance-tool)" /usr/local/bin/b52-maintenance-tool.sh recover >/dev/null
      ;;
    validate-recovery)
      case_recovery_check
      ;;
    *)
      echo "unsupported B52 action $1" >&2
      return 2
      ;;
  esac
}

ab_main "$@"
