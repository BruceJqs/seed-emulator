#!/usr/bin/env bash
set -euo pipefail

CASE_ID="b55"
CASE_SLUG="verizon_route_leak"
CASE_GENERATOR="verizon_route_leak.py"
CONTAINER_PREFIX="${B55_CONTAINER_PREFIX:-b55-}"

source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../_agent_benchmark_common" && pwd)/agent_case_ctl_common.sh"
ab_init

VICTIM_PREFIX="10.55.0.0/24"
LEAK_PREFIX="10.55.0.0/25"
VICTIM_URL="http://10.55.0.80/"
DQE_ROUTER="${CONTAINER_PREFIX}as702brd-DQE_BGP_Optimizer_Router-10.70.2.254"
VICTIM_EDGE="${CONTAINER_PREFIX}as55brd-Victim_CDN_Router-10.55.0.254"

case_runtime_min_containers() {
  case "$1" in
    S0) printf '%s\n' 11 ;;
    S1) printf '%s\n' 137 ;;
    S1_5) printf '%s\n' 177 ;;
    S2) printf '%s\n' 177 ;;
    *) ab_require_tier "$1" ;;
  esac
}

b55_router_for_asn() {
  local asn="$1"
  case "$asn" in
    55) printf '%sas55brd-Victim_CDN_Router-10.55.0.254\n' "$CONTAINER_PREFIX" ;;
    56) printf '%sas56brd-Legitimate_Transit_Router-10.56.0.254\n' "$CONTAINER_PREFIX" ;;
    57) printf '%sas57brd-Filtered_Transit_Router-10.57.0.254\n' "$CONTAINER_PREFIX" ;;
    701) printf '%sas701brd-Verizon_AS701_Router-10.70.1.254\n' "$CONTAINER_PREFIX" ;;
    702) printf '%sas702brd-DQE_BGP_Optimizer_Router-10.70.2.254\n' "$CONTAINER_PREFIX" ;;
    703) printf '%sas703brd-Allegheny_Customer_Router-10.70.3.254\n' "$CONTAINER_PREFIX" ;;
    *)
      if b55_asn_in_list "$asn" b55_unfiltered_probe_asns; then
        printf '%sas%sbrd-Unfiltered_Probe_Router_%s-10.%s.0.254\n' "$CONTAINER_PREFIX" "$asn" "$asn" "$asn"
      elif b55_asn_in_list "$asn" b55_filtered_probe_asns; then
        printf '%sas%sbrd-Filtered_Probe_Router_%s-10.%s.0.254\n' "$CONTAINER_PREFIX" "$asn" "$asn" "$asn"
      elif b55_asn_in_list "$asn" b55_collector_asns; then
        printf '%sas%sbrd-Route_Collector_Router_%s-10.%s.0.254\n' "$CONTAINER_PREFIX" "$asn" "$asn" "$asn"
      else
        printf '%sas%sbrd-Background_AS_Router_%s-10.%s.0.254\n' "$CONTAINER_PREFIX" "$asn" "$asn" "$asn"
      fi
      ;;
  esac
}

b55_asn_in_list() {
  local wanted="$1" list_fn="$2" candidate
  while read -r candidate; do
    [ "$candidate" = "$wanted" ] && return 0
  done < <("$list_fn")
  return 1
}

b55_unfiltered_probe_asns() {
  case "$(ab_canonical_tier "$TIER")" in
    S0) printf '80\n81\n' ;;
    S1) { seq 80 99; seq 101 125; printf '250\n'; } ;;
    S1_5) { seq 80 99; seq 101 144; printf '250\n'; } ;;
    S2) { seq 80 99; seq 101 169; printf '255\n'; } ;;
  esac
}

b55_filtered_probe_asns() {
  case "$(ab_canonical_tier "$TIER")" in
    S0) printf '90\n' ;;
    S1) seq 126 145 ;;
    S1_5) seq 145 169 ;;
    S2) seq 170 219 ;;
  esac
}

b55_collector_asns() {
  case "$(ab_canonical_tier "$TIER")" in
    S0) printf '101\n' ;;
    S1) seq 160 169 ;;
    S1_5) seq 170 185 ;;
    S2) seq 220 244 ;;
  esac
}

b55_wait_route_present() {
  local container="$1" prefix="$2" out="$3" attempts="${4:-$(ab_runtime_attempts "$TIER")}"
  docker exec "$container" sh -lc "for i in \$(seq 1 $attempts); do birdc show route $prefix all 2>&1 | tee $out; grep -q '$prefix' $out && exit 0; sleep 1; done; echo 'route $prefix not present after $attempts attempts' >&2; cat $out >&2; exit 1"
}

