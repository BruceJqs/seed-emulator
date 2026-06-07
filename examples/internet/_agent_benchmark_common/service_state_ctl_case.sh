#!/usr/bin/env bash
set -euo pipefail

case_runtime_min_containers() {
  case "$1" in
    S0) printf '%s\n' 10 ;;
    S1) printf '%s\n' 135 ;;
    S1_5) printf '%s\n' 170 ;;
    S2) printf '%s\n' 230 ;;
    *) ab_require_tier "$1" ;;
  esac
}

ss_frontend_router() {
  printf '%sas%sbrd-Public_Service_Frontend_Router-10.%s.10.254\n' "$CONTAINER_PREFIX" "$FRONTEND_ASN" "$FRONTEND_ASN"
}

ss_backend_host() {
  printf '%sas%sh-backend-10.%s.10.80\n' "$CONTAINER_PREFIX" "$ORIGIN_ASN" "$ORIGIN_ASN"
}

ss_client_asns() {
  case "$(ab_canonical_tier "$TIER")" in
    S0) seq 80 83 ;;
    S1) { seq 80 99; seq 101 139; printf '250\n'; } ;;
    S1_5) { seq 80 99; seq 101 154; printf '250\n'; } ;;
    S2) { seq 80 99; seq 101 179; } ;;
  esac
}

ss_client_router() {
  local asn="$1"
  printf '%sas%sbrd-Client_Probe_Router_%s-10.%s.0.254\n' "$CONTAINER_PREFIX" "$asn" "$asn" "$asn"
}

ss_ops_router() {
  case "$(ab_canonical_tier "$TIER")" in
    S0) printf '%sas120brd-Observer_Ops_Router_120-10.120.0.254\n' "$CONTAINER_PREFIX" ;;
    S1) printf '%sas140brd-Observer_Ops_Router_140-10.140.0.254\n' "$CONTAINER_PREFIX" ;;
    S1_5) printf '%sas155brd-Observer_Ops_Router_155-10.155.0.254\n' "$CONTAINER_PREFIX" ;;
    S2) printf '%sas180brd-Observer_Ops_Router_180-10.180.0.254\n' "$CONTAINER_PREFIX" ;;
  esac
}

ss_wait_http_code() {
  local container="$1" expected="$2" out="$3" attempts="${4:-$(ab_runtime_attempts "$TIER")}"
  docker exec "$container" sh -lc "for i in \$(seq 1 $attempts); do code=\$(curl -sS --max-time 3 -o /tmp/agent-case-body.txt -w '%{http_code}' http://$SERVICE_IP/ 2>$out.err || true); printf '%s\n' \"\$code\" | tee $out; [ \"\$code\" = '$expected' ] && exit 0; sleep 1; done; echo 'expected HTTP $expected from $SERVICE_IP' >&2; cat $out >&2; cat $out.err >&2 || true; exit 1"
}

ss_control_state_path() {
  local phase="$1"
  printf '%s/%s_control_state.txt\n' "$ARTIFACT_DIR" "$phase"
}

ss_validate_domain_state() {
  local phase="$1" file="$2"
  case "$CASE_ID:$phase" in
    b52:fault)
      grep -q 'root_cause=maintenance_selector_removed_index_and_placement_capacity' "$file"
      grep -q 'index_quorum=2/7' "$file"
      grep -q 'placement_quorum=1/5' "$file"
      grep -q 'backend_origin=healthy' "$file"
      ;;
    b52:recovery)
      grep -q 'maintenance_selector=frozen' "$file"
      grep -q 'integrity_check=passed' "$file"
      grep -q 'canary_put=passed' "$file"
      ;;
    b53:fault)
      grep -q 'root_cause=valid_customer_config_triggered_edge_runtime_bug' "$file"
      grep -q 'origin_health=healthy' "$file"
      grep -q 'pop_error_rate=85_percent' "$file"
      grep -q 'release_manager=release_v43_active' "$file"
      ;;
    b53:recovery)
      grep -q 'config_api=frozen_for_incident' "$file"
      grep -q 'distributor=rolled_back' "$file"
      grep -q 'canary_pop=passed' "$file"
      ;;
    b54:fault)
      grep -q 'root_cause=feature_file_count_and_size_exceeded_core_proxy_limit' "$file"
      grep -q 'origin_health=healthy' "$file"
      grep -q 'feature_generator=runaway' "$file"
      grep -q 'core_proxy=5xx' "$file"
      ;;
    b54:recovery)
      grep -q 'feature_generator=stopped' "$file"
      grep -q 'known_good_store=restored_feature_set_20260606' "$file"
      grep -q 'tail_services=validated' "$file"
      ;;
    b57:fault)
      grep -q 'root_cause=maintenance_automation_descheduled_network_control_plane' "$file"
      grep -q 'workload_health=healthy' "$file"
      grep -q 'network_control_plane=down' "$file"
      grep -q 'bgp_state=withdrawn_or_degraded' "$file"
      ;;
    b57:recovery)
      grep -q 'maintenance_automation=halted' "$file"
      grep -q 'network_control_plane=running' "$file"
      grep -q 'region_verification=passed' "$file"
      ;;
  esac
  if [ "$phase" = "recovery" ]; then
    grep -q 'recovery_complete=yes' "$file"
    grep -q 'canary_passed=yes' "$file"
  fi
}

