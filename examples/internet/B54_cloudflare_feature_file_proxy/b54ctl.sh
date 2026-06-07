#!/usr/bin/env bash
set -euo pipefail

CASE_ID="b54"
CASE_SLUG="cloudflare_feature_file_proxy"
CASE_GENERATOR="cloudflare_feature_file_proxy.py"
CONTAINER_PREFIX="${B54_CONTAINER_PREFIX:-b54-}"

source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../_agent_benchmark_common" && pwd)/agent_case_ctl_common.sh"
ab_init

SERVICE_IP="10.54.10.80"

B54_POPS=(iad sjc lhr sin gru syd ams canary)
B54_TAIL_SERVICES=(kv access turnstile dashboard)
B54_ORIGINS=(shop api media)
B54_CONTROL_COMPONENTS=(feature-db permission-rollout feature-generator feature-distributor known-good-store incident-console dashboard-control)

case_runtime_min_containers() {
  case "$1" in
    S0) printf '%s\n' 30 ;;
    S1) printf '%s\n' 160 ;;
    S1_5) printf '%s\n' 190 ;;
    S2) printf '%s\n' 225 ;;
    *) ab_require_tier "$1" ;;
  esac
}

b54_container_for_role() {
  case "$1" in
    frontend)
      printf '%sas54brd-Cloudflare_Core_Proxy_Router-10.54.10.254\n' "$CONTAINER_PREFIX"
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
      echo "unknown B54 role $1" >&2
      return 2
      ;;
  esac
}

b54_pop_ip() {
  case "$1" in
    iad) printf '%s\n' 10.54.10.11 ;;
    sjc) printf '%s\n' 10.54.10.12 ;;
    lhr) printf '%s\n' 10.54.10.13 ;;
    sin) printf '%s\n' 10.54.10.14 ;;
    gru) printf '%s\n' 10.54.10.15 ;;
    syd) printf '%s\n' 10.54.10.16 ;;
    ams) printf '%s\n' 10.54.10.17 ;;
    canary) printf '%s\n' 10.54.10.18 ;;
    *) return 2 ;;
  esac
}

b54_origin_ip() {
  case "$1" in
    shop) printf '%s\n' 10.56.10.80 ;;
    api) printf '%s\n' 10.56.10.81 ;;
    media) printf '%s\n' 10.56.10.82 ;;
    *) return 2 ;;
  esac
}

b54_pop_container() {
  local pop="$1"
  printf '%sas54h-Core_Proxy_POP_%s-%s\n' "$CONTAINER_PREFIX" "$(printf '%s' "$pop" | tr '[:lower:]' '[:upper:]')" "$(b54_pop_ip "$pop")"
}

b54_tail_container() {
  case "$1" in
    kv) printf '%sas54h-Workers_KV_Gateway-10.54.10.31\n' "$CONTAINER_PREFIX" ;;
    access) printf '%sas54h-Access_Gateway-10.54.10.32\n' "$CONTAINER_PREFIX" ;;
    turnstile) printf '%sas54h-Turnstile_Service-10.54.10.33\n' "$CONTAINER_PREFIX" ;;
    dashboard) printf '%sas54h-Dashboard_Service-10.54.10.34\n' "$CONTAINER_PREFIX" ;;
    *) return 2 ;;
  esac
}

b54_control_container() {
  case "$1" in
    feature-db) printf '%sas55h-Feature_DB-10.55.10.11\n' "$CONTAINER_PREFIX" ;;
    permission-rollout) printf '%sas55h-Permission_Rollout-10.55.10.12\n' "$CONTAINER_PREFIX" ;;
    feature-generator) printf '%sas55h-Feature_Generator-10.55.10.13\n' "$CONTAINER_PREFIX" ;;
    feature-distributor) printf '%sas55h-Feature_Distributor-10.55.10.14\n' "$CONTAINER_PREFIX" ;;
    known-good-store) printf '%sas55h-Known_Good_Store-10.55.10.15\n' "$CONTAINER_PREFIX" ;;
    incident-console) printf '%sas55h-Incident_Console-10.55.10.16\n' "$CONTAINER_PREFIX" ;;
    dashboard-control) printf '%sas55h-Dashboard_Control-10.55.10.17\n' "$CONTAINER_PREFIX" ;;
    *) return 2 ;;
  esac
}

