#!/usr/bin/env bash
set -euo pipefail

CASE_ID="b57"
CASE_SLUG="google_network_congestion"
CASE_GENERATOR="google_network_congestion.py"
CONTAINER_PREFIX="${B57_CONTAINER_PREFIX:-b57-}"

source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../_agent_benchmark_common" && pwd)/agent_case_ctl_common.sh"
ab_init

SERVICE_IP="10.57.10.80"
SERVICE_PREFIX="10.57.10.0/24"

B57_REGIONS=(us-east1 us-east4 us-central1 us-west1 us-west2 eu-west1 asia-east1 canary)
B57_CONTROL_COMPONENTS=(maintenance-automation cluster-manager-loc-a cluster-manager-loc-b cluster-manager-loc-c network-control-plane-a network-control-plane-b network-control-plane-c config-store route-distributor te-controller ops-tooling)
B57_WORKLOADS=(gce-api cloud-storage app-engine vpn-endpoint console customer-project)

case_runtime_min_containers() {
  case "$1" in
    S0) printf '%s\n' 35 ;;
    S1) printf '%s\n' 166 ;;
    S1_5) printf '%s\n' 194 ;;
    S2) printf '%s\n' 245 ;;
    *) ab_require_tier "$1" ;;
  esac
}

b57_container_for_role() {
  case "$1" in
    frontend)
      printf '%sas57brd-Google_Edge_Router-10.57.10.254\n' "$CONTAINER_PREFIX"
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
      echo "unknown B57 role $1" >&2
      return 2
      ;;
  esac
}

b57_region_ip() {
  case "$1" in
    us-east1) printf '%s\n' 10.57.10.11 ;;
    us-east4) printf '%s\n' 10.57.10.12 ;;
    us-central1) printf '%s\n' 10.57.10.13 ;;
    us-west1) printf '%s\n' 10.57.10.14 ;;
    us-west2) printf '%s\n' 10.57.10.15 ;;
    eu-west1) printf '%s\n' 10.57.10.16 ;;
    asia-east1) printf '%s\n' 10.57.10.17 ;;
    canary) printf '%s\n' 10.57.10.18 ;;
    *) return 2 ;;
  esac
}

b57_workload_ip() {
  case "$1" in
    gce-api) printf '%s\n' 10.59.10.80 ;;
    cloud-storage) printf '%s\n' 10.59.10.81 ;;
    app-engine) printf '%s\n' 10.59.10.82 ;;
    vpn-endpoint) printf '%s\n' 10.59.10.83 ;;
    console) printf '%s\n' 10.59.10.84 ;;
    customer-project) printf '%s\n' 10.59.10.85 ;;
    *) return 2 ;;
  esac
}

b57_region_display() {
  case "$1" in
    us-east1) printf '%s\n' "US_East_1_Frontend" ;;
    us-east4) printf '%s\n' "US_East_4_Frontend" ;;
    us-central1) printf '%s\n' "US_Central_1_Frontend" ;;
    us-west1) printf '%s\n' "US_West_1_Frontend" ;;
    us-west2) printf '%s\n' "US_West_2_Frontend" ;;
    eu-west1) printf '%s\n' "EU_West_1_Frontend" ;;
    asia-east1) printf '%s\n' "Asia_East_1_Frontend" ;;
    canary) printf '%s\n' "Canary_Region_Frontend" ;;
    *) return 2 ;;
  esac
}

b57_region_container() {
  local region="$1"
  printf '%sas57h-%s-%s\n' "$CONTAINER_PREFIX" "$(b57_region_display "$region")" "$(b57_region_ip "$region")"
}

