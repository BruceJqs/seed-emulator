#!/usr/bin/env bash
set -euo pipefail

CASE_ID="b53"
CASE_SLUG="fastly_edge_config_bug"
CASE_GENERATOR="fastly_edge_config_bug.py"
CONTAINER_PREFIX="${B53_CONTAINER_PREFIX:-b53-}"

source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../_agent_benchmark_common" && pwd)/agent_case_ctl_common.sh"
ab_init

SERVICE_IP="10.53.10.80"

B53_POPS=(iad sjc lhr sin gru syd ams canary)
B53_AFFECTED_POPS=(iad sjc lhr sin gru syd ams)
B53_ORIGINS=(news api media)
B53_CONTROL_COMPONENTS=(config-api validator compiler distributor release-manager status-dashboard)

case_runtime_min_containers() {
  case "$1" in
    S0) printf '%s\n' 25 ;;
    S1) printf '%s\n' 155 ;;
    S1_5) printf '%s\n' 185 ;;
    S2) printf '%s\n' 220 ;;
    *) ab_require_tier "$1" ;;
  esac
}

b53_container_for_role() {
  case "$1" in
    frontend)
      printf '%sas53brd-Fastly_Public_Edge_Router-10.53.10.254\n' "$CONTAINER_PREFIX"
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
      echo "unknown B53 role $1" >&2
      return 2
      ;;
  esac
}

b53_pop_ip() {
  case "$1" in
    iad) printf '%s\n' 10.53.10.11 ;;
    sjc) printf '%s\n' 10.53.10.12 ;;
    lhr) printf '%s\n' 10.53.10.13 ;;
    sin) printf '%s\n' 10.53.10.14 ;;
    gru) printf '%s\n' 10.53.10.15 ;;
    syd) printf '%s\n' 10.53.10.16 ;;
    ams) printf '%s\n' 10.53.10.17 ;;
    canary) printf '%s\n' 10.53.10.18 ;;
    *) return 2 ;;
  esac
}

b53_origin_ip() {
  case "$1" in
    news) printf '%s\n' 10.55.10.80 ;;
    api) printf '%s\n' 10.55.10.81 ;;
    media) printf '%s\n' 10.55.10.82 ;;
    *) return 2 ;;
  esac
}

b53_control_ip() {
  case "$1" in
    config-api) printf '%s\n' 10.54.10.11 ;;
    validator) printf '%s\n' 10.54.10.12 ;;
    compiler) printf '%s\n' 10.54.10.13 ;;
    distributor) printf '%s\n' 10.54.10.14 ;;
    release-manager) printf '%s\n' 10.54.10.15 ;;
    status-dashboard) printf '%s\n' 10.54.10.16 ;;
    *) return 2 ;;
  esac
}

b53_display_token() {
  local raw="$1"
  raw="${raw//-/_}"
  printf '%s\n' "$raw"
}

b53_pop_container() {
  local pop="$1"
  printf '%sas53h-Edge_POP_%s-%s\n' "$CONTAINER_PREFIX" "$(printf '%s' "$pop" | tr '[:lower:]' '[:upper:]')" "$(b53_pop_ip "$pop")"
}

b53_control_container() {
  local role="$1"
  case "$role" in
    config-api) printf '%sas54h-Config_API-10.54.10.11\n' "$CONTAINER_PREFIX" ;;
    validator) printf '%sas54h-Config_Validator-10.54.10.12\n' "$CONTAINER_PREFIX" ;;
    compiler) printf '%sas54h-Config_Compiler-10.54.10.13\n' "$CONTAINER_PREFIX" ;;
    distributor) printf '%sas54h-Config_Distributor-10.54.10.14\n' "$CONTAINER_PREFIX" ;;
    release-manager) printf '%sas54h-Release_Manager-10.54.10.15\n' "$CONTAINER_PREFIX" ;;
    status-dashboard) printf '%sas54h-Status_Dashboard-10.54.10.16\n' "$CONTAINER_PREFIX" ;;
    *) return 2 ;;
  esac
}

b53_origin_container() {
  local origin="$1"
  case "$origin" in
    news) printf '%sas55h-Customer_Origin_News-10.55.10.80\n' "$CONTAINER_PREFIX" ;;
    api) printf '%sas55h-Customer_Origin_API-10.55.10.81\n' "$CONTAINER_PREFIX" ;;
    media) printf '%sas55h-Customer_Origin_Media-10.55.10.82\n' "$CONTAINER_PREFIX" ;;
    *) return 2 ;;
  esac
}