b54_origin_container() {
  case "$1" in
    shop) printf '%sas56h-Customer_Origin_Shop-10.56.10.80\n' "$CONTAINER_PREFIX" ;;
    api) printf '%sas56h-Customer_Origin_API-10.56.10.81\n' "$CONTAINER_PREFIX" ;;
    media) printf '%sas56h-Customer_Origin_Media-10.56.10.82\n' "$CONTAINER_PREFIX" ;;
    *) return 2 ;;
  esac
}

b54_client_asns() {
  case "$(ab_canonical_tier "$TIER")" in
    S0) seq 80 83 ;;
    S1) { seq 80 99; seq 101 139; printf '250\n'; } ;;
    S1_5) { seq 80 99; seq 101 154; printf '250\n'; } ;;
    S2) { seq 80 99; seq 101 179; } ;;
  esac
}

b54_client_router() {
  local asn="$1"
  printf '%sas%sbrd-Client_Probe_Router_%s-10.%s.0.254\n' "$CONTAINER_PREFIX" "$asn" "$asn" "$asn"
}

b54_token() {
  printf '%s' "$1" | tr '-' '_'
}

b54_set_component_phase() {
  local phase="$1" item
  docker exec "$(b54_container_for_role frontend)" /usr/local/bin/b54-core-frontend.sh "$phase" >/dev/null
  for item in "${B54_CONTROL_COMPONENTS[@]}"; do
    docker exec "$(b54_control_container "$item")" /usr/local/bin/b54-control-component.sh "$phase" >/dev/null
  done
  for item in "${B54_POPS[@]}"; do
    docker exec "$(b54_pop_container "$item")" /usr/local/bin/b54-core-pop.sh "$phase" >/dev/null
  done
  for item in "${B54_TAIL_SERVICES[@]}"; do
    docker exec "$(b54_tail_container "$item")" /usr/local/bin/b54-tail-service.sh "$phase" >/dev/null
  done
}

b54_wait_http_code() {
  local container="$1" url="$2" expected="$3" out="$4" attempts="${5:-$(ab_runtime_attempts "$TIER")}"
  docker exec "$container" sh -lc "for i in \$(seq 1 $attempts); do code=\$(curl -sS --max-time 3 -o /tmp/b54-body.txt -w '%{http_code}' '$url' 2>$out.err || true); printf '%s\n' \"\$code\" | tee $out; [ \"\$code\" = '$expected' ] && exit 0; sleep 1; done; echo 'expected HTTP $expected from $url' >&2; cat $out >&2; cat $out.err >&2 || true; cat /tmp/b54-body.txt >&2 || true; exit 1"
}

b54_copy_tmp() {
  local container="$1" src="$2" dest="$3"
  docker cp "$container:$src" "$dest" >/dev/null
}