b57_control_container() {
  case "$1" in
    maintenance-automation) printf '%sas58h-Maintenance_Automation-10.58.10.11\n' "$CONTAINER_PREFIX" ;;
    cluster-manager-loc-a) printf '%sas58h-Cluster_Manager_Loc_A-10.58.10.12\n' "$CONTAINER_PREFIX" ;;
    cluster-manager-loc-b) printf '%sas58h-Cluster_Manager_Loc_B-10.58.10.13\n' "$CONTAINER_PREFIX" ;;
    cluster-manager-loc-c) printf '%sas58h-Cluster_Manager_Loc_C-10.58.10.14\n' "$CONTAINER_PREFIX" ;;
    network-control-plane-a) printf '%sas58h-Network_Control_Plane_A-10.58.10.21\n' "$CONTAINER_PREFIX" ;;
    network-control-plane-b) printf '%sas58h-Network_Control_Plane_B-10.58.10.22\n' "$CONTAINER_PREFIX" ;;
    network-control-plane-c) printf '%sas58h-Network_Control_Plane_C-10.58.10.23\n' "$CONTAINER_PREFIX" ;;
    config-store) printf '%sas58h-Config_Store-10.58.10.31\n' "$CONTAINER_PREFIX" ;;
    route-distributor) printf '%sas58h-Route_Distributor-10.58.10.32\n' "$CONTAINER_PREFIX" ;;
    te-controller) printf '%sas58h-TE_Controller-10.58.10.33\n' "$CONTAINER_PREFIX" ;;
    ops-tooling) printf '%sas58h-Ops_Tooling-10.58.10.34\n' "$CONTAINER_PREFIX" ;;
    *) return 2 ;;
  esac
}

b57_workload_container() {
  case "$1" in
    gce-api) printf '%sas59h-GCE_API_Workload-10.59.10.80\n' "$CONTAINER_PREFIX" ;;
    cloud-storage) printf '%sas59h-Cloud_Storage_Workload-10.59.10.81\n' "$CONTAINER_PREFIX" ;;
    app-engine) printf '%sas59h-App_Engine_Workload-10.59.10.82\n' "$CONTAINER_PREFIX" ;;
    vpn-endpoint) printf '%sas59h-Cloud_VPN_Endpoint-10.59.10.83\n' "$CONTAINER_PREFIX" ;;
    console) printf '%sas59h-Cloud_Console_Workload-10.59.10.84\n' "$CONTAINER_PREFIX" ;;
    customer-project) printf '%sas59h-Customer_Project_Workload-10.59.10.85\n' "$CONTAINER_PREFIX" ;;
    *) return 2 ;;
  esac
}

b57_client_asns() {
  case "$(ab_canonical_tier "$TIER")" in
    S0) seq 80 83 ;;
    S1) { seq 80 99; seq 101 139; printf '250\n'; } ;;
    S1_5) { seq 80 99; seq 101 154; printf '250\n'; } ;;
    S2) { seq 80 99; seq 101 179; } ;;
  esac
}

b57_client_router() {
  local asn="$1"
  printf '%sas%sbrd-Client_Probe_Router_%s-10.%s.0.254\n' "$CONTAINER_PREFIX" "$asn" "$asn" "$asn"
}

b57_token() {
  printf '%s' "$1" | tr '-' '_'
}

b57_set_component_phase() {
  local phase="$1" item
  docker exec "$(b57_container_for_role frontend)" /usr/local/bin/b57-edge-frontend.sh "$phase" >/dev/null
  for item in "${B57_REGIONS[@]}"; do
    docker exec "$(b57_region_container "$item")" /usr/local/bin/b57-region-frontend.sh "$phase" >/dev/null
  done
  for item in "${B57_CONTROL_COMPONENTS[@]}"; do
    docker exec "$(b57_control_container "$item")" /usr/local/bin/b57-control-component.sh "$phase" >/dev/null
  done
  for item in "${B57_WORKLOADS[@]}"; do
    docker exec "$(b57_workload_container "$item")" /usr/local/bin/b57-workload.sh "$phase" >/dev/null
  done
}

b57_route_control() {
  docker exec "$(b57_container_for_role frontend)" /usr/local/bin/b57-route-control.sh "$1" >/dev/null
}

b57_wait_route_present() {
  local container="$1" out="$2" attempts="${3:-$(ab_runtime_attempts "$TIER")}"
  docker exec "$container" sh -lc "for i in \$(seq 1 $attempts); do birdc show route $SERVICE_PREFIX all 2>&1 | tee $out; grep -q '$SERVICE_PREFIX' $out && exit 0; sleep 1; done; echo 'route $SERVICE_PREFIX not present after $attempts attempts' >&2; cat $out >&2; exit 1"
}