b55_wait_route_absent() {
  local container="$1" prefix="$2" out="$3" attempts="${4:-$(ab_runtime_attempts "$TIER")}"
  docker exec "$container" sh -lc "for i in \$(seq 1 $attempts); do birdc show route $prefix all 2>&1 | tee $out; ! grep -q '$prefix' $out && exit 0; sleep 1; done; echo 'route $prefix still present after $attempts attempts' >&2; cat $out >&2; exit 1"
}

case_normal_check() {
  local asn container
  ab_log "checking victim service remains healthy"
  docker exec "$VICTIM_EDGE" sh -lc "curl -fsS --max-time 2 http://127.0.0.1/" > "$ARTIFACT_DIR/normal_victim_local_health.txt"

  while read -r asn; do
    [ -n "$asn" ] || continue
    container="$(b55_router_for_asn "$asn")"
    ab_log "checking unfiltered AS$asn reaches victim aggregate before leak"
    b55_wait_route_present "$container" "$VICTIM_PREFIX" "/tmp/b55-normal-aggregate-$asn.txt"
    b55_wait_route_absent "$container" "$LEAK_PREFIX" "/tmp/b55-normal-leak-$asn.txt"
    docker exec "$container" sh -lc "curl -fsS --max-time 3 $VICTIM_URL" > "$ARTIFACT_DIR/normal_unfiltered_curl_$asn.txt"
  done < <(b55_unfiltered_probe_asns)

  while read -r asn; do
    [ -n "$asn" ] || continue
    container="$(b55_router_for_asn "$asn")"
    ab_log "checking filtered AS$asn reaches victim aggregate before leak"
    b55_wait_route_present "$container" "$VICTIM_PREFIX" "/tmp/b55-normal-filtered-aggregate-$asn.txt"
    b55_wait_route_absent "$container" "$LEAK_PREFIX" "/tmp/b55-normal-filtered-leak-$asn.txt"
    docker exec "$container" sh -lc "curl -fsS --max-time 3 $VICTIM_URL" > "$ARTIFACT_DIR/normal_filtered_curl_$asn.txt"
  done < <(b55_filtered_probe_asns)

  ab_log "normal-runtime passed"
}

case_inject_fault() {
  ab_log "injecting route leak by enabling DQE export session to Allegheny"
  docker exec "$DQE_ROUTER" /usr/local/bin/b55-dqe-control.sh inject
  sleep 10
}

case_fault_check() {
  local asn container first_unfiltered first_filtered collector
  first_unfiltered="$(b55_unfiltered_probe_asns | ab_first_line)"
  first_filtered="$(b55_filtered_probe_asns | ab_first_line)"

  while read -r asn; do
    [ -n "$asn" ] || continue
    container="$(b55_router_for_asn "$asn")"
    ab_log "checking unfiltered AS$asn accepted leaked more-specific"
    b55_wait_route_present "$container" "$LEAK_PREFIX" "/tmp/b55-fault-leak-$asn.txt"
    docker cp "$container:/tmp/b55-fault-leak-$asn.txt" "$ARTIFACT_DIR/fault_unfiltered_route_$asn.txt" >/dev/null
  done < <(b55_unfiltered_probe_asns)

  while read -r asn; do
    [ -n "$asn" ] || continue
    container="$(b55_router_for_asn "$asn")"
    ab_log "checking filtered AS$asn rejects leaked more-specific"
    b55_wait_route_absent "$container" "$LEAK_PREFIX" "/tmp/b55-fault-filtered-leak-$asn.txt"
    docker exec "$container" sh -lc "curl -fsS --max-time 3 $VICTIM_URL" > "$ARTIFACT_DIR/fault_filtered_curl_$asn.txt"
  done < <(b55_filtered_probe_asns)

  collector="$(b55_router_for_asn "$(b55_collector_asns | ab_first_line)")"
  b55_wait_route_present "$collector" "$LEAK_PREFIX" "/tmp/b55-fault-collector-leak.txt"
  docker cp "$collector:/tmp/b55-fault-collector-leak.txt" "$ARTIFACT_DIR/fault_route_collector_leak.txt" >/dev/null
  docker exec "$(b55_router_for_asn "$first_unfiltered")" sh -lc "ip route get 10.55.0.80 2>&1 || true; birdc show route $LEAK_PREFIX all 2>&1 || true" > "$ARTIFACT_DIR/fault_unfiltered_path_$first_unfiltered.txt"
  docker exec "$(b55_router_for_asn "$first_filtered")" sh -lc "ip route get 10.55.0.80 2>&1 || true; birdc show route $VICTIM_PREFIX all 2>&1 || true" > "$ARTIFACT_DIR/fault_filtered_path_$first_filtered.txt"
  docker exec "$VICTIM_EDGE" sh -lc "curl -fsS --max-time 2 http://127.0.0.1/" > "$ARTIFACT_DIR/fault_victim_local_health.txt"
  ab_log "fault-runtime passed"
}