b53_client_asns() {
  case "$(ab_canonical_tier "$TIER")" in
    S0) seq 80 83 ;;
    S1) { seq 80 99; seq 101 139; printf '250\n'; } ;;
    S1_5) { seq 80 99; seq 101 154; printf '250\n'; } ;;
    S2) { seq 80 99; seq 101 179; } ;;
  esac
}

b53_client_router() {
  local asn="$1"
  printf '%sas%sbrd-Client_Probe_Router_%s-10.%s.0.254\n' "$CONTAINER_PREFIX" "$asn" "$asn" "$asn"
}

b53_name_ip() {
  printf '%s' "$1" | tr '.' '_'
}

b53_set_component_phase() {
  local phase="$1" component
  docker exec "$(b53_container_for_role frontend)" /usr/local/bin/b53-edge-frontend.sh "$phase" >/dev/null
  for component in "${B53_CONTROL_COMPONENTS[@]}"; do
    docker exec "$(b53_control_container "$component")" /usr/local/bin/b53-control-component.sh "$phase" >/dev/null
  done
  for component in "${B53_POPS[@]}"; do
    docker exec "$(b53_pop_container "$component")" /usr/local/bin/b53-edge-pop.sh "$phase" >/dev/null
  done
}

b53_wait_http_code() {
  local container="$1" url="$2" expected="$3" out="$4" attempts="${5:-$(ab_runtime_attempts "$TIER")}"
  docker exec "$container" sh -lc "for i in \$(seq 1 $attempts); do code=\$(curl -sS --max-time 3 -o /tmp/b53-body.txt -w '%{http_code}' '$url' 2>$out.err || true); printf '%s\n' \"\$code\" | tee $out; [ \"\$code\" = '$expected' ] && exit 0; sleep 1; done; echo 'expected HTTP $expected from $url' >&2; cat $out >&2; cat $out.err >&2 || true; cat /tmp/b53-body.txt >&2 || true; exit 1"
}

b53_capture_control_state() {
  local phase="$1" out component pop origin
  out="$ARTIFACT_DIR/${phase}_control_state.txt"
  {
    printf '== edge_frontend ==\n'
    docker exec "$(b53_container_for_role frontend)" /usr/local/bin/b53-edge-frontend.sh status 2>&1 || true
    printf '\n== control_plane ==\n'
    for component in "${B53_CONTROL_COMPONENTS[@]}"; do
      printf -- '-- %s --\n' "$component"
      docker exec "$(b53_control_container "$component")" /usr/local/bin/b53-control-component.sh status 2>&1 || true
    done
    printf '\n== edge_pops ==\n'
    for pop in "${B53_POPS[@]}"; do
      printf -- '-- %s --\n' "$pop"
      docker exec "$(b53_pop_container "$pop")" /usr/local/bin/b53-edge-pop.sh status 2>&1 || true
    done
    printf '\n== origins ==\n'
    for origin in "${B53_ORIGINS[@]}"; do
      printf -- '-- %s --\n' "$origin"
      docker exec "$(b53_origin_container "$origin")" sh -lc "curl -fsS --max-time 2 http://127.0.0.1/" 2>&1 || true
    done
  } > "$out"
}

b53_copy_tmp() {
  local container="$1" src="$2" dest="$3"
  docker cp "$container:$src" "$dest" >/dev/null
}

case_normal_check() {
  local asn container origin
  b53_set_component_phase normal

  for origin in "${B53_ORIGINS[@]}"; do
    docker exec "$(b53_origin_container "$origin")" sh -lc "curl -fsS --max-time 2 http://127.0.0.1/" > "$ARTIFACT_DIR/normal_origin_${origin}_health.txt"
  done

  while read -r asn; do
    container="$(b53_client_router "$asn")"
    b53_wait_http_code "$container" "http://$SERVICE_IP/" 200 "/tmp/b53-normal-http-$asn.txt"
    b53_copy_tmp "$container" /tmp/b53-normal-http-$asn.txt "$ARTIFACT_DIR/normal_client_http_$asn.txt"
  done < <(b53_client_asns)

  b53_capture_control_state normal
  grep -q 'incident_phase=normal' "$ARTIFACT_DIR/normal_control_state.txt"
  grep -q 'origin_health=healthy' "$ARTIFACT_DIR/normal_control_state.txt"
  grep -q 'affected_pops=0/8' "$ARTIFACT_DIR/normal_control_state.txt"
  ab_log "normal-runtime passed"
}