b57_wait_route_absent() {
  local container="$1" out="$2" attempts="${3:-$(ab_runtime_attempts "$TIER")}"
  docker exec "$container" sh -lc "for i in \$(seq 1 $attempts); do birdc show route $SERVICE_PREFIX all 2>&1 | tee $out; ! grep -q '$SERVICE_PREFIX' $out && exit 0; sleep 1; done; echo 'route $SERVICE_PREFIX still present after $attempts attempts' >&2; cat $out >&2; exit 1"
}

b57_wait_http_code() {
  local container="$1" url="$2" expected="$3" out="$4" attempts="${5:-$(ab_runtime_attempts "$TIER")}"
  docker exec "$container" sh -lc "for i in \$(seq 1 $attempts); do code=\$(curl -sS --max-time 3 -o /tmp/b57-body.txt -w '%{http_code}' '$url' 2>$out.err || true); printf '%s\n' \"\$code\" | tee $out; [ \"\$code\" = '$expected' ] && exit 0; sleep 1; done; echo 'expected HTTP $expected from $url' >&2; cat $out >&2; cat $out.err >&2 || true; cat /tmp/b57-body.txt >&2 || true; exit 1"
}

b57_copy_tmp() {
  local container="$1" src="$2" dest="$3"
  docker cp "$container:$src" "$dest" >/dev/null
}

b57_capture_control_state() {
  local phase="$1" out item
  out="$ARTIFACT_DIR/${phase}_control_state.txt"
  {
    printf '== edge_frontend ==\n'
    docker exec "$(b57_container_for_role frontend)" /usr/local/bin/b57-edge-frontend.sh status 2>&1 || true
    printf '\n== route_control ==\n'
    docker exec "$(b57_container_for_role frontend)" /usr/local/bin/b57-route-control.sh status 2>&1 || true
    printf '\n== control_plane ==\n'
    for item in "${B57_CONTROL_COMPONENTS[@]}"; do
      printf -- '-- %s --\n' "$item"
      docker exec "$(b57_control_container "$item")" /usr/local/bin/b57-control-component.sh status 2>&1 || true
    done
    printf '\n== region_frontends ==\n'
    for item in "${B57_REGIONS[@]}"; do
      printf -- '-- %s --\n' "$item"
      docker exec "$(b57_region_container "$item")" /usr/local/bin/b57-region-frontend.sh status 2>&1 || true
    done
    printf '\n== workloads ==\n'
    for item in "${B57_WORKLOADS[@]}"; do
      printf -- '-- %s --\n' "$item"
      docker exec "$(b57_workload_container "$item")" /usr/local/bin/b57-workload.sh status 2>&1 || true
    done
  } > "$out"
}

case_normal_check() {
  local asn container item
  b57_set_component_phase normal
  b57_route_control normal
  sleep 4
  for item in "${B57_WORKLOADS[@]}"; do
    docker exec "$(b57_workload_container "$item")" sh -lc "curl -fsS --max-time 2 http://127.0.0.1:8080/" > "$ARTIFACT_DIR/normal_workload_${item}_health.txt"
  done
  while read -r asn; do
    container="$(b57_client_router "$asn")"
    b57_wait_route_present "$container" "/tmp/b57-normal-route-$asn.txt"
    b57_wait_http_code "$container" "http://$SERVICE_IP/" 200 "/tmp/b57-normal-http-$asn.txt"
    b57_copy_tmp "$container" /tmp/b57-normal-http-$asn.txt "$ARTIFACT_DIR/normal_client_http_$asn.txt"
  done < <(b57_client_asns)
  b57_capture_control_state normal
  grep -q 'network_control_plane=running' "$ARTIFACT_DIR/normal_control_state.txt"
  grep -q 'bgp_state=stable' "$ARTIFACT_DIR/normal_control_state.txt"
  grep -q 'workload_health=healthy' "$ARTIFACT_DIR/normal_control_state.txt"
  ab_log "normal-runtime passed"
}

