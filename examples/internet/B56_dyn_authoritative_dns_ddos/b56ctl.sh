#!/usr/bin/env bash
set -euo pipefail

CASE_ID="b56"
CASE_SLUG="dyn_dns_ddos"
CASE_GENERATOR="dyn_dns_ddos.py"
CONTAINER_PREFIX="${B56_CONTAINER_PREFIX:-b56-}"

source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../_agent_benchmark_common" && pwd)/agent_case_ctl_common.sh"
ab_init

FQDN="www.customer-a.test"
SECONDARY_FQDN="www.customer-b.test"
DYNAUTH_IP="10.56.10.53"
SECONDARY_AUTH_IP="10.56.20.53"
RESOLVER_IP="10.56.30.53"
ORIGIN_URL="http://10.56.40.80/"
DYN_ROUTER="${CONTAINER_PREFIX}as56brd-Dyn_Anycast_Authoritative_DNS_Router-10.56.10.254"
RESOLVER_ROUTER="${CONTAINER_PREFIX}as58brd-Recursive_Resolver_Router-10.56.30.254"
ORIGIN_HOST="${CONTAINER_PREFIX}as59brd-Customer_Origin_Router-10.56.40.254"

case_runtime_min_containers() {
  case "$1" in
    S0) printf '%s\n' 14 ;;
    S1) printf '%s\n' 158 ;;
    S1_5) printf '%s\n' 178 ;;
    S2) printf '%s\n' 183 ;;
    *) ab_require_tier "$1" ;;
  esac
}

b56_router_for_asn() {
  local asn="$1"
  case "$asn" in
    50) printf '%sas50brd-Internet_Transit_Router-10.56.50.254\n' "$CONTAINER_PREFIX" ;;
    56) printf '%sas56brd-Dyn_Anycast_Authoritative_DNS_Router-10.56.10.254\n' "$CONTAINER_PREFIX" ;;
    57) printf '%sas57brd-Secondary_Authoritative_DNS_Router-10.56.20.254\n' "$CONTAINER_PREFIX" ;;
    58) printf '%sas58brd-Recursive_Resolver_Router-10.56.30.254\n' "$CONTAINER_PREFIX" ;;
    59) printf '%sas59brd-Customer_Origin_Router-10.56.40.254\n' "$CONTAINER_PREFIX" ;;
    *)
      if b56_asn_in_list "$asn" b56_client_asns; then
        printf '%sas%sbrd-Client_Probe_Router_%s-10.%s.0.254\n' "$CONTAINER_PREFIX" "$asn" "$asn" "$asn"
      elif b56_asn_in_list "$asn" b56_bot_asns; then
        printf '%sas%sbrd-Botnet_IoT_Router_%s-10.%s.0.254\n' "$CONTAINER_PREFIX" "$asn" "$asn" "$asn"
      elif b56_asn_in_list "$asn" b56_collector_asns; then
        printf '%sas%sbrd-DNS_Route_Collector_Router_%s-10.%s.0.254\n' "$CONTAINER_PREFIX" "$asn" "$asn" "$asn"
      else
        printf '%sas%sbrd-Background_Router_%s-10.%s.0.254\n' "$CONTAINER_PREFIX" "$asn" "$asn" "$asn"
      fi
      ;;
  esac
}

b56_asn_in_list() {
  local wanted="$1" list_fn="$2" candidate
  while read -r candidate; do
    [ "$candidate" = "$wanted" ] && return 0
  done < <("$list_fn")
  return 1
}

b56_client_asns() {
  case "$(ab_canonical_tier "$TIER")" in
    S0) printf '80\n81\n82\n' ;;
    S1) { seq 80 99; seq 101 131; printf '250\n'; } ;;
    S1_5) { seq 80 99; seq 101 144; printf '250\n'; } ;;
    S2) { seq 80 99; seq 101 179; printf '255\n'; } ;;
  esac
}

b56_bot_asns() {
  case "$(ab_canonical_tier "$TIER")" in
    S0) printf '120\n121\n122\n123\n' ;;
    S1) seq 132 187 ;;
    S1_5) seq 145 214 ;;
    S2) seq 180 244 ;;
  esac
}

b56_collector_asns() {
  case "$(ab_canonical_tier "$TIER")" in
    S0) printf '150\n' ;;
    S1) seq 188 197 ;;
    S1_5) seq 215 230 ;;
    S2) seq 245 254 ;;
  esac
}

b56_wait_dig_contains() {
  local container="$1" server="$2" name="$3" pattern="$4" out="$5" attempts="${6:-$(ab_runtime_attempts "$TIER")}"
  docker exec "$container" sh -lc "for i in \$(seq 1 $attempts); do dig +short +time=2 +tries=1 @$server $name A 2>&1 | tee $out; grep -q '$pattern' $out && exit 0; sleep 1; done; echo 'dig $name via $server did not match $pattern after $attempts attempts' >&2; cat $out >&2; exit 1"
}