case_normal_check() {
  local asn container
  docker exec "$(ss_frontend_router)" /usr/local/bin/agent-case-control.sh normal
  docker exec "$(ss_backend_host)" sh -lc "curl -fsS --max-time 2 http://127.0.0.1/" > "$ARTIFACT_DIR/normal_backend_health.txt"
  docker exec "$(ss_frontend_router)" /usr/local/bin/agent-case-control.sh status > "$(ss_control_state_path normal)"
  grep -q 'incident_phase=normal' "$(ss_control_state_path normal)"
  while read -r asn; do
    container="$(ss_client_router "$asn")"
    ss_wait_http_code "$container" 200 "/tmp/${CASE_ID}-normal-http-$asn.txt"
    docker cp "$container:/tmp/${CASE_ID}-normal-http-$asn.txt" "$ARTIFACT_DIR/normal_client_http_$asn.txt" >/dev/null
  done < <(ss_client_asns)
  ab_log "normal-runtime passed"
}

case_inject_fault() {
  docker exec "$(ss_frontend_router)" /usr/local/bin/agent-case-control.sh inject
  sleep 3
}

case_fault_check() {
  local asn container
  docker exec "$(ss_backend_host)" sh -lc "curl -fsS --max-time 2 http://127.0.0.1/" > "$ARTIFACT_DIR/fault_backend_or_origin_healthy.txt"
  docker exec "$(ss_frontend_router)" /usr/local/bin/agent-case-control.sh status > "$ARTIFACT_DIR/fault_control_state.txt"
  ss_validate_domain_state fault "$ARTIFACT_DIR/fault_control_state.txt"
  while read -r asn; do
    container="$(ss_client_router "$asn")"
    ss_wait_http_code "$container" 503 "/tmp/${CASE_ID}-fault-http-$asn.txt"
    docker cp "$container:/tmp/${CASE_ID}-fault-http-$asn.txt" "$ARTIFACT_DIR/fault_client_http_$asn.txt" >/dev/null
  done < <(ss_client_asns)
  ab_log "fault-runtime passed"
}

case_recovery_check() {
  local asn container
  docker exec "$(ss_frontend_router)" /usr/local/bin/agent-case-control.sh recover
  sleep 3
  docker exec "$(ss_frontend_router)" /usr/local/bin/agent-case-control.sh status > "$ARTIFACT_DIR/recovery_control_state.txt"
  ss_validate_domain_state recovery "$ARTIFACT_DIR/recovery_control_state.txt"
  while read -r asn; do
    container="$(ss_client_router "$asn")"
    ss_wait_http_code "$container" 200 "/tmp/${CASE_ID}-recovery-http-$asn.txt"
    docker cp "$container:/tmp/${CASE_ID}-recovery-http-$asn.txt" "$ARTIFACT_DIR/recovery_client_http_$asn.txt" >/dev/null
  done < <(ss_client_asns)
  ab_log "recovery-runtime passed"
}

case_collect() {
  docker exec "$(ss_frontend_router)" sh -lc "cat /var/log/agent-case-control.log 2>/dev/null || true; printf '\n== state ==\n'; cat /var/run/agent-case-state 2>/dev/null || true; printf '\n== domain state ==\n'; cat /var/lib/agent-case/domain_state.env 2>/dev/null || true; printf '\n== recovery steps ==\n'; cat /var/lib/agent-case/recovery_steps.txt 2>/dev/null || true; printf '\n== service self ==\n'; curl -sS --max-time 2 -i http://127.0.0.1/ 2>&1 || true; printf '\n== bird ==\n'; birdc show protocols 2>&1 || true" > "$ARTIFACT_DIR/frontend_state_collect.txt" 2>&1 || true
  docker exec "$(ss_ops_router)" sh -lc "curl -sS --max-time 3 -i http://$SERVICE_IP/ 2>&1 || true; printf '\n== route ==\n'; birdc show route 10.$FRONTEND_ASN.10.0/24 all 2>&1 || true" > "$ARTIFACT_DIR/ops_view_collect.txt" 2>&1 || true
}

case_exercise_observe_one() {
  local role="$1" dir="$2" asn container
  mkdir -p "$dir"
  case "$role" in
    public-users)
      for asn in "$(ss_client_asns | ab_first_line)" "$(ss_client_asns | ab_last_line)"; do
        container="$(ss_client_router "$asn")"
        docker exec "$container" sh -lc "curl -sS --max-time 3 -i http://$SERVICE_IP/ 2>&1 || true" > "$dir/as${asn}_http.txt" 2>&1 || true
      done
      ;;
    provider-ops|service-ops)
      docker exec "$(ss_backend_host)" sh -lc "curl -fsS --max-time 2 http://127.0.0.1/ 2>&1 || true" > "$dir/backend_or_origin_health.txt" 2>&1 || true
      docker exec "$(ss_frontend_router)" sh -lc "curl -sS --max-time 3 -i http://127.0.0.1/ 2>&1 || true" > "$dir/frontend_self_check.txt" 2>&1 || true
      ;;
    network-ops|route-collectors)
      docker exec "$(ss_ops_router)" sh -lc "birdc show route 10.$FRONTEND_ASN.10.0/24 all 2>&1 || true; printf '\n== protocols ==\n'; birdc show protocols 2>&1 || true" > "$dir/route_view.txt" 2>&1 || true
      ;;
    control-plane|change-audit)
      docker exec "$(ss_frontend_router)" /usr/local/bin/agent-case-control.sh status > "$dir/control_state.txt" 2>&1 || true
      ;;
    *)
      echo "role $role has no $CASE_ID observation mapping" > "$dir/unsupported.txt"
      ;;
  esac
}

case_exercise_action() {
  case "$1" in
    inject-fault)
      case_inject_fault
      ;;
    mitigate|rollback|freeze-distribution|rollback-known-good|halt-automation|restore-control-plane|recover)
      docker exec "$(ss_frontend_router)" /usr/local/bin/agent-case-control.sh recover
      ;;
    validate-recovery)
      case_recovery_check
      ;;
    *)
      echo "unsupported $CASE_ID action $1" >&2
      return 2
      ;;
  esac
}