case_inject_fault() {
  b57_set_component_phase fault
  b57_route_control fault
  sleep 8
}

case_fault_check() {
  local asn container item
  docker exec "$(b57_container_for_role frontend)" sh -lc "curl -fsS --max-time 2 http://127.0.0.1/" > "$ARTIFACT_DIR/fault_edge_frontend_local_alive.txt"
  for item in "${B57_WORKLOADS[@]}"; do
    docker exec "$(b57_workload_container "$item")" sh -lc "curl -fsS --max-time 2 http://127.0.0.1:8080/" > "$ARTIFACT_DIR/fault_workload_${item}_still_healthy.txt"
  done
  while read -r asn; do
    container="$(b57_client_router "$asn")"
    b57_wait_route_absent "$container" "/tmp/b57-fault-route-$asn.txt"
    b57_wait_http_code "$container" "http://$SERVICE_IP/" 000 "/tmp/b57-fault-http-$asn.txt" 3
    b57_copy_tmp "$container" /tmp/b57-fault-http-$asn.txt "$ARTIFACT_DIR/fault_client_http_$asn.txt"
    b57_copy_tmp "$container" /tmp/b57-fault-route-$asn.txt "$ARTIFACT_DIR/fault_client_route_$asn.txt"
  done < <(b57_client_asns)
  b57_capture_control_state fault
  grep -q 'root_cause=maintenance_automation_descheduled_network_control_plane' "$ARTIFACT_DIR/fault_control_state.txt"
  grep -q 'maintenance_automation=unsafe_global_deschedule' "$ARTIFACT_DIR/fault_control_state.txt"
  grep -q 'network_control_plane=down' "$ARTIFACT_DIR/fault_control_state.txt"
  grep -q 'route_distributor=fail_static_expired' "$ARTIFACT_DIR/fault_control_state.txt"
  grep -q 'te_controller=congested' "$ARTIFACT_DIR/fault_control_state.txt"
  grep -q 'bgp_state=withdrawn_or_degraded' "$ARTIFACT_DIR/fault_control_state.txt"
  grep -q 'external_route=10.57.10.0/24 withdrawn' "$ARTIFACT_DIR/fault_control_state.txt"
  grep -q 'workload_health=healthy' "$ARTIFACT_DIR/fault_control_state.txt"
  ab_log "fault-runtime passed"
}

b57_stage_recovery() {
  b57_set_component_phase recovery
  b57_route_control recovery
  sleep 8
}

case_recovery_check() {
  local asn container
  b57_stage_recovery
  while read -r asn; do
    container="$(b57_client_router "$asn")"
    b57_wait_route_present "$container" "/tmp/b57-recovery-route-$asn.txt"
    b57_wait_http_code "$container" "http://$SERVICE_IP/" 200 "/tmp/b57-recovery-http-$asn.txt"
    b57_copy_tmp "$container" /tmp/b57-recovery-http-$asn.txt "$ARTIFACT_DIR/recovery_client_http_$asn.txt"
  done < <(b57_client_asns)
  b57_capture_control_state recovery
  grep -q 'maintenance_automation=halted' "$ARTIFACT_DIR/recovery_control_state.txt"
  grep -q 'network_control_plane=running' "$ARTIFACT_DIR/recovery_control_state.txt"
  grep -q 'config_store=rebuild_passed' "$ARTIFACT_DIR/recovery_control_state.txt"
  grep -q 'route_distributor=distributed' "$ARTIFACT_DIR/recovery_control_state.txt"
  grep -q 'bgp_state=stable' "$ARTIFACT_DIR/recovery_control_state.txt"
  grep -q 'region_verification=passed' "$ARTIFACT_DIR/recovery_control_state.txt"
  grep -q 'recovery_complete=yes' "$ARTIFACT_DIR/recovery_control_state.txt"
  ab_log "recovery-runtime passed"
}