case_inject_fault() {
  b53_set_component_phase fault
  sleep 3
}

case_fault_check() {
  local asn container origin
  for origin in "${B53_ORIGINS[@]}"; do
    docker exec "$(b53_origin_container "$origin")" sh -lc "curl -fsS --max-time 2 http://127.0.0.1/" > "$ARTIFACT_DIR/fault_origin_${origin}_still_healthy.txt"
  done
  docker exec "$(b53_pop_container iad)" sh -lc "curl -sS --max-time 2 -o /tmp/b53-pop-affected-body.txt -w '%{http_code}\n' http://127.0.0.1:8080/" > "$ARTIFACT_DIR/fault_affected_pop_iad_http.txt" || true
  docker exec "$(b53_pop_container canary)" sh -lc "curl -sS --max-time 2 -o /tmp/b53-pop-canary-body.txt -w '%{http_code}\n' http://127.0.0.1:8080/" > "$ARTIFACT_DIR/fault_canary_pop_http.txt" || true

  while read -r asn; do
    container="$(b53_client_router "$asn")"
    b53_wait_http_code "$container" "http://$SERVICE_IP/" 503 "/tmp/b53-fault-http-$asn.txt"
    b53_copy_tmp "$container" /tmp/b53-fault-http-$asn.txt "$ARTIFACT_DIR/fault_client_http_$asn.txt"
  done < <(b53_client_asns)

  b53_capture_control_state fault
  grep -q 'root_cause=valid_customer_config_triggered_edge_runtime_bug' "$ARTIFACT_DIR/fault_control_state.txt"
  grep -q 'origin_health=healthy' "$ARTIFACT_DIR/fault_control_state.txt"
  grep -q 'config_api=valid_config_accepted' "$ARTIFACT_DIR/fault_control_state.txt"
  grep -q 'validator=passed' "$ARTIFACT_DIR/fault_control_state.txt"
  grep -q 'distributor=propagated_to_majority_pops' "$ARTIFACT_DIR/fault_control_state.txt"
  grep -q 'pop_error_rate=85_percent' "$ARTIFACT_DIR/fault_control_state.txt"
  grep -q 'affected_pops=7/8' "$ARTIFACT_DIR/fault_control_state.txt"
  grep -q 'edge_status=canary_unaffected' "$ARTIFACT_DIR/fault_control_state.txt"
  ab_log "fault-runtime passed"
}

b53_stage_recovery() {
  b53_set_component_phase recovery
  sleep 3
}

case_recovery_check() {
  local asn container
  b53_stage_recovery
  while read -r asn; do
    container="$(b53_client_router "$asn")"
    b53_wait_http_code "$container" "http://$SERVICE_IP/" 200 "/tmp/b53-recovery-http-$asn.txt"
    b53_copy_tmp "$container" /tmp/b53-recovery-http-$asn.txt "$ARTIFACT_DIR/recovery_client_http_$asn.txt"
  done < <(b53_client_asns)
  b53_capture_control_state recovery
  grep -q 'config_api=frozen_for_incident' "$ARTIFACT_DIR/recovery_control_state.txt"
  grep -q 'distributor=rolled_back' "$ARTIFACT_DIR/recovery_control_state.txt"
  grep -q 'release_manager=trigger_config_disabled' "$ARTIFACT_DIR/recovery_control_state.txt"
  grep -q 'canary_pop=passed' "$ARTIFACT_DIR/recovery_control_state.txt"
  grep -q 'hotfix_note=recorded' "$ARTIFACT_DIR/recovery_control_state.txt"
  grep -q 'recovery_complete=yes' "$ARTIFACT_DIR/recovery_control_state.txt"
  ab_log "recovery-runtime passed"
}