b54_capture_control_state() {
  local phase="$1" out item
  out="$ARTIFACT_DIR/${phase}_control_state.txt"
  {
    printf '== core_frontend ==\n'
    docker exec "$(b54_container_for_role frontend)" /usr/local/bin/b54-core-frontend.sh status 2>&1 || true
    printf '\n== control_plane ==\n'
    for item in "${B54_CONTROL_COMPONENTS[@]}"; do
      printf -- '-- %s --\n' "$item"
      docker exec "$(b54_control_container "$item")" /usr/local/bin/b54-control-component.sh status 2>&1 || true
    done
    printf '\n== core_proxy_pops ==\n'
    for item in "${B54_POPS[@]}"; do
      printf -- '-- %s --\n' "$item"
      docker exec "$(b54_pop_container "$item")" /usr/local/bin/b54-core-pop.sh status 2>&1 || true
    done
    printf '\n== tail_services ==\n'
    for item in "${B54_TAIL_SERVICES[@]}"; do
      printf -- '-- %s --\n' "$item"
      docker exec "$(b54_tail_container "$item")" /usr/local/bin/b54-tail-service.sh status 2>&1 || true
    done
    printf '\n== origins ==\n'
    for item in "${B54_ORIGINS[@]}"; do
      printf -- '-- %s --\n' "$item"
      docker exec "$(b54_origin_container "$item")" sh -lc "curl -fsS --max-time 2 http://127.0.0.1/" 2>&1 || true
    done
  } > "$out"
}

case_normal_check() {
  local asn container item
  b54_set_component_phase normal
  for item in "${B54_ORIGINS[@]}"; do
    docker exec "$(b54_origin_container "$item")" sh -lc "curl -fsS --max-time 2 http://127.0.0.1/" > "$ARTIFACT_DIR/normal_origin_${item}_health.txt"
  done
  for item in "${B54_TAIL_SERVICES[@]}"; do
    docker exec "$(b54_tail_container "$item")" sh -lc "curl -fsS --max-time 2 http://127.0.0.1:8080/" > "$ARTIFACT_DIR/normal_tail_${item}_health.txt"
  done
  while read -r asn; do
    container="$(b54_client_router "$asn")"
    b54_wait_http_code "$container" "http://$SERVICE_IP/" 200 "/tmp/b54-normal-http-$asn.txt"
    b54_copy_tmp "$container" /tmp/b54-normal-http-$asn.txt "$ARTIFACT_DIR/normal_client_http_$asn.txt"
  done < <(b54_client_asns)
  b54_capture_control_state normal
  grep -q 'incident_phase=normal' "$ARTIFACT_DIR/normal_control_state.txt"
  grep -q 'feature_file_count=24000' "$ARTIFACT_DIR/normal_control_state.txt"
  grep -q 'core_proxy=healthy' "$ARTIFACT_DIR/normal_control_state.txt"
  grep -q 'origin_health=healthy' "$ARTIFACT_DIR/normal_control_state.txt"
  ab_log "normal-runtime passed"
}

case_inject_fault() {
  b54_set_component_phase fault
  sleep 3
}

case_fault_check() {
  local asn container item
  for item in "${B54_ORIGINS[@]}"; do
    docker exec "$(b54_origin_container "$item")" sh -lc "curl -fsS --max-time 2 http://127.0.0.1/" > "$ARTIFACT_DIR/fault_origin_${item}_still_healthy.txt"
  done
  docker exec "$(b54_pop_container iad)" sh -lc "curl -sS --max-time 2 -o /tmp/b54-pop-body.txt -w '%{http_code}\n' http://127.0.0.1:8080/" > "$ARTIFACT_DIR/fault_core_pop_iad_http.txt" || true
  docker exec "$(b54_tail_container kv)" sh -lc "curl -sS --max-time 2 -o /tmp/b54-tail-kv-body.txt -w '%{http_code}\n' http://127.0.0.1:8080/" > "$ARTIFACT_DIR/fault_tail_kv_http.txt" || true
  while read -r asn; do
    container="$(b54_client_router "$asn")"
    b54_wait_http_code "$container" "http://$SERVICE_IP/" 503 "/tmp/b54-fault-http-$asn.txt"
    b54_copy_tmp "$container" /tmp/b54-fault-http-$asn.txt "$ARTIFACT_DIR/fault_client_http_$asn.txt"
  done < <(b54_client_asns)
  b54_capture_control_state fault
  grep -q 'root_cause=feature_file_count_and_size_exceeded_core_proxy_limit' "$ARTIFACT_DIR/fault_control_state.txt"
  grep -q 'feature_db=expanded_permissions' "$ARTIFACT_DIR/fault_control_state.txt"
  grep -q 'permission_rollout=new_acl_active' "$ARTIFACT_DIR/fault_control_state.txt"
  grep -q 'feature_generator=runaway' "$ARTIFACT_DIR/fault_control_state.txt"
  grep -q 'feature_file_count=1250000' "$ARTIFACT_DIR/fault_control_state.txt"
  grep -q 'feature_file_size_mb=920' "$ARTIFACT_DIR/fault_control_state.txt"
  grep -q 'feature_distributor=global_bad_file' "$ARTIFACT_DIR/fault_control_state.txt"
  grep -q 'known_good_store=available' "$ARTIFACT_DIR/fault_control_state.txt"
  grep -q 'core_proxy=5xx' "$ARTIFACT_DIR/fault_control_state.txt"
  grep -q 'tail_service_status=degraded_by_core_proxy' "$ARTIFACT_DIR/fault_control_state.txt"
  grep -q 'origin_health=healthy' "$ARTIFACT_DIR/fault_control_state.txt"
  ab_log "fault-runtime passed"
}