case_collect() {
  local item
  b57_capture_control_state collect
  docker exec "$(b57_container_for_role frontend)" sh -lc "cat /var/log/b57-route-control.log 2>/dev/null || true; printf '\n== route status ==\n'; /usr/local/bin/b57-route-control.sh status; printf '\n== frontend ==\n'; /usr/local/bin/b57-edge-frontend.sh status" > "$ARTIFACT_DIR/edge_route_collect.txt" 2>&1 || true
  for item in "${B57_CONTROL_COMPONENTS[@]}"; do
    docker exec "$(b57_control_container "$item")" sh -lc "cat /var/log/b57-$item.log 2>/dev/null || true; printf '\n== status ==\n'; /usr/local/bin/b57-control-component.sh status" > "$ARTIFACT_DIR/control_$(b57_token "$item")_collect.txt" 2>&1 || true
  done
  docker exec "$(b57_container_for_role ops)" sh -lc "birdc show route $SERVICE_PREFIX all 2>&1 || true; printf '\n== frontend curl ==\n'; curl -sS --max-time 3 -i http://$SERVICE_IP/ 2>&1 || true" > "$ARTIFACT_DIR/ops_view_collect.txt" 2>&1 || true
}

case_exercise_observe_one() {
  local role="$1" dir="$2" asn container
  mkdir -p "$dir"
  case "$role" in
    public-users)
      for asn in "$(b57_client_asns | ab_first_line)" "$(b57_client_asns | ab_last_line)"; do
        container="$(b57_client_router "$asn")"
        docker exec "$container" sh -lc "printf '== curl ==\n'; curl -sS --max-time 3 -i http://$SERVICE_IP/ 2>&1 || true; printf '\n== route ==\n'; birdc show route $SERVICE_PREFIX all 2>&1 || true" > "$dir/as${asn}_user_path.txt" 2>&1 || true
      done
      ;;
    provider-ops|service-ops)
      docker exec "$(b57_container_for_role frontend)" sh -lc "curl -fsS --max-time 2 http://127.0.0.1/ 2>&1 || true; printf '\n== frontend state ==\n'; /usr/local/bin/b57-edge-frontend.sh status" > "$dir/edge_frontend_local.txt" 2>&1 || true
      docker exec "$(b57_workload_container gce-api)" /usr/local/bin/b57-workload.sh status > "$dir/gce_api_workload_status.txt" 2>&1 || true
      docker exec "$(b57_region_container us-east1)" /usr/local/bin/b57-region-frontend.sh status > "$dir/us_east1_region_status.txt" 2>&1 || true
      ;;
    network-ops|route-collectors)
      docker exec "$(b57_container_for_role ops)" sh -lc "birdc show route $SERVICE_PREFIX all 2>&1 || true; printf '\n== protocols ==\n'; birdc show protocols 2>&1 || true" > "$dir/route_view.txt" 2>&1 || true
      docker exec "$(b57_container_for_role frontend)" /usr/local/bin/b57-route-control.sh status > "$dir/edge_route_control.txt" 2>&1 || true
      ;;
    control-plane|change-audit)
      b57_capture_control_state observe
      cp "$ARTIFACT_DIR/observe_control_state.txt" "$dir/control_state.txt"
      docker exec "$(b57_control_container maintenance-automation)" /usr/local/bin/b57-control-component.sh status > "$dir/maintenance_automation_audit.txt" 2>&1 || true
      docker exec "$(b57_control_container route-distributor)" /usr/local/bin/b57-control-component.sh status > "$dir/route_distributor_audit.txt" 2>&1 || true
      docker exec "$(b57_control_container te-controller)" /usr/local/bin/b57-control-component.sh status > "$dir/te_controller_audit.txt" 2>&1 || true
      ;;
    *)
      echo "role $role has no B57 observation mapping" > "$dir/unsupported.txt"
      ;;
  esac
}

case_exercise_action() {
  case "$1" in
    inject-fault)
      case_inject_fault
      ;;
    mitigate|restore-control-plane|halt-automation|recover)
      b57_stage_recovery
      ;;
    validate-recovery)
      case_recovery_check
      ;;
    *)
      echo "unsupported B57 action $1" >&2
      return 2
      ;;
  esac
}

ab_main "$@"