case_recovery_check() {
  local asn container
  ab_log "withdrawing leaked more-specific by disabling DQE export session"
  docker exec "$DQE_ROUTER" /usr/local/bin/b55-dqe-control.sh clear
  sleep 10
  while read -r asn; do
    [ -n "$asn" ] || continue
    container="$(b55_router_for_asn "$asn")"
    b55_wait_route_absent "$container" "$LEAK_PREFIX" "/tmp/b55-recovery-leak-$asn.txt"
    b55_wait_route_present "$container" "$VICTIM_PREFIX" "/tmp/b55-recovery-aggregate-$asn.txt"
    docker exec "$container" sh -lc "curl -fsS --max-time 3 $VICTIM_URL" > "$ARTIFACT_DIR/recovery_curl_$asn.txt"
  done < <(b55_unfiltered_probe_asns)
  ab_log "recovery-runtime passed"
}

case_collect() {
  local asn container
  docker exec "$DQE_ROUTER" sh -lc "cat /var/log/b55-route-leak-change.log 2>/dev/null || true; printf '\n== protocols ==\n'; birdc show protocols 2>&1 || true; printf '\n== leak route ==\n'; birdc show route $LEAK_PREFIX all 2>&1 || true" > "$ARTIFACT_DIR/dqe_change_and_route.txt" 2>&1 || true
  for asn in 55 56 57 701 702 703; do
    container="$(b55_router_for_asn "$asn")"
    docker exec "$container" sh -lc "birdc show protocols 2>&1 || true; printf '\n== aggregate ==\n'; birdc show route $VICTIM_PREFIX all 2>&1 || true; printf '\n== leak ==\n'; birdc show route $LEAK_PREFIX all 2>&1 || true" > "$ARTIFACT_DIR/router_${asn}_bird.txt" 2>&1 || true
  done
}

case_exercise_observe_one() {
  local role="$1" dir="$2" asn container
  mkdir -p "$dir"
  case "$role" in
    public-users)
      for asn in "$(b55_unfiltered_probe_asns | ab_first_line)" "$(b55_filtered_probe_asns | ab_first_line)"; do
        container="$(b55_router_for_asn "$asn")"
        docker exec "$container" sh -lc "printf '== AS$asn curl ==\n'; curl -fsS --max-time 3 $VICTIM_URL 2>&1 || true; printf '\n== AS$asn route get ==\n'; ip route get 10.55.0.80 2>&1 || true" > "$dir/as${asn}_user.txt" 2>&1 || true
      done
      ;;
    route-collectors|network-ops)
      for asn in "$(b55_collector_asns | ab_first_line)" 701; do
        container="$(b55_router_for_asn "$asn")"
        docker exec "$container" sh -lc "birdc show route $VICTIM_PREFIX all 2>&1 || true; printf '\n== more-specific ==\n'; birdc show route $LEAK_PREFIX all 2>&1 || true; printf '\n== protocols ==\n'; birdc show protocols 2>&1 || true" > "$dir/as${asn}_routes.txt" 2>&1 || true
      done
      ;;
    provider-ops|service-ops)
      docker exec "$VICTIM_EDGE" sh -lc "curl -fsS --max-time 2 http://127.0.0.1/ 2>&1 || true" > "$dir/victim_service_health.txt" 2>&1 || true
      ;;
    control-plane|change-audit)
      docker exec "$DQE_ROUTER" sh -lc "cat /var/log/b55-route-leak-change.log 2>/dev/null || true; /usr/local/bin/b55-dqe-control.sh status 2>&1 || true" > "$dir/dqe_leak_control.txt" 2>&1 || true
      ;;
    *)
      echo "role $role has no B55 observation mapping" > "$dir/unsupported.txt"
      ;;
  esac
}

case_exercise_action() {
  case "$1" in
    inject-fault)
      case_inject_fault
      ;;
    mitigate|withdraw-leak|apply-filter|rollback|recover)
      docker exec "$DQE_ROUTER" /usr/local/bin/b55-dqe-control.sh clear
      ;;
    validate-recovery)
      case_recovery_check
      ;;
    *)
      echo "unsupported B55 action $1" >&2
      return 2
      ;;
  esac
}

ab_main "$@"