case_collect() {
  local component pop origin
  b53_capture_control_state collect
  docker exec "$(b53_container_for_role frontend)" sh -lc "cat /var/log/b53-edge-frontend.log 2>/dev/null || true; printf '\n== status ==\n'; /usr/local/bin/b53-edge-frontend.sh status" > "$ARTIFACT_DIR/edge_frontend_collect.txt" 2>&1 || true
  for component in "${B53_CONTROL_COMPONENTS[@]}"; do
    docker exec "$(b53_control_container "$component")" sh -lc "cat /var/log/b53-$component.log 2>/dev/null || true; printf '\n== status ==\n'; /usr/local/bin/b53-control-component.sh status" > "$ARTIFACT_DIR/control_$(b53_display_token "$component")_collect.txt" 2>&1 || true
  done
  for pop in "${B53_POPS[@]}"; do
    docker exec "$(b53_pop_container "$pop")" sh -lc "cat /var/log/b53-edge-pop-$pop.log 2>/dev/null || true; printf '\n== status ==\n'; /usr/local/bin/b53-edge-pop.sh status" > "$ARTIFACT_DIR/pop_${pop}_collect.txt" 2>&1 || true
  done
  for origin in "${B53_ORIGINS[@]}"; do
    docker exec "$(b53_origin_container "$origin")" sh -lc "curl -fsS --max-time 2 http://127.0.0.1/" > "$ARTIFACT_DIR/origin_${origin}_collect.txt" 2>&1 || true
  done
  docker exec "$(b53_container_for_role ops)" sh -lc "birdc show route 10.53.10.0/24 all 2>&1 || true; printf '\n== frontend curl ==\n'; curl -sS --max-time 3 -i http://$SERVICE_IP/ 2>&1 || true" > "$ARTIFACT_DIR/ops_view_collect.txt" 2>&1 || true
}

case_exercise_observe_one() {
  local role="$1" dir="$2" asn container
  mkdir -p "$dir"
  case "$role" in
    public-users)
      for asn in "$(b53_client_asns | ab_first_line)" "$(b53_client_asns | ab_last_line)"; do
        container="$(b53_client_router "$asn")"
        docker exec "$container" sh -lc "curl -sS --max-time 3 -i http://$SERVICE_IP/ 2>&1 || true" > "$dir/as${asn}_customer_http.txt" 2>&1 || true
      done
      ;;
    provider-ops|service-ops)
      docker exec "$(b53_pop_container iad)" /usr/local/bin/b53-edge-pop.sh status > "$dir/affected_pop_iad_status.txt" 2>&1 || true
      docker exec "$(b53_pop_container canary)" /usr/local/bin/b53-edge-pop.sh status > "$dir/canary_pop_status.txt" 2>&1 || true
      docker exec "$(b53_origin_container news)" sh -lc "curl -fsS --max-time 2 http://127.0.0.1/ 2>&1 || true" > "$dir/news_origin_health.txt" 2>&1 || true
      docker exec "$(b53_container_for_role frontend)" /usr/local/bin/b53-edge-frontend.sh status > "$dir/edge_frontend_status.txt" 2>&1 || true
      ;;
    network-ops|route-collectors)
      docker exec "$(b53_container_for_role ops)" sh -lc "birdc show route 10.53.10.0/24 all 2>&1 || true; printf '\n== protocols ==\n'; birdc show protocols 2>&1 || true" > "$dir/route_view.txt" 2>&1 || true
      ;;
    control-plane|change-audit)
      b53_capture_control_state observe
      cp "$ARTIFACT_DIR/observe_control_state.txt" "$dir/control_state.txt"
      docker exec "$(b53_control_container config-api)" /usr/local/bin/b53-control-component.sh status > "$dir/config_api_audit.txt" 2>&1 || true
      docker exec "$(b53_control_container release-manager)" /usr/local/bin/b53-control-component.sh status > "$dir/release_manager_audit.txt" 2>&1 || true
      ;;
    *)
      echo "role $role has no B53 observation mapping" > "$dir/unsupported.txt"
      ;;
  esac
}

case_exercise_action() {
  case "$1" in
    inject-fault)
      case_inject_fault
      ;;
    mitigate|rollback|freeze-distribution|recover)
      b53_stage_recovery
      ;;
    validate-recovery)
      case_recovery_check
      ;;
    *)
      echo "unsupported B53 action $1" >&2
      return 2
      ;;
  esac
}

ab_main "$@"