b54_stage_recovery() {
  b54_set_component_phase recovery
  sleep 3
}

case_recovery_check() {
  local asn container item
  b54_stage_recovery
  for item in "${B54_TAIL_SERVICES[@]}"; do
    docker exec "$(b54_tail_container "$item")" sh -lc "curl -fsS --max-time 2 http://127.0.0.1:8080/" > "$ARTIFACT_DIR/recovery_tail_${item}_health.txt"
  done
  while read -r asn; do
    container="$(b54_client_router "$asn")"
    b54_wait_http_code "$container" "http://$SERVICE_IP/" 200 "/tmp/b54-recovery-http-$asn.txt"
    b54_copy_tmp "$container" /tmp/b54-recovery-http-$asn.txt "$ARTIFACT_DIR/recovery_client_http_$asn.txt"
  done < <(b54_client_asns)
  b54_capture_control_state recovery
  grep -q 'feature_generator=stopped' "$ARTIFACT_DIR/recovery_control_state.txt"
  grep -q 'feature_distributor=stopped_then_known_good' "$ARTIFACT_DIR/recovery_control_state.txt"
  grep -q 'known_good_store=restored_feature_set_20260606' "$ARTIFACT_DIR/recovery_control_state.txt"
  grep -q 'bot_module=fail_small' "$ARTIFACT_DIR/recovery_control_state.txt"
  grep -q 'tail_services=validated' "$ARTIFACT_DIR/recovery_control_state.txt"
  grep -q 'tail_service_status=validated' "$ARTIFACT_DIR/recovery_control_state.txt"
  grep -q 'canary_passed=yes' "$ARTIFACT_DIR/recovery_control_state.txt"
  grep -q 'recovery_complete=yes' "$ARTIFACT_DIR/recovery_control_state.txt"
  ab_log "recovery-runtime passed"
}