b56_wait_dig_fails() {
  local container="$1" server="$2" name="$3" out="$4" attempts="${5:-$(ab_runtime_attempts "$TIER")}"
  docker exec "$container" sh -lc "for i in \$(seq 1 $attempts); do dig +time=1 +tries=1 @$server $name A 2>&1 | tee $out; ! grep -q '10.56.40.80' $out && grep -Eq '(timed out|no servers could be reached|SERVFAIL|connection timed out)' $out && exit 0; sleep 1; done; echo 'dig $name via $server still produced an answer or no DNS failure marker after $attempts attempts' >&2; cat $out >&2; exit 1"
}

case_normal_check() {
  local asn container
  ab_log "checking Dyn authoritative DNS and customer origin before attack"
  docker exec "$DYN_ROUTER" sh -lc "pgrep -a named; dig +short +time=2 +tries=1 @$DYNAUTH_IP $FQDN A" > "$ARTIFACT_DIR/normal_dyn_auth.txt"
  docker exec "$ORIGIN_HOST" sh -lc "curl -fsS --max-time 2 http://127.0.0.1/" > "$ARTIFACT_DIR/normal_origin_local.txt"
  docker exec "$RESOLVER_ROUTER" sh -lc "rndc flush 2>/dev/null || true"

  while read -r asn; do
    [ -n "$asn" ] || continue
    container="$(b56_router_for_asn "$asn")"
    ab_log "checking client AS$asn fresh DNS and HTTP"
    docker exec "$RESOLVER_ROUTER" sh -lc "rndc flush 2>/dev/null || true"
    b56_wait_dig_contains "$container" "$RESOLVER_IP" "$FQDN" "10.56.40.80" "/tmp/b56-normal-dig-$asn.txt"
    docker exec "$container" sh -lc "curl -fsS --resolve $FQDN:80:10.56.40.80 --max-time 3 http://$FQDN/" > "$ARTIFACT_DIR/normal_client_curl_$asn.txt"
  done < <(b56_client_asns)
  ab_log "normal-runtime passed"
}

case_inject_fault() {
  local asn container
  ab_log "triggering synthetic bot query bursts and authoritative-path overload"
  while read -r asn; do
    [ -n "$asn" ] || continue
    container="$(b56_router_for_asn "$asn")"
    docker exec "$container" /usr/local/bin/b56-bot-query.sh burst 8 >/dev/null 2>&1 || true
  done < <(b56_bot_asns | ab_take_lines 20)
  docker exec "$DYN_ROUTER" /usr/local/bin/b56-dyn-ddos-control.sh inject
  docker exec "$RESOLVER_ROUTER" sh -lc "rndc flush 2>/dev/null || true"
  sleep 5
}

case_fault_check() {
  local asn container first_client
  first_client="$(b56_client_asns | ab_first_line)"
  docker exec "$DYN_ROUTER" sh -lc "pgrep -a named; /usr/local/bin/b56-dyn-ddos-control.sh status" > "$ARTIFACT_DIR/fault_dyn_auth_status.txt" 2>&1 || true
  docker exec "$ORIGIN_HOST" sh -lc "curl -fsS --max-time 2 http://127.0.0.1/" > "$ARTIFACT_DIR/fault_origin_local.txt"

  while read -r asn; do
    [ -n "$asn" ] || continue
    container="$(b56_router_for_asn "$asn")"
    ab_log "checking client AS$asn sees fresh lookup failure against Dyn-only domain"
    docker exec "$RESOLVER_ROUTER" sh -lc "rndc flush 2>/dev/null || true"
    b56_wait_dig_fails "$container" "$RESOLVER_IP" "$FQDN" "/tmp/b56-fault-dig-$asn.txt"
    docker cp "$container:/tmp/b56-fault-dig-$asn.txt" "$ARTIFACT_DIR/fault_client_dig_$asn.txt" >/dev/null
  done < <(b56_client_asns)

  container="$(b56_router_for_asn "$first_client")"
  b56_wait_dig_contains "$container" "$RESOLVER_IP" "$SECONDARY_FQDN" "10.56.40.80" "/tmp/b56-secondary-ok.txt"
  docker cp "$container:/tmp/b56-secondary-ok.txt" "$ARTIFACT_DIR/fault_secondary_dns_ok.txt" >/dev/null
  ab_log "fault-runtime passed"
}

case_recovery_check() {
  local asn container
  ab_log "applying scrubber/rate-limit recovery on Dyn authoritative path"
  docker exec "$DYN_ROUTER" /usr/local/bin/b56-dyn-ddos-control.sh scrub
  sleep 5
  while read -r asn; do
    [ -n "$asn" ] || continue
    container="$(b56_router_for_asn "$asn")"
    docker exec "$RESOLVER_ROUTER" sh -lc "rndc flush 2>/dev/null || true"
    b56_wait_dig_contains "$container" "$RESOLVER_IP" "$FQDN" "10.56.40.80" "/tmp/b56-recovery-dig-$asn.txt"
    docker cp "$container:/tmp/b56-recovery-dig-$asn.txt" "$ARTIFACT_DIR/recovery_client_dig_$asn.txt" >/dev/null
    docker exec "$container" sh -lc "curl -fsS --resolve $FQDN:80:10.56.40.80 --max-time 3 http://$FQDN/" > "$ARTIFACT_DIR/recovery_client_curl_$asn.txt"
  done < <(b56_client_asns)
  ab_log "recovery-runtime passed"
}