case_collect() {
  local item
  b54_capture_control_state collect
  docker exec "$(b54_container_for_role frontend)" sh -lc "cat /var/log/b54-core-frontend.log 2>/dev/null || true; printf '\n== status ==\n'; /usr/local/bin/b54-core-frontend.sh status" > "$ARTIFACT_DIR/core_frontend_collect.txt" 2>&1 || true
  for item in "${B54_CONTROL_COMPONENTS[@]}"; do
    docker exec "$(b54_control_container "$item")" sh -lc "cat /var/log/b54-$item.log 2>/dev/null || true; printf '\n== status ==\n'; /usr/local/bin/b54-control-component.sh status" > "$ARTIFACT_DIR/control_$(b54_token "$item")_collect.txt" 2>&1 || true
  done
  for item in "${B54_POPS[@]}"; do
    docker exec "$(b54_pop_container "$item")" sh -lc "cat /var/log/b54-core-pop-$item.log 2>/dev/null || true; printf '\n== status ==\n'; /usr/local/bin/b54-core-pop.sh status" > "$ARTIFACT_DIR/pop_${item}_collect.txt" 2>&1 || true
  done
  for item in "${B54_TAIL_SERVICES[@]}"; do
    docker exec "$(b54_tail_container "$item")" sh -lc "cat /var/log/b54-tail-$item.log 2>/dev/null || true; printf '\n== status ==\n'; /usr/local/bin/b54-tail-service.sh status" > "$ARTIFACT_DIR/tail_${item}_collect.txt" 2>&1 || true
  done
  docker exec "$(b54_container_for_role ops)" sh -lc "birdc show route 10.54.10.0/24 all 2>&1 || true; printf '\n== frontend curl ==\n'; curl -sS --max-time 3 -i http://$SERVICE_IP/ 2>&1 || true" > "$ARTIFACT_DIR/ops_view_collect.txt" 2>&1 || true
}

case_exercise_observe_one() {
  local role="$1" dir="$2" asn container
  mkdir -p "$dir"
  case "$role" in
    public-users)
      for asn in "$(b54_client_asns | ab_first_line)" "$(b54_client_asns | ab_last_line)"; do
        container="$(b54_client_router "$asn")"
        docker exec "$container" sh -lc "curl -sS --max-time 3 -i http://$SERVICE_IP/ 2>&1 || true" > "$dir/as${asn}_customer_http.txt" 2>&1 || true
      done
      ;;
    provider-ops|service-ops)
      docker exec "$(b54_pop_container iad)" /usr/local/bin/b54-core-pop.sh status > "$dir/core_pop_iad_status.txt" 2>&1 || true
      docker exec "$(b54_tail_container kv)" /usr/local/bin/b54-tail-service.sh status > "$dir/kv_tail_status.txt" 2>&1 || true
      docker exec "$(b54_tail_container access)" /usr/local/bin/b54-tail-service.sh status > "$dir/access_tail_status.txt" 2>&1 || true
      docker exec "$(b54_origin_container shop)" sh -lc "curl -fsS --max-time 2 http://127.0.0.1/ 2>&1 || true" > "$dir/shop_origin_health.txt" 2>&1 || true
      docker exec "$(b54_container_for_role frontend)" /usr/local/bin/b54-core-frontend.sh status > "$dir/core_frontend_status.txt" 2>&1 || true
      ;;
    network-ops|route-collectors)
      docker exec "$(b54_container_for_role ops)" sh -lc "birdc show route 10.54.10.0/24 all 2>&1 || true; printf '\n== protocols ==\n'; birdc show protocols 2>&1 || true" > "$dir/route_view.txt" 2>&1 || true
      ;;
    control-plane|change-audit)
      b54_capture_control_state observe
      cp "$ARTIFACT_DIR/observe_control_state.txt" "$dir/control_state.txt"
      docker exec "$(b54_control_container permission-rollout)" /usr/local/bin/b54-control-component.sh status > "$dir/permission_rollout_audit.txt" 2>&1 || true
      docker exec "$(b54_control_container feature-generator)" /usr/local/bin/b54-control-component.sh status > "$dir/feature_generator_audit.txt" 2>&1 || true
      docker exec "$(b54_control_container known-good-store)" /usr/local/bin/b54-control-component.sh status > "$dir/known_good_audit.txt" 2>&1 || true
      ;;
    *)
      echo "role $role has no B54 observation mapping" > "$dir/unsupported.txt"
      ;;
  esac
}

case_exercise_action() {
  case "$1" in
    inject-fault)
      case_inject_fault
      ;;
    mitigate|rollback|rollback-known-good|recover)
      b54_stage_recovery
      ;;
    validate-recovery)
      case_recovery_check
      ;;
    *)
      echo "unsupported B54 action $1" >&2
      return 2
      ;;
  esac
}

ab_main "$@"