case_collect() {
  local asn container
  docker exec "$DYN_ROUTER" sh -lc "cat /var/log/b56-dyn-ddos.log 2>/dev/null || true; printf '\n== control status ==\n'; /usr/local/bin/b56-dyn-ddos-control.sh status 2>&1 || true; printf '\n== protocols ==\n'; birdc show protocols 2>&1 || true" > "$ARTIFACT_DIR/dyn_auth_collect.txt" 2>&1 || true
  docker exec "$RESOLVER_ROUTER" sh -lc "pgrep -a named 2>&1 || true; printf '\n== resolver config ==\n'; cat /etc/bind/named.conf.local /etc/bind/named.conf.options 2>/dev/null || true" > "$ARTIFACT_DIR/resolver_collect.txt" 2>&1 || true
  while read -r asn; do
    container="$(b56_router_for_asn "$asn")"
    docker exec "$container" sh -lc "cat /var/log/b56-bot-traffic.log 2>/dev/null || true" > "$ARTIFACT_DIR/bot_${asn}_traffic.txt" 2>&1 || true
  done < <(b56_bot_asns | ab_take_lines 10)
}

case_exercise_observe_one() {
  local role="$1" dir="$2" asn container
  mkdir -p "$dir"
  case "$role" in
    public-users)
      for asn in "$(b56_client_asns | ab_first_line)" "$(b56_client_asns | ab_last_line)"; do
        container="$(b56_router_for_asn "$asn")"
        docker exec "$container" sh -lc "printf '== Dyn-only fresh lookup ==\n'; dig +time=2 +tries=1 @$RESOLVER_IP $FQDN A 2>&1 || true; printf '\n== secondary-provider domain ==\n'; dig +time=2 +tries=1 @$RESOLVER_IP $SECONDARY_FQDN A 2>&1 || true" > "$dir/as${asn}_dns.txt" 2>&1 || true
      done
      ;;
    resolvers|provider-ops)
      docker exec "$RESOLVER_ROUTER" sh -lc "printf '== resolver fresh Dyn-only ==\n'; rndc flush 2>/dev/null || true; dig +time=2 +tries=1 @$RESOLVER_IP $FQDN A 2>&1 || true; printf '\n== resolver secondary ==\n'; dig +time=2 +tries=1 @$RESOLVER_IP $SECONDARY_FQDN A 2>&1 || true" > "$dir/resolver_view.txt" 2>&1 || true
      ;;
    service-ops)
      docker exec "$ORIGIN_HOST" sh -lc "curl -fsS --max-time 2 http://127.0.0.1/ 2>&1 || true" > "$dir/origin_health.txt" 2>&1 || true
      ;;
    network-ops|route-collectors)
      for asn in 56 "$(b56_collector_asns | ab_first_line)"; do
        container="$(b56_router_for_asn "$asn")"
        docker exec "$container" sh -lc "birdc show route 10.56.10.0/24 all 2>&1 || true; printf '\n== protocols ==\n'; birdc show protocols 2>&1 || true" > "$dir/as${asn}_route_view.txt" 2>&1 || true
      done
      ;;
    botnet)
      for asn in "$(b56_bot_asns | ab_first_line)" "$(b56_bot_asns | ab_last_line)"; do
        container="$(b56_router_for_asn "$asn")"
        docker exec "$container" sh -lc "cat /var/log/b56-bot-traffic.log 2>/dev/null || true" > "$dir/as${asn}_bot.txt" 2>&1 || true
      done
      ;;
    control-plane|change-audit)
      docker exec "$DYN_ROUTER" sh -lc "cat /var/log/b56-dyn-ddos.log 2>/dev/null || true; /usr/local/bin/b56-dyn-ddos-control.sh status 2>&1 || true" > "$dir/dyn_control.txt" 2>&1 || true
      ;;
    *)
      echo "role $role has no B56 observation mapping" > "$dir/unsupported.txt"
      ;;
  esac
}

case_exercise_action() {
  case "$1" in
    inject-fault)
      case_inject_fault
      ;;
    mitigate|activate-scrubber|activate-secondary|recover)
      docker exec "$DYN_ROUTER" /usr/local/bin/b56-dyn-ddos-control.sh scrub
      ;;
    validate-recovery)
      case_recovery_check
      ;;
    *)
      echo "unsupported B56 action $1" >&2
      return 2
      ;;
  esac
}

ab_main "$@"
