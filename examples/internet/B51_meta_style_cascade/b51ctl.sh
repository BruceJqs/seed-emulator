#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/output"
ARTIFACT_DIR="$SCRIPT_DIR/test_log"
TELEMETRY_OUTPUT_DIR="$ARTIFACT_DIR/telemetry"
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-seed_meta_cascade_s0}"
PLATFORM="${PLATFORM:-amd}"
PYTHON_BIN="${SEED_PYTHON:-python3}"
CONTAINER_PREFIX="${B51_CONTAINER_PREFIX:-b51-}"
TIER="${TIER:-S0}"
RUNTIME_LADDER="${B51_RUNTIME_LADDER:-S0 S1}"

EDGE_ROUTER="${CONTAINER_PREFIX}as20brd-Edge_Health_Gate_Router-10.20.0.254"
TRANSIT_ROUTER="${CONTAINER_PREFIX}as10brd-r100-10.10.0.254"
DC_ROUTER="${CONTAINER_PREFIX}as30brd-DC_Backend_Router-10.30.0.254"
CLIENT_ROUTER="${CONTAINER_PREFIX}as50brd-client-router-10.50.0.254"
CLIENT="$CLIENT_ROUTER"
RESOLVER="$CLIENT_ROUTER"
DOMAIN="www.meta-bench.test"
RESOLVER_IP="10.50.0.53"
EDGE_PREFIX="10.20.0.0/24"
EDGE_DNS_IP="10.20.0.53"
EDGE_SERVICE_IP="10.20.0.80"
BACKEND_IP="10.30.0.80"

log() {
  printf '[b51ctl] %s\n' "$*"
}

is_runtime_tier() {
  case "$1" in
    S0|S1|S1.5|S1_5|S15|S2) return 0 ;;
    *) return 1 ;;
  esac
}

canonical_tier() {
  case "$1" in
    S1.5|S1_5|S15) printf '%s\n' "S1_5" ;;
    *) printf '%s\n' "$1" ;;
  esac
}

display_tier() {
  case "$1" in
    S1_5) printf '%s\n' "S1.5" ;;
    *) printf '%s\n' "$1" ;;
  esac
}

runtime_tier_supported() {
  local tier
  tier="$(canonical_tier "$1")"
  if is_runtime_tier "$tier"; then
    return 0
  fi

  case "$1" in
    *)
      echo "unsupported runtime TIER=$1; expected S0, S1, S1.5, or S2" >&2
      return 1
      ;;
  esac
}

require_runtime_tier() {
  runtime_tier_supported "$1"
}

runtime_expected_min_containers() {
  case "$(canonical_tier "$1")" in
    S0) printf '%s\n' 7 ;;
    S1) printf '%s\n' 129 ;;
    S1_5) printf '%s\n' 225 ;;
    S2) printf '%s\n' 1023 ;;
    *) require_runtime_tier "$1" ;;
  esac
}

runtime_wait_seconds() {
  case "$(canonical_tier "$1")" in
    S0|S1) printf '%s\n' 45 ;;
    S1_5) printf '%s\n' 75 ;;
    S2) printf '%s\n' 180 ;;
    *) require_runtime_tier "$1" ;;
  esac
}

runtime_convergence_attempts() {
  case "$(canonical_tier "$1")" in
    S0) printf '%s\n' 60 ;;
    S1) printf '%s\n' 120 ;;
    S1_5) printf '%s\n' 180 ;;
    S2) printf '%s\n' 300 ;;
    *) require_runtime_tier "$1" ;;
  esac
}

runtime_dns_attempts() {
  case "$(canonical_tier "$1")" in
    S0) printf '%s\n' 15 ;;
    S1) printf '%s\n' 30 ;;
    S1_5) printf '%s\n' 45 ;;
    S2) printf '%s\n' 60 ;;
    *) require_runtime_tier "$1" ;;
  esac
}

runtime_probe_dns_attempts() {
  case "$(canonical_tier "$1")" in
    S0) printf '%s\n' 5 ;;
    S1) printf '%s\n' 10 ;;
    S1_5) printf '%s\n' 15 ;;
    S2) printf '%s\n' 20 ;;
    *) require_runtime_tier "$1" ;;
  esac
}

runtime_compose_parallel_limit() {
  case "$(canonical_tier "$1")" in
    S0|S1|S1_5) printf '%s\n' 32 ;;
    S2) printf '%s\n' 1 ;;
    *) require_runtime_tier "$1" ;;
  esac
}

s2_runtime_enabled() {
  case "${B51_ALLOW_S2_RUNTIME:-0}" in
    1|true|TRUE|yes|YES) return 0 ;;
    *) return 1 ;;
  esac
}

host_sysctl_value() {
  local key="$1"
  local path="/proc/sys/${key//.//}"
  if [ -r "$path" ]; then
    cat "$path"
  else
    printf '0\n'
  fi
}

collect_host_diagnostics() {
  local dir="${1:-$ARTIFACT_DIR/host}"
  mkdir -p "$dir"

  {
    printf 'timestamp=%s\n' "$(date -Is)"
    printf 'project=%s\n' "$PROJECT_NAME"
    printf 'tier=%s\n' "$TIER"
    printf 's2_runtime_enabled=%s\n' "${B51_ALLOW_S2_RUNTIME:-0}"
    printf '\n== uname ==\n'
    uname -a 2>&1 || true
    printf '\n== memory ==\n'
    free -h 2>&1 || true
    printf '\n== neighbor thresholds ==\n'
    for key in \
      net.ipv4.neigh.default.gc_thresh1 \
      net.ipv4.neigh.default.gc_thresh2 \
      net.ipv4.neigh.default.gc_thresh3; do
      printf '%s=%s\n' "$key" "$(host_sysctl_value "$key")"
    done
    printf '\n== docker counts ==\n'
    printf 'containers=%s\n' "$(docker ps -a --format '{{.Names}}' 2>/dev/null | wc -l | tr -d ' ')"
    printf 'running_containers=%s\n' "$(docker ps --format '{{.Names}}' 2>/dev/null | wc -l | tr -d ' ')"
    printf 'networks=%s\n' "$(docker network ls --format '{{.Name}}' 2>/dev/null | wc -l | tr -d ' ')"
    printf 'volumes=%s\n' "$(docker volume ls --format '{{.Name}}' 2>/dev/null | wc -l | tr -d ' ')"
    printf 'compose_project_containers=%s\n' "$(docker ps -a --filter "label=com.docker.compose.project=$PROJECT_NAME" --format '{{.Names}}' 2>/dev/null | wc -l | tr -d ' ')"
    printf 'b51_named_containers=%s\n' "$(docker ps -a --filter "name=$CONTAINER_PREFIX" --format '{{.Names}}' 2>/dev/null | wc -l | tr -d ' ')"
    printf '\n== host neighbor count ==\n'
    ip -s neigh show 2>/dev/null | wc -l | tr -d ' ' || true
    printf '\n== bridge fdb count ==\n'
    if command -v bridge >/dev/null 2>&1; then
      bridge fdb show 2>/dev/null | wc -l | tr -d ' ' || true
    else
      echo "bridge command not available"
    fi
    printf '\n== docker system df ==\n'
    docker system df 2>&1 || true
  } > "$dir/host_status.txt" 2>&1 || true

  docker ps -a --format '{{.Names}}' > "$dir/docker_containers.txt" 2>&1 || true
  docker network ls --format '{{.Name}} {{.Driver}} {{.Scope}}' > "$dir/docker_networks.txt" 2>&1 || true
  docker volume ls --format '{{.Name}}' > "$dir/docker_volumes.txt" 2>&1 || true
  ip -br link > "$dir/host_links.txt" 2>&1 || true
  ip -s neigh show > "$dir/host_neighbors.txt" 2>&1 || true
  if command -v bridge >/dev/null 2>&1; then
    bridge fdb show > "$dir/bridge_fdb.txt" 2>&1 || true
  fi
  dmesg -T 2>&1 | grep -E 'arp_cache|neighbor|neigh|veth|bridge|docker' | tail -n 300 > "$dir/dmesg_network_tail.txt" || true
}

s2_preflight_report() {
  local previous_tier="$TIER"
  local previous_artifact_dir="$ARTIFACT_DIR"
  local rc=0
  local gc1 gc2 gc3 report_dir

  TIER="S2"
  ARTIFACT_DIR="$SCRIPT_DIR/test_log/host_diagnostics/S2-preflight"
  report_dir="$ARTIFACT_DIR"
  mkdir -p "$report_dir"
  collect_host_diagnostics "$report_dir"

  gc1="$(host_sysctl_value net.ipv4.neigh.default.gc_thresh1)"
  gc2="$(host_sysctl_value net.ipv4.neigh.default.gc_thresh2)"
  gc3="$(host_sysctl_value net.ipv4.neigh.default.gc_thresh3)"

  {
    printf 'tier=S2\n'
    printf 'diagnostic_only=true\n'
    printf 'starts_containers=false\n'
    printf 's2_runtime_enabled=%s\n' "${B51_ALLOW_S2_RUNTIME:-0}"
    printf 'observed_gc_thresh1=%s\n' "$gc1"
    printf 'observed_gc_thresh2=%s\n' "$gc2"
    printf 'observed_gc_thresh3=%s\n' "$gc3"
    printf 'required_gc_thresh1=4096\n'
    printf 'required_gc_thresh2=8192\n'
    printf 'required_gc_thresh3=65536\n'
  } > "$report_dir/s2_preflight.txt"

  if ! s2_runtime_enabled; then
    {
      echo "status=blocked"
      echo "reason=B51_ALLOW_S2_RUNTIME is not set"
    } >> "$report_dir/s2_preflight.txt"
    rc=2
  fi

  if [ "$gc1" -lt 4096 ] || [ "$gc2" -lt 8192 ] || [ "$gc3" -lt 65536 ]; then
    {
      echo "status=blocked"
      echo "reason=neighbor cache thresholds are below S2 minimums"
    } >> "$report_dir/s2_preflight.txt"
    rc=2
  fi

  if [ "$rc" -eq 0 ]; then
    echo "status=ready_for_operator_review" >> "$report_dir/s2_preflight.txt"
  fi

  cat "$report_dir/s2_preflight.txt"
  log "S2 preflight diagnostics collected into $report_dir"

  TIER="$previous_tier"
  ARTIFACT_DIR="$previous_artifact_dir"
  return "$rc"
}

host_diagnose() {
  local label="${1:-current}"
  case "$label" in
    *[!A-Za-z0-9_.-]*|"")
      echo "host-diagnose label must use only letters, digits, dot, underscore, or dash" >&2
      return 2
      ;;
  esac
  local dir="$SCRIPT_DIR/test_log/host_diagnostics/$label"
  collect_host_diagnostics "$dir"
  log "host diagnostics collected into $dir"
}

require_s2_runtime_preflight() {
  TIER="$(canonical_tier "$TIER")"
  [ "$TIER" = "S2" ] || return 0

  if ! s2_runtime_enabled; then
    cat >&2 <<'EOF'
S2 runtime is disabled by default because it starts 1023 local Docker containers.
Set B51_ALLOW_S2_RUNTIME=1 only on a prepared host after reviewing the risk.
The default runtime ladder remains S0 S1.
EOF
    return 2
  fi

  local gc1 gc2 gc3
  gc1="$(host_sysctl_value net.ipv4.neigh.default.gc_thresh1)"
  gc2="$(host_sysctl_value net.ipv4.neigh.default.gc_thresh2)"
  gc3="$(host_sysctl_value net.ipv4.neigh.default.gc_thresh3)"

  if [ "$gc1" -lt 4096 ] || [ "$gc2" -lt 8192 ] || [ "$gc3" -lt 65536 ]; then
    cat >&2 <<EOF
S2 host preflight failed: neighbor cache thresholds are too low.
observed: gc_thresh1=$gc1 gc_thresh2=$gc2 gc_thresh3=$gc3
required: gc_thresh1>=4096 gc_thresh2>=8192 gc_thresh3>=65536
Lower limits previously caused arp_cache neighbor table overflow and AS50 resolver timeouts.
Do not start S2 on this host until the host networking limits are raised or S2 is moved to a distributed/lightweight runtime.
EOF
    return 2
  fi

  log "S2 host preflight passed: gc_thresh1=$gc1 gc_thresh2=$gc2 gc_thresh3=$gc3"
}

skip_service_build() {
  case "${B51_SKIP_SERVICE_BUILD:-0}" in
    1|true|TRUE|yes|YES) return 0 ;;
    *) return 1 ;;
  esac
}

preserve_on_fail() {
  case "${B51_PRESERVE_ON_FAIL:-0}" in
    1|true|TRUE|yes|YES) return 0 ;;
    *) return 1 ;;
  esac
}

cleanup_after_failure() {
  local rc="$1"
  collect || true
  if preserve_on_fail; then
    log "B51_PRESERVE_ON_FAIL is set; leaving compose project $PROJECT_NAME running for live diagnosis"
  else
    down || true
  fi
  exit "$rc"
}

serial_container_start_enabled() {
  case "${B51_SERIAL_CONTAINER_START:-auto}" in
    1|true|TRUE|yes|YES) return 0 ;;
    0|false|FALSE|no|NO) return 1 ;;
    auto)
      [ "$(canonical_tier "$TIER")" = "S2" ] && skip_service_build
      ;;
    *)
      echo "unsupported B51_SERIAL_CONTAINER_START=${B51_SERIAL_CONTAINER_START}; expected auto, 1, or 0" >&2
      return 2
      ;;
  esac
}

compose_live_container_count() {
  docker ps --filter "label=com.docker.compose.project=$PROJECT_NAME" --format '{{.Names}}' | wc -l | tr -d ' '
}

runtime_live_container_count() {
  docker ps --format '{{.Names}}' | awk -v prefix="$CONTAINER_PREFIX" 'index($0, prefix) == 1' | wc -l | tr -d ' '
}

start_runtime_containers_serial() {
  local batch_size="${B51_SERIAL_START_BATCH:-25}"
  local batch_sleep="${B51_SERIAL_START_SLEEP:-2}"
  local count=0
  local name

  log "starting runtime containers serially: batch=$batch_size sleep=${batch_sleep}s"
  while IFS= read -r name; do
    [ -n "$name" ] || continue
    case "$name" in
      "$CONTAINER_PREFIX"*) ;;
      *) continue ;;
    esac
    if ! docker start "$name" >/dev/null; then
      echo "failed to start $name after $count runtime containers" >&2
      echo "live_containers=$(compose_live_container_count)" >&2
      return 1
    fi
    count=$((count + 1))
    if [ $((count % batch_size)) -eq 0 ]; then
      log "started $count runtime containers"
      sleep "$batch_sleep"
    fi
  done < <(docker ps -a --filter "label=com.docker.compose.project=$PROJECT_NAME" --format '{{.Names}}' | sort)
  log "serial start completed for $count runtime containers"
}

assert_runtime_live_scale() {
  local expected actual compose_actual
  TIER="$(canonical_tier "$TIER")"
  require_runtime_tier "$TIER"
  expected="$(runtime_expected_min_containers "$TIER")"
  actual="$(runtime_live_container_count)"
  compose_actual="$(compose_live_container_count)"
  mkdir -p "$ARTIFACT_DIR"
  printf 'tier=%s\nproject=%s\nruntime_prefix=%s\nruntime_live_containers=%s\ncompose_live_containers=%s\nminimum_required=%s\n' \
    "$(display_tier "$TIER")" "$PROJECT_NAME" "$CONTAINER_PREFIX" "$actual" "$compose_actual" "$expected" > "$ARTIFACT_DIR/runtime_container_count.txt"
  if [ "$actual" -lt "$expected" ]; then
    echo "$(display_tier "$TIER") runtime scale check failed: prefix=$CONTAINER_PREFIX live containers=$actual, required>=$expected" >&2
    return 1
  fi
  log "$(display_tier "$TIER") live topology container check passed: $actual >= $expected"
}

router_service_image() {
  case "$PLATFORM" in
    arm|arm64) printf '%s\n' "b51-router-services-base-arm" ;;
    amd|amd64) printf '%s\n' "b51-router-services-base-amd" ;;
    *)
      echo "unsupported PLATFORM=$PLATFORM; expected arm or amd" >&2
      return 2
      ;;
  esac
}

compose() {
  if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_PROJECT_NAME="$PROJECT_NAME" COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT:-$(runtime_compose_parallel_limit "$TIER")}" DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 docker-compose "$@"
  elif docker compose version >/dev/null 2>&1; then
    COMPOSE_PROJECT_NAME="$PROJECT_NAME" COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT:-$(runtime_compose_parallel_limit "$TIER")}" DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 docker compose "$@"
  else
    echo "docker-compose or docker compose is required" >&2
    return 1
  fi
}

docker_exec() {
  docker exec "$@"
}

generate() {
  TIER="$(canonical_tier "$TIER")"
  require_runtime_tier "$TIER"
  require_s2_runtime_preflight
  log "generating SEED output for platform=$PLATFORM tier=$(display_tier "$TIER")"
  export PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"
  (cd "$SCRIPT_DIR" && "$PYTHON_BIN" ./meta_style_cascade.py "$PLATFORM" "$TIER")
  printf '%s\n' "$TIER" > "$OUTPUT_DIR/.b51-runtime-tier"
}

up() {
  TIER="$(canonical_tier "$TIER")"
  require_runtime_tier "$TIER"
  require_s2_runtime_preflight
  if [ ! -f "$OUTPUT_DIR/docker-compose.yml" ] || [ "$(cat "$OUTPUT_DIR/.b51-runtime-tier" 2>/dev/null || true)" != "$TIER" ]; then
    generate
  fi
  log "starting compose project $PROJECT_NAME"
  (
    cd "$OUTPUT_DIR"
    if skip_service_build; then
      log "skipping compose build via B51_SKIP_SERVICE_BUILD; using existing images"
      if serial_container_start_enabled; then
        compose up -d --no-build --no-start
        start_runtime_containers_serial
      else
        compose up -d --no-build
      fi
    else
      compose build "$(router_service_image)"
      for dummy in dummies/*; do
        [ -f "$dummy" ] || continue
        compose build "$(basename "$dummy")"
      done
      compose build
      compose up -d
    fi
  )
  log "waiting for BIRD and services"
  sleep "$(runtime_wait_seconds "$TIER")"
}

down() {
  if [ -f "$OUTPUT_DIR/docker-compose.yml" ]; then
    log "stopping compose project $PROJECT_NAME"
    (cd "$OUTPUT_DIR" && compose down)
  fi
}

status() {
  mkdir -p "$ARTIFACT_DIR"
  docker_exec "$EDGE_ROUTER" sh -lc 'cat /var/run/meta-health-status 2>/dev/null || true'
}

wait_health_status() {
  local expected="$1"
  docker_exec "$EDGE_ROUTER" sh -lc "for i in \$(seq 1 60); do status=\$(cat /var/run/meta-health-status 2>/dev/null || true); [ \"\$status\" = '$expected' ] && exit 0; sleep 1; done; echo \"expected health status '$expected', got '\$status'\" >&2; tail -n 40 /var/log/meta-health-gate.log 2>/dev/null >&2 || true; exit 1"
}

wait_bird_route_visible() {
  local container="$1"
  local prefix="$2"
  local tmp="$3"
  local attempts="${4:-$(runtime_convergence_attempts "$TIER")}"
  docker_exec "$container" sh -lc "for i in \$(seq 1 $attempts); do birdc show route $prefix 2>&1 | tee $tmp; grep -q '$prefix' $tmp && exit 0; sleep 1; done; echo 'route $prefix not visible after $attempts attempts' >&2; cat $tmp >&2; exit 1"
}

wait_bird_route_absent() {
  local container="$1"
  local prefix="$2"
  local tmp="$3"
  local attempts="${4:-$(runtime_convergence_attempts "$TIER")}"
  docker_exec "$container" sh -lc "for i in \$(seq 1 $attempts); do birdc show route $prefix 2>&1 | tee $tmp; ! grep -q '$prefix' $tmp && exit 0; sleep 1; done; echo 'route $prefix still visible after $attempts attempts' >&2; cat $tmp >&2; exit 1"
}

wait_dns_record_present() {
  local container="$1"
  local tmp="$2"
  local attempts="${3:-$(runtime_dns_attempts "$TIER")}"
  docker_exec "$container" sh -lc "for i in \$(seq 1 $attempts); do dig +short +time=2 +tries=1 @$RESOLVER_IP $DOMAIN A | tee $tmp; grep -q '^$EDGE_SERVICE_IP$' $tmp && exit 0; sleep 1; done; echo 'expected $DOMAIN A $EDGE_SERVICE_IP after $attempts attempts' >&2; cat $tmp >&2; exit 1"
}

wait_dns_record_absent() {
  local container="$1"
  local tmp="$2"
  local attempts="${3:-$(runtime_dns_attempts "$TIER")}"
  docker_exec "$container" sh -lc "for i in \$(seq 1 $attempts); do dig +short +time=2 +tries=1 @$RESOLVER_IP $DOMAIN A | tee $tmp; ! grep -q '^$EDGE_SERVICE_IP$' $tmp && exit 0; sleep 1; done; echo 'unexpected $DOMAIN A $EDGE_SERVICE_IP after $attempts attempts' >&2; cat $tmp >&2; exit 1"
}

normal_check() {
  TIER="$(canonical_tier "$TIER")"
  require_runtime_tier "$TIER"
  require_s2_runtime_preflight
  mkdir -p "$ARTIFACT_DIR"
  log "checking live runtime scale"
  assert_runtime_live_scale
  log "checking health gate"
  wait_health_status healthy
  docker_exec "$EDGE_ROUTER" sh -lc "curl -fsS --max-time 2 http://$BACKEND_IP/" > "$ARTIFACT_DIR/normal_edge_to_backend.txt"

  log "waiting for client route visibility"
  wait_bird_route_visible "$CLIENT_ROUTER" "$EDGE_PREFIX" "/tmp/meta-normal-route.txt"
  docker cp "$CLIENT_ROUTER:/tmp/meta-normal-route.txt" "$ARTIFACT_DIR/normal_route.txt" >/dev/null

  log "checking DNS"
  wait_dns_record_present "$CLIENT" "/tmp/meta-normal-dig.txt"
  docker cp "$CLIENT:/tmp/meta-normal-dig.txt" "$ARTIFACT_DIR/normal_dig.txt" >/dev/null

  log "checking service access"
  docker_exec "$CLIENT" sh -lc "curl -fsS --max-time 3 http://$DOMAIN/" > "$ARTIFACT_DIR/normal_curl.txt"
  scale_runtime_normal_check
  log "normal-check passed"
}

inject_fault() {
  TIER="$(canonical_tier "$TIER")"
  require_runtime_tier "$TIER"
  require_s2_runtime_preflight
  mkdir -p "$ARTIFACT_DIR"
  log "injecting internal path policy fault"
  docker_exec "$EDGE_ROUTER" /usr/local/bin/meta-backbone-fault.sh inject
  log "waiting for health gate to withdraw external BGP peer"
  sleep 12
}

fault_check() {
  TIER="$(canonical_tier "$TIER")"
  require_runtime_tier "$TIER"
  require_s2_runtime_preflight
  mkdir -p "$ARTIFACT_DIR"
  log "checking health gate failure"
  wait_health_status unhealthy
  docker_exec "$EDGE_ROUTER" sh -lc 'tail -n 20 /var/log/meta-health-gate.log' > "$ARTIFACT_DIR/fault_health_gate.log"
  docker_exec "$EDGE_ROUTER" sh -lc 'tail -n 20 /var/log/meta-recent-change.log' > "$ARTIFACT_DIR/fault_recent_change.log"

  log "checking route withdrawal"
  wait_bird_route_absent "$CLIENT_ROUTER" "$EDGE_PREFIX" "/tmp/meta-fault-route.txt"
  docker cp "$CLIENT_ROUTER:/tmp/meta-fault-route.txt" "$ARTIFACT_DIR/fault_route.txt" >/dev/null

  log "checking external DNS/service symptoms"
  wait_dns_record_absent "$CLIENT" "/tmp/meta-fault-dig-short.txt"
  docker cp "$CLIENT:/tmp/meta-fault-dig-short.txt" "$ARTIFACT_DIR/fault_dig_short.txt" >/dev/null
  docker_exec "$CLIENT" sh -lc "dig +time=2 +tries=1 @$RESOLVER_IP $DOMAIN A" > "$ARTIFACT_DIR/fault_dig.txt" 2>&1 || true
  if docker_exec "$CLIENT" sh -lc "curl -fsS --max-time 3 http://$DOMAIN/" > "$ARTIFACT_DIR/fault_curl.txt" 2>&1; then
    echo "curl unexpectedly succeeded" >&2
    return 1
  fi
  scale_runtime_fault_check
  log "fault-check passed"
}

collect() {
  mkdir -p "$ARTIFACT_DIR"
  log "collecting artifacts into $ARTIFACT_DIR"
  collect_host_diagnostics "$ARTIFACT_DIR/host"
  docker inspect "$TRANSIT_ROUTER" > "$ARTIFACT_DIR/transit_docker_inspect.json" 2>&1 || true
  docker inspect "$EDGE_ROUTER" > "$ARTIFACT_DIR/edge_docker_inspect.json" 2>&1 || true
  docker inspect "$CLIENT_ROUTER" > "$ARTIFACT_DIR/client_docker_inspect.json" 2>&1 || true
  docker_exec "$EDGE_ROUTER" sh -lc 'cat /var/run/meta-health-status 2>/dev/null || true' > "$ARTIFACT_DIR/health_status.txt" || true
  docker_exec "$EDGE_ROUTER" sh -lc 'cat /var/log/meta-health-gate.log 2>/dev/null || true' > "$ARTIFACT_DIR/health_gate.log" || true
  docker_exec "$EDGE_ROUTER" sh -lc 'cat /var/log/meta-recent-change.log 2>/dev/null || true' > "$ARTIFACT_DIR/recent_change.log" || true
  docker_exec "$EDGE_ROUTER" sh -lc 'birdc show protocols 2>/dev/null || true' > "$ARTIFACT_DIR/edge_protocols.txt" || true
  docker_exec "$TRANSIT_ROUTER" sh -lc "printf '== ip addr ==\n'; ip -br addr 2>&1 || true; printf '\n== ip route ==\n'; ip route 2>&1 || true; printf '\n== ip neigh ==\n'; ip neigh show 2>&1 || true; printf '\n== route get ix peers ==\n'; for peer in 10.225.0.20 10.225.0.50; do printf '\n-- %s --\n' \"\$peer\"; ip route get \"\$peer\" 2>&1 || true; ping -c 1 -W 1 \"\$peer\" 2>&1 || true; done; printf '\n== bird interfaces ==\n'; birdc show interfaces 2>&1 || true; printf '\n== bird protocols ==\n'; birdc show protocols 2>&1 || true" > "$ARTIFACT_DIR/transit_runtime_net.txt" || true
  docker_exec "$EDGE_ROUTER" sh -lc "printf '== ip addr ==\n'; ip -br addr 2>&1 || true; printf '\n== ip route ==\n'; ip route 2>&1 || true; printf '\n== ip neigh ==\n'; ip neigh show 2>&1 || true; printf '\n== route get peers ==\n'; for peer in 10.225.0.10 10.225.1.30 $BACKEND_IP; do printf '\n-- %s --\n' \"\$peer\"; ip route get \"\$peer\" 2>&1 || true; ping -c 1 -W 1 \"\$peer\" 2>&1 || true; done; printf '\n== bird interfaces ==\n'; birdc show interfaces 2>&1 || true; printf '\n== bird protocols ==\n'; birdc show protocols 2>&1 || true" > "$ARTIFACT_DIR/edge_runtime_net.txt" || true
  docker_exec "$CLIENT_ROUTER" sh -lc "printf '== ip addr ==\n'; ip -br addr 2>&1 || true; printf '\n== ip route ==\n'; ip route 2>&1 || true; printf '\n== ip neigh ==\n'; ip neigh show 2>&1 || true; printf '\n== route get peers ==\n'; for peer in 10.225.0.10 $EDGE_DNS_IP; do printf '\n-- %s --\n' \"\$peer\"; ip route get \"\$peer\" 2>&1 || true; ping -c 1 -W 1 \"\$peer\" 2>&1 || true; done; printf '\n== bird interfaces ==\n'; birdc show interfaces 2>&1 || true; printf '\n== bird protocols ==\n'; birdc show protocols 2>&1 || true" > "$ARTIFACT_DIR/client_runtime_net.txt" || true
  docker_exec "$EDGE_ROUTER" sh -lc "printf '== protocols all ==\n'; birdc show protocols all 2>&1 || true; printf '\n== route $EDGE_PREFIX all ==\n'; birdc show route $EDGE_PREFIX all 2>&1 || true; printf '\n== export u_as10 $EDGE_PREFIX ==\n'; birdc show route export u_as10 $EDGE_PREFIX all 2>&1 || true; printf '\n== export c_as30 $EDGE_PREFIX ==\n'; birdc show route export c_as30 $EDGE_PREFIX all 2>&1 || true" > "$ARTIFACT_DIR/edge_bird_detail.txt" || true
  docker_exec "$TRANSIT_ROUTER" sh -lc "printf '== protocols all ==\n'; birdc show protocols all 2>&1 || true; printf '\n== route $EDGE_PREFIX all ==\n'; birdc show route $EDGE_PREFIX all 2>&1 || true; printf '\n== export c_as20 $EDGE_PREFIX ==\n'; birdc show route export c_as20 $EDGE_PREFIX all 2>&1 || true; printf '\n== export c_as50 $EDGE_PREFIX ==\n'; birdc show route export c_as50 $EDGE_PREFIX all 2>&1 || true; printf '\n== export c_as210 $EDGE_PREFIX ==\n'; birdc show route export c_as210 $EDGE_PREFIX all 2>&1 || true" > "$ARTIFACT_DIR/transit_bird_detail.txt" || true
  docker_exec "$DC_ROUTER" sh -lc "printf '== protocols all ==\n'; birdc show protocols all 2>&1 || true; printf '\n== route $EDGE_PREFIX all ==\n'; birdc show route $EDGE_PREFIX all 2>&1 || true" > "$ARTIFACT_DIR/dc_bird_detail.txt" || true
  docker_exec "$EDGE_ROUTER" sh -lc "named-checkconf -z 2>&1 || true; printf '\n== named defaults ==\n'; cat /etc/default/named 2>/dev/null || true; printf '\n== named process ==\n'; pgrep -a named 2>/dev/null || true; printf '\n== dns sockets ==\n'; ss -lunp 2>/dev/null | grep -E '(:53|named)' || true; printf '\n== route to resolver ==\n'; birdc show route 10.50.0.0/24 2>&1 || true; ip route get $RESOLVER_IP 2>&1 || true; printf '\n== local auth dig ==\n'; dig +short +time=3 +tries=1 @$EDGE_DNS_IP $DOMAIN A 2>&1 || true; printf '\n== named log ==\n'; tail -n 80 /var/log/named.log /var/log/bind/named.log 2>/dev/null || true" > "$ARTIFACT_DIR/edge_dns_diag.txt" || true
  docker_exec "$CLIENT_ROUTER" sh -lc "birdc show route $EDGE_PREFIX 2>/dev/null || true" > "$ARTIFACT_DIR/client_route_view.txt" || true
  docker_exec "$CLIENT_ROUTER" sh -lc "printf '== protocols all ==\n'; birdc show protocols all 2>&1 || true; printf '\n== route $EDGE_PREFIX all ==\n'; birdc show route $EDGE_PREFIX all 2>&1 || true; printf '\n== export u_as10 $EDGE_PREFIX ==\n'; birdc show route export u_as10 $EDGE_PREFIX all 2>&1 || true" > "$ARTIFACT_DIR/client_bird_detail.txt" || true
  docker_exec "$CLIENT_ROUTER" sh -lc "named-checkconf -z 2>&1 || true; printf '\n== named defaults ==\n'; cat /etc/default/named 2>/dev/null || true; printf '\n== named process ==\n'; pgrep -a named 2>/dev/null || true; printf '\n== dns sockets ==\n'; ss -lunp 2>/dev/null | grep -E '(:53|named)' || true; printf '\n== route to edge dns ==\n'; birdc show route $EDGE_PREFIX 2>&1 || true; ip route get $EDGE_DNS_IP 2>&1 || true; printf '\n== direct auth dig ==\n'; dig +short +time=3 +tries=1 @$EDGE_DNS_IP $DOMAIN A 2>&1 || true; printf '\n== local resolver dig ==\n'; dig +short +time=3 +tries=1 @$RESOLVER_IP $DOMAIN A 2>&1 || true; printf '\n== named local config ==\n'; cat /etc/bind/named.conf.local 2>/dev/null || true; printf '\n== named options ==\n'; cat /etc/bind/named.conf.options 2>/dev/null || true; printf '\n== named log ==\n'; tail -n 80 /var/log/named.log /var/log/bind/named.log 2>/dev/null || true" > "$ARTIFACT_DIR/client_dns_diag.txt" || true
  docker_exec "$CLIENT" sh -lc "dig +time=2 +tries=1 @$RESOLVER_IP $DOMAIN A 2>&1 || true" > "$ARTIFACT_DIR/client_dig_latest.txt" || true
  docker_exec "$CLIENT" sh -lc "curl -fsS --max-time 3 http://$DOMAIN/ 2>&1 || true" > "$ARTIFACT_DIR/client_curl_latest.txt" || true
}

panel_snapshot() {
  local out
  mkdir -p "$ARTIFACT_DIR/showcase_panel"
  out="$ARTIFACT_DIR/showcase_panel/index.html"
  "$PYTHON_BIN" "$ROOT_DIR/examples/internet/_agent_benchmark_common/showcase_panel.py" \
    --case-dir "$SCRIPT_DIR" \
    --case-id b51 \
    --tier "$TIER" \
    --project "$PROJECT_NAME" \
    --prefix "$CONTAINER_PREFIX" \
    --snapshot-out "$out" >/dev/null
  log "showcase panel snapshot written to $out"
}

panel_runtime() {
  local port="${1:-${B51_SHOWCASE_PORT:-8510}}"
  "$PYTHON_BIN" "$ROOT_DIR/examples/internet/_agent_benchmark_common/showcase_panel.py" \
    --case-dir "$SCRIPT_DIR" \
    --case-id b51 \
    --tier "$TIER" \
    --project "$PROJECT_NAME" \
    --prefix "$CONTAINER_PREFIX" \
    --port "$port"
}

smoke() {
  local rc
  trap 'rc=$?; cleanup_after_failure "$rc"' EXIT
  generate
  up
  normal_check
  inject_fault
  fault_check
  collect
  trap - EXIT
  down
}

scale_probe_asns() {
  TIER="$(canonical_tier "$TIER")"
  case "$TIER" in
    S0) ;;
    S1) seq 51 90 ;;
    S1_5) seq 51 99; seq 102 132 ;;
    S2) seq 300 659 ;;
    *)
      echo "unsupported runtime TIER=$TIER; expected S0, S1, S1.5, or S2" >&2
      return 2
      ;;
  esac
}

scale_collector_asns() {
  TIER="$(canonical_tier "$TIER")"
  case "$TIER" in
    S0) ;;
    S1) seq 110 121 ;;
    S1_5) seq 133 148 ;;
    S2) seq 700 711 ;;
    *)
      echo "unsupported runtime TIER=$TIER; expected S0, S1, S1.5, or S2" >&2
      return 2
      ;;
  esac
}

scale_router_ip() {
  local asn="$1"
  if [ "$asn" -lt 256 ]; then
    printf '10.%s.0.254\n' "$asn"
    return 0
  fi

  local idx second third
  idx=$((asn - 256))
  second=$((220 + (idx / 256)))
  third=$((idx % 256))
  if [ "$second" -gt 224 ]; then
    echo "ASN $asn is outside the local 10.220.0.0/16-10.224.0.0/16 IPAM range" >&2
    return 2
  fi
  printf '10.%s.%s.254\n' "$second" "$third"
}

scale_router_name() {
  local asn="$1"
  local kind="$2"
  local ip
  ip="$(scale_router_ip "$asn")"
  case "$kind" in
    probe) printf '%sas%sbrd-Scale_Probe_Router_%s-%s\n' "$CONTAINER_PREFIX" "$asn" "$asn" "$ip" ;;
    collector) printf '%sas%sbrd-Scale_Route_Collector_%s-%s\n' "$CONTAINER_PREFIX" "$asn" "$asn" "$ip" ;;
    *) return 2 ;;
  esac
}

scale_runtime_normal_check() {
  local asn container
  while read -r asn; do
    [ -n "$asn" ] || continue
    container="$(scale_router_name "$asn" collector)"
    log "checking $TIER collector AS$asn route visibility"
    wait_bird_route_visible "$container" "$EDGE_PREFIX" "/tmp/meta-normal-route-$asn.txt"
    docker cp "$container:/tmp/meta-normal-route-$asn.txt" "$ARTIFACT_DIR/normal_route_collector_$asn.txt" >/dev/null
  done < <(scale_collector_asns)

  while read -r asn; do
    [ -n "$asn" ] || continue
    container="$(scale_router_name "$asn" probe)"
    log "checking $TIER probe AS$asn DNS/service"
    wait_dns_record_present "$container" "/tmp/meta-normal-dig-$asn.txt" "$(runtime_probe_dns_attempts "$TIER")"
    docker cp "$container:/tmp/meta-normal-dig-$asn.txt" "$ARTIFACT_DIR/normal_probe_dig_$asn.txt" >/dev/null
    docker_exec "$container" sh -lc "curl -fsS --max-time 3 http://$DOMAIN/" > "$ARTIFACT_DIR/normal_probe_curl_$asn.txt"
  done < <(scale_probe_asns)
}

scale_runtime_fault_check() {
  local asn container
  while read -r asn; do
    [ -n "$asn" ] || continue
    container="$(scale_router_name "$asn" collector)"
    log "checking $TIER collector AS$asn route withdrawal"
    wait_bird_route_absent "$container" "$EDGE_PREFIX" "/tmp/meta-fault-route-$asn.txt"
    docker cp "$container:/tmp/meta-fault-route-$asn.txt" "$ARTIFACT_DIR/fault_route_collector_$asn.txt" >/dev/null
  done < <(scale_collector_asns)

  while read -r asn; do
    [ -n "$asn" ] || continue
    container="$(scale_router_name "$asn" probe)"
    log "checking $TIER probe AS$asn DNS/service failure"
    wait_dns_record_absent "$container" "/tmp/meta-fault-dig-$asn.txt" "$(runtime_probe_dns_attempts "$TIER")"
    docker cp "$container:/tmp/meta-fault-dig-$asn.txt" "$ARTIFACT_DIR/fault_probe_dig_$asn.txt" >/dev/null
    if docker_exec "$container" sh -lc "curl -fsS --max-time 3 http://$DOMAIN/" > "$ARTIFACT_DIR/fault_probe_curl_$asn.txt" 2>&1; then
      echo "$TIER probe AS$asn curl unexpectedly succeeded" >&2
      return 1
    fi
  done < <(scale_probe_asns)
}

scale_runtime_recovery_check() {
  local asn container
  while read -r asn; do
    [ -n "$asn" ] || continue
    container="$(scale_router_name "$asn" collector)"
    log "checking $TIER collector AS$asn recovered route visibility"
    docker_exec "$container" sh -lc "birdc show route $EDGE_PREFIX | tee /tmp/meta-recovery-route-$asn.txt | grep -q '$EDGE_PREFIX'" >/dev/null
    docker cp "$container:/tmp/meta-recovery-route-$asn.txt" "$ARTIFACT_DIR/recovery_route_collector_$asn.txt" >/dev/null
  done < <(scale_collector_asns)

  while read -r asn; do
    [ -n "$asn" ] || continue
    container="$(scale_router_name "$asn" probe)"
    log "checking $TIER probe AS$asn recovered DNS/service"
    docker_exec "$container" sh -lc "dig +short +time=2 +tries=1 @$RESOLVER_IP $DOMAIN A | tee /tmp/meta-recovery-dig-$asn.txt | grep -q '^10.20.0.80$'"
    docker cp "$container:/tmp/meta-recovery-dig-$asn.txt" "$ARTIFACT_DIR/recovery_probe_dig_$asn.txt" >/dev/null
    docker_exec "$container" sh -lc "curl -fsS --max-time 3 http://$DOMAIN/" > "$ARTIFACT_DIR/recovery_probe_curl_$asn.txt"
  done < <(scale_probe_asns)
}

scale_runtime_agent_observe() {
  local asn container
  while read -r asn; do
    [ -n "$asn" ] || continue
    container="$(scale_router_name "$asn" collector)"
    docker_exec "$container" sh -lc "birdc show route $EDGE_PREFIX 2>&1 || true" > "$ARTIFACT_DIR/agent_route_collector_$asn.txt" 2>&1 || true
  done < <(scale_collector_asns)

  while read -r asn; do
    [ -n "$asn" ] || continue
    container="$(scale_router_name "$asn" probe)"
    docker_exec "$container" sh -lc "dig +time=2 +tries=1 @$RESOLVER_IP $DOMAIN A 2>&1 || true" > "$ARTIFACT_DIR/agent_probe_dig_$asn.txt" 2>&1 || true
    docker_exec "$container" sh -lc "curl -fsS --max-time 3 http://$DOMAIN/ 2>&1 || true" > "$ARTIFACT_DIR/agent_probe_curl_$asn.txt" 2>&1 || true
  done < <(scale_probe_asns)
}

agent_observe() {
  TIER="$(canonical_tier "$TIER")"
  require_runtime_tier "$TIER"
  require_s2_runtime_preflight
  mkdir -p "$ARTIFACT_DIR"
  log "collecting restricted agent observations"
  docker_exec "$CLIENT" sh -lc "dig +time=2 +tries=1 @$RESOLVER_IP $DOMAIN A 2>&1 || true" > "$ARTIFACT_DIR/agent_blackbox_dig.txt" 2>&1 || true
  docker_exec "$CLIENT" sh -lc "curl -fsS --max-time 3 http://$DOMAIN/ 2>&1 || true" > "$ARTIFACT_DIR/agent_blackbox_curl.txt" 2>&1 || true
  docker_exec "$CLIENT_ROUTER" sh -lc "birdc show route $EDGE_PREFIX 2>&1 || true" > "$ARTIFACT_DIR/agent_route_view.txt" 2>&1 || true
  docker_exec "$EDGE_ROUTER" sh -lc 'cat /var/run/meta-health-status 2>/dev/null || true' > "$ARTIFACT_DIR/agent_health_status.txt" 2>&1 || true
  docker_exec "$EDGE_ROUTER" sh -lc "curl -fsS --max-time 2 http://$BACKEND_IP/ 2>&1 || true" > "$ARTIFACT_DIR/agent_edge_to_backend.txt" 2>&1 || true
  docker_exec "$EDGE_ROUTER" sh -lc 'tail -n 40 /var/log/meta-health-gate.log 2>/dev/null || true' > "$ARTIFACT_DIR/agent_health_gate_tail.txt" 2>&1 || true
  docker_exec "$EDGE_ROUTER" sh -lc 'tail -n 40 /var/log/meta-recent-change.log 2>/dev/null || true' > "$ARTIFACT_DIR/agent_recent_change_tail.txt" 2>&1 || true
  scale_runtime_agent_observe
  log "agent-observe collected"
}

safe_token() {
  local value="$1"
  case "$value" in
    *[!A-Za-z0-9_.-]*|"")
      return 1
      ;;
  esac
}

exercise_require_s1_5() {
  TIER="$(canonical_tier "$TIER")"
  require_runtime_tier "$TIER"
  require_s2_runtime_preflight
  if [ "$TIER" != "S1_5" ]; then
    echo "interactive exercise commands are currently defined for S1.5 only; set TIER=S1.5" >&2
    return 2
  fi
}

exercise_id() {
  local id="${B51_EXERCISE_ID:-current}"
  if ! safe_token "$id"; then
    echo "B51_EXERCISE_ID must use only letters, digits, dot, underscore, or dash" >&2
    return 2
  fi
  printf '%s\n' "$id"
}

exercise_dir() {
  local id
  id="$(exercise_id)"
  printf '%s/exercise/%s\n' "$ARTIFACT_DIR" "$id"
}

exercise_stamp() {
  printf '%s_%s\n' "$(date -u +%Y%m%dT%H%M%SZ)" "$$"
}

exercise_event() {
  local root event detail
  event="$1"
  detail="${2:-}"
  root="$(exercise_dir)"
  mkdir -p "$root"
  printf '%s\t%s\t%s\n' "$(date -Is)" "$event" "$detail" >> "$root/events.tsv"
}

exercise_init() {
  local root
  exercise_require_s1_5
  root="$(exercise_dir)"
  mkdir -p "$root/observations" "$root/actions" "$root/gates"
  {
    printf 'exercise_id=%s\n' "$(exercise_id)"
    printf 'tier=%s\n' "$(display_tier "$TIER")"
    printf 'project=%s\n' "$PROJECT_NAME"
    printf 'status=initialized\n'
    printf 'phase=not_started\n'
    printf 'created_at=%s\n' "$(date -Is)"
  } > "$root/state.env"
  exercise_event "init" "project=$PROJECT_NAME tier=$(display_tier "$TIER")"
  cat > "$root/README.txt" <<EOF
Interactive S1.5 incident exercise workspace.

This directory is an operator ledger, not a final smoke-test result.
Use exercise-phase, exercise-observe, exercise-note, exercise-action, and
exercise-gate to record a live investigation. The exercise is designed around
role-scoped observations and staged evidence, not around revealing the root
cause at the start.
EOF
  log "exercise initialized at $root"
}

exercise_phase_usage() {
  cat >&2 <<'EOF'
usage: b51ctl.sh exercise-phase PHASE
phases:
  baseline               pre-fault user, resolver, route, and Meta edge view
  impact                 user-visible failure after the facilitator injects fault
  user-feedback          public user reports from several probe ASes
  resolver-triage        Cloudflare-like recursive resolver/support view
  external-routing       route collector and public prefix visibility view
  meta-triage            Meta NOC, DNS, and backend service triage
  dns-triage             authoritative DNS process and zone health triage
  neteng-triage          Meta edge BGP/control-plane triage
  change-audit           recent internal change review after escalation
  mitigation             restricted rollback decision and action
  recovery-verification  health-gated reannouncement and external validation
  postmortem             final ledger review and explanation
EOF
}

exercise_phase_allowed() {
  case "$1" in
    baseline|impact|user-feedback|resolver-triage|external-routing|meta-triage|dns-triage|neteng-triage|internal-triage|change-audit|mitigation|recovery-verification|verification|postmortem)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

exercise_phase() {
  local phase="${1:-}"
  local root
  exercise_require_s1_5
  if ! safe_token "$phase" || ! exercise_phase_allowed "$phase"; then
    exercise_phase_usage
    return 2
  fi
  root="$(exercise_dir)"
  mkdir -p "$root"
  if [ -f "$root/state.env" ]; then
    grep -v '^phase=' "$root/state.env" > "$root/state.env.tmp" || true
    mv "$root/state.env.tmp" "$root/state.env"
  fi
  printf 'phase=%s\n' "$phase" >> "$root/state.env"
  exercise_event "phase" "$phase"
  log "exercise phase set to $phase"
}

exercise_note() {
  local role="${1:-}"
  local root
  shift || true
  exercise_require_s1_5
  if ! safe_token "$role" || [ "$#" -eq 0 ]; then
    echo "usage: $0 exercise-note ROLE TEXT..." >&2
    return 2
  fi
  root="$(exercise_dir)"
  mkdir -p "$root"
  printf '%s\t%s\t%s\n' "$(date -Is)" "$role" "$*" >> "$root/notes.tsv"
  exercise_event "note" "role=$role"
  log "exercise note recorded for $role"
}

exercise_status() {
  local root
  exercise_require_s1_5
  root="$(exercise_dir)"
  if [ -f "$root/state.env" ]; then
    cat "$root/state.env"
  else
    echo "exercise_state=not_initialized"
  fi
  if [ -f "$root/events.tsv" ]; then
    printf '\n== recent events ==\n'
    tail -n 20 "$root/events.tsv"
  fi
}

exercise_observe_usage() {
  cat >&2 <<'EOF'
usage: b51ctl.sh exercise-observe ROLE
roles:
  public-users       DNS/HTTP from AS50, AS51, AS99, and AS132
  resolver-support   Cloudflare-like recursive resolver and authoritative reachability
  external-routing   AS133/AS140/AS148 route collector views
  meta-noc           Edge health and backend reachability, without recent-change log
  meta-dns           DNS daemon and authoritative DNS health
  meta-neteng        Edge BGP protocol and route-export state
  dc-team            Backend service and DC-side routing
  change-audit       Recent internal change log, use only after escalation
  frontline          Collect public/resolver/external-routing symptoms only
  all-roles          Collect all roles above; use for facilitator/final review
EOF
}

exercise_role_allowed() {
  case "$1" in
    public-users|resolver-support|external-routing|meta-noc|meta-dns|meta-neteng|dc-team|change-audit|frontline|all-roles)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

exercise_observe_one() {
  local role="$1"
  local dir="$2"
  mkdir -p "$dir"
  case "$role" in
    public-users)
      docker_exec "$CLIENT" sh -lc "printf '== AS50 public user DNS ==\n'; dig +time=2 +tries=1 @$RESOLVER_IP $DOMAIN A 2>&1 || true; printf '\n== AS50 public user HTTP ==\n'; curl -fsS --max-time 3 http://$DOMAIN/ 2>&1 || true" > "$dir/as50-public-user.txt" 2>&1 || true
      docker_exec "$(scale_router_name 51 probe)" sh -lc "printf '== AS51 regional user DNS ==\n'; dig +time=2 +tries=1 @$RESOLVER_IP $DOMAIN A 2>&1 || true; printf '\n== AS51 regional user HTTP ==\n'; curl -fsS --max-time 3 http://$DOMAIN/ 2>&1 || true" > "$dir/as51-regional-user.txt" 2>&1 || true
      docker_exec "$(scale_router_name 99 probe)" sh -lc "printf '== AS99 mobile-like user DNS ==\n'; dig +time=2 +tries=1 @$RESOLVER_IP $DOMAIN A 2>&1 || true; printf '\n== AS99 mobile-like user HTTP ==\n'; curl -fsS --max-time 3 http://$DOMAIN/ 2>&1 || true" > "$dir/as99-mobile-user.txt" 2>&1 || true
      docker_exec "$(scale_router_name 132 probe)" sh -lc "printf '== AS132 enterprise user DNS ==\n'; dig +time=2 +tries=1 @$RESOLVER_IP $DOMAIN A 2>&1 || true; printf '\n== AS132 enterprise user HTTP ==\n'; curl -fsS --max-time 3 http://$DOMAIN/ 2>&1 || true" > "$dir/as132-enterprise-user.txt" 2>&1 || true
      ;;
    resolver-support)
      docker_exec "$CLIENT_ROUTER" sh -lc "printf '== recursive resolver query ==\n'; dig +time=2 +tries=1 @$RESOLVER_IP $DOMAIN A 2>&1 || true; printf '\n== direct authoritative query from resolver network ==\n'; dig +time=2 +tries=1 @$EDGE_DNS_IP $DOMAIN A 2>&1 || true; printf '\n== route to edge DNS ==\n'; ip route get $EDGE_DNS_IP 2>&1 || true; printf '\n== resolver daemon ==\n'; pgrep -a named 2>&1 || true" > "$dir/resolver-support.txt" 2>&1 || true
      ;;
    external-routing)
      docker_exec "$(scale_router_name 133 collector)" sh -lc "printf '== AS133 route collector ==\n'; birdc show route $EDGE_PREFIX 2>&1 || true" > "$dir/as133-route-collector.txt" 2>&1 || true
      docker_exec "$(scale_router_name 140 collector)" sh -lc "printf '== AS140 route collector ==\n'; birdc show route $EDGE_PREFIX 2>&1 || true" > "$dir/as140-route-collector.txt" 2>&1 || true
      docker_exec "$(scale_router_name 148 collector)" sh -lc "printf '== AS148 route collector ==\n'; birdc show route $EDGE_PREFIX 2>&1 || true" > "$dir/as148-route-collector.txt" 2>&1 || true
      ;;
    meta-noc)
      docker_exec "$EDGE_ROUTER" sh -lc "printf '== edge health status ==\n'; cat /var/run/meta-health-status 2>/dev/null || true; printf '\n== edge to backend dependency ==\n'; curl -fsS --max-time 2 http://$BACKEND_IP/ 2>&1 || true; printf '\n== health-gate timeline ==\n'; tail -n 20 /var/log/meta-health-gate.log 2>/dev/null || true" > "$dir/meta-noc.txt" 2>&1 || true
      ;;
    meta-dns)
      docker_exec "$EDGE_ROUTER" sh -lc "printf '== authoritative named check ==\n'; named-checkconf -z 2>&1 || true; printf '\n== authoritative named process ==\n'; pgrep -a named 2>&1 || true; printf '\n== authoritative DNS socket ==\n'; ss -lunp 2>/dev/null | grep -E '(:53|named)' || true; printf '\n== local authoritative query ==\n'; dig +time=2 +tries=1 @$EDGE_DNS_IP $DOMAIN A 2>&1 || true" > "$dir/meta-dns.txt" 2>&1 || true
      ;;
    meta-neteng)
      docker_exec "$EDGE_ROUTER" sh -lc "printf '== edge BGP protocols ==\n'; birdc show protocols 2>&1 || true; printf '\n== internal peer c_as30 ==\n'; birdc show protocols c_as30 2>&1 || true; printf '\n== external peer u_as10 ==\n'; birdc show protocols u_as10 2>&1 || true; printf '\n== edge prefix local route ==\n'; birdc show route $EDGE_PREFIX 2>&1 || true; printf '\n== export to external transit ==\n'; birdc show route export u_as10 $EDGE_PREFIX all 2>&1 || true" > "$dir/meta-neteng.txt" 2>&1 || true
      ;;
    dc-team)
      docker_exec "$DC_ROUTER" sh -lc "printf '== backend service local check ==\n'; curl -fsS --max-time 2 http://$BACKEND_IP/ 2>&1 || true; printf '\n== DC BGP protocols ==\n'; birdc show protocols 2>&1 || true; printf '\n== DC route to edge prefix ==\n'; birdc show route $EDGE_PREFIX 2>&1 || true" > "$dir/dc-team.txt" 2>&1 || true
      ;;
    change-audit)
      docker_exec "$EDGE_ROUTER" sh -lc "printf '== recent internal changes ==\n'; cat /var/log/meta-recent-change.log 2>/dev/null || true" > "$dir/change-audit.txt" 2>&1 || true
      ;;
    *)
      return 2
      ;;
  esac
}

exercise_observe() {
  local role="${1:-}"
  local root obsdir stamp
  local nested_role
  exercise_require_s1_5
  if ! safe_token "$role" || ! exercise_role_allowed "$role"; then
    exercise_observe_usage
    return 2
  fi
  assert_runtime_live_scale
  root="$(exercise_dir)"
  stamp="$(exercise_stamp)"
  obsdir="$root/observations/${stamp}_${role}"
  mkdir -p "$obsdir"
  {
    printf 'timestamp=%s\n' "$(date -Is)"
    printf 'exercise_id=%s\n' "$(exercise_id)"
    printf 'role=%s\n' "$role"
    printf 'tier=%s\n' "$(display_tier "$TIER")"
    printf 'project=%s\n' "$PROJECT_NAME"
  } > "$obsdir/context.txt"

  if [ "$role" = "frontline" ]; then
    for nested_role in public-users resolver-support external-routing; do
      exercise_observe_one "$nested_role" "$obsdir/$nested_role"
    done
  elif [ "$role" = "all-roles" ]; then
    for nested_role in public-users resolver-support external-routing meta-noc meta-dns meta-neteng dc-team change-audit; do
      exercise_observe_one "$nested_role" "$obsdir/$nested_role"
    done
  elif ! exercise_observe_one "$role" "$obsdir"; then
    exercise_observe_usage
    return 2
  fi

  exercise_event "observe" "role=$role dir=$obsdir"
  log "exercise observation collected for $role into $obsdir"
}

exercise_action_usage() {
  cat >&2 <<'EOF'
usage: b51ctl.sh exercise-action ACTION
actions:
  inject-fault                 facilitator starts the incident
  rollback-internal-policy     operator mitigation for the internal path fault
  verify-health                verify backend health from the edge
  canary-reannounce            wait for health-gate-managed route restoration
  validate-recovery            run the full recovery validation gate
  forbidden action names are passed to the policy-deny path
EOF
}

exercise_action_known() {
  case "$1" in
    inject-fault|rollback-internal-policy|verify-health|canary-reannounce|validate-recovery|force-announce-unhealthy-prefix|force-announce|disable-health-gate|kill-dns|stop-dns|delete-zone|client-hosts-bypass|edit-oracle|global-reset)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

exercise_run_live_action() {
  local action_dir="$1"
  local rc
  shift
  rc=0
  assert_runtime_live_scale > "$action_dir/runtime-preflight.txt" 2>&1 || rc=$?
  if [ "$rc" -ne 0 ]; then
    cat "$action_dir/runtime-preflight.txt" > "$action_dir/output.txt" 2>&1 || true
    return "$rc"
  fi
  "$@" > "$action_dir/output.txt" 2>&1 || return $?
  return 0
}

exercise_observation_count() {
  local root="$1"
  local role="$2"
  find "$root/observations" -type d \( -name "*_$role" -o -name "$role" \) 2>/dev/null | wc -l | tr -d ' '
}

exercise_success_action_count() {
  local root="$1"
  local action="$2"
  local dir count
  count=0
  while IFS= read -r dir; do
    [ -f "$dir/result.env" ] || continue
    if grep -q '^result_code=0$' "$dir/result.env"; then
      count=$((count + 1))
    fi
  done < <(find "$root/actions" -maxdepth 1 -type d -name "*_$action" 2>/dev/null)
  printf '%s\n' "$count"
}

exercise_gate_usage() {
  cat >&2 <<'EOF'
usage: b51ctl.sh exercise-gate PHASE

exercise-gate checks whether the operator ledger has enough staged evidence
for a phase. It does not inspect hidden truth and it does not replace live
runtime normal/fault/recovery checks.
EOF
}

exercise_gate_require_observation() {
  local root="$1"
  local role="$2"
  local report="$3"
  local count
  count="$(exercise_observation_count "$root" "$role")"
  if [ "$count" -gt 0 ]; then
    printf 'ok observation role=%s count=%s\n' "$role" "$count" >> "$report"
    return 0
  fi
  printf 'missing observation role=%s\n' "$role" >> "$report"
  return 1
}

exercise_gate_require_action() {
  local root="$1"
  local action="$2"
  local report="$3"
  local count
  count="$(exercise_success_action_count "$root" "$action")"
  if [ "$count" -gt 0 ]; then
    printf 'ok action action=%s success_count=%s\n' "$action" "$count" >> "$report"
    return 0
  fi
  printf 'missing successful action action=%s\n' "$action" >> "$report"
  return 1
}

exercise_gate_require_notes() {
  local root="$1"
  local report="$2"
  if [ -s "$root/notes.tsv" ]; then
    printf 'ok notes file=%s\n' "$root/notes.tsv" >> "$report"
    return 0
  fi
  printf 'missing operator notes file=%s\n' "$root/notes.tsv" >> "$report"
  return 1
}

exercise_gate() {
  local phase="${1:-}"
  local root report rc role action
  exercise_require_s1_5
  if ! safe_token "$phase" || ! exercise_phase_allowed "$phase"; then
    exercise_gate_usage
    exercise_phase_usage
    return 2
  fi

  root="$(exercise_dir)"
  mkdir -p "$root/gates"
  report="$root/gates/$(exercise_stamp)_$phase.txt"
  rc=0
  {
    printf 'timestamp=%s\n' "$(date -Is)"
    printf 'exercise_id=%s\n' "$(exercise_id)"
    printf 'phase=%s\n' "$phase"
    printf 'tier=%s\n' "$(display_tier "$TIER")"
    printf 'project=%s\n' "$PROJECT_NAME"
    printf '\n'
  } > "$report"

  case "$phase" in
    baseline)
      for role in public-users resolver-support external-routing meta-noc; do
        exercise_gate_require_observation "$root" "$role" "$report" || rc=1
      done
      ;;
    impact|user-feedback)
      exercise_gate_require_observation "$root" public-users "$report" || rc=1
      exercise_gate_require_notes "$root" "$report" || rc=1
      ;;
    resolver-triage)
      for role in public-users resolver-support; do
        exercise_gate_require_observation "$root" "$role" "$report" || rc=1
      done
      exercise_gate_require_notes "$root" "$report" || rc=1
      ;;
    external-routing)
      for role in resolver-support external-routing; do
        exercise_gate_require_observation "$root" "$role" "$report" || rc=1
      done
      exercise_gate_require_notes "$root" "$report" || rc=1
      ;;
    meta-triage|dns-triage|internal-triage)
      for role in external-routing meta-noc meta-dns dc-team; do
        exercise_gate_require_observation "$root" "$role" "$report" || rc=1
      done
      exercise_gate_require_notes "$root" "$report" || rc=1
      ;;
    neteng-triage)
      for role in meta-noc meta-dns dc-team meta-neteng; do
        exercise_gate_require_observation "$root" "$role" "$report" || rc=1
      done
      exercise_gate_require_notes "$root" "$report" || rc=1
      ;;
    change-audit)
      for role in meta-neteng change-audit; do
        exercise_gate_require_observation "$root" "$role" "$report" || rc=1
      done
      exercise_gate_require_notes "$root" "$report" || rc=1
      ;;
    mitigation)
      for role in public-users resolver-support external-routing meta-noc meta-dns dc-team meta-neteng change-audit; do
        exercise_gate_require_observation "$root" "$role" "$report" || rc=1
      done
      exercise_gate_require_notes "$root" "$report" || rc=1
      ;;
    recovery-verification|verification)
      for role in public-users external-routing meta-noc; do
        exercise_gate_require_observation "$root" "$role" "$report" || rc=1
      done
      for action in rollback-internal-policy verify-health canary-reannounce validate-recovery; do
        exercise_gate_require_action "$root" "$action" "$report" || rc=1
      done
      exercise_gate_require_notes "$root" "$report" || rc=1
      ;;
    postmortem)
      for role in public-users resolver-support external-routing meta-noc meta-dns dc-team meta-neteng change-audit; do
        exercise_gate_require_observation "$root" "$role" "$report" || rc=1
      done
      for action in rollback-internal-policy verify-health canary-reannounce validate-recovery; do
        exercise_gate_require_action "$root" "$action" "$report" || rc=1
      done
      exercise_gate_require_notes "$root" "$report" || rc=1
      ;;
  esac

  if [ "$rc" -eq 0 ]; then
    printf '\nresult=pass\n' >> "$report"
    exercise_event "gate-pass" "phase=$phase report=$report"
    log "exercise gate passed for $phase; report=$report"
    return 0
  fi

  printf '\nresult=fail\n' >> "$report"
  exercise_event "gate-fail" "phase=$phase report=$report"
  cat "$report" >&2
  return 1
}

exercise_action() {
  local action="${1:-}"
  local root action_dir rc
  exercise_require_s1_5
  if ! safe_token "$action" || ! exercise_action_known "$action"; then
    exercise_action_usage
    return 2
  fi
  root="$(exercise_dir)"
  action_dir="$root/actions/$(exercise_stamp)_$action"
  mkdir -p "$action_dir"
  exercise_event "action-start" "$action"
  rc=0
  case "$action" in
    inject-fault)
      exercise_run_live_action "$action_dir" inject_fault || rc=$?
      ;;
    rollback-internal-policy)
      exercise_run_live_action "$action_dir" agent_act rollback-internal-policy || rc=$?
      ;;
    verify-health)
      exercise_run_live_action "$action_dir" agent_act verify-health || rc=$?
      ;;
    canary-reannounce)
      exercise_run_live_action "$action_dir" agent_act canary-reannounce || rc=$?
      ;;
    validate-recovery)
      exercise_run_live_action "$action_dir" recovery_check || rc=$?
      ;;
    force-announce-unhealthy-prefix|force-announce|disable-health-gate|kill-dns|stop-dns|delete-zone|client-hosts-bypass|edit-oracle|global-reset)
      agent_act "$action" > "$action_dir/output.txt" 2>&1 || rc=$?
      ;;
  esac
  printf 'action=%s\nresult_code=%s\n' "$action" "$rc" > "$action_dir/result.env"
  exercise_event "action-end" "action=$action rc=$rc dir=$action_dir"
  if [ "$rc" -ne 0 ]; then
    cat "$action_dir/output.txt" >&2 || true
    return "$rc"
  fi
  log "exercise action completed: $action"
}

demo_snapshot() {
  local phase="${1:-snapshot}"
  TIER="$(canonical_tier "$TIER")"
  require_runtime_tier "$TIER"
  require_s2_runtime_preflight
  if [ "$TIER" != "S1_5" ]; then
    echo "demo-snapshot is currently defined for S1.5 only; set TIER=S1.5" >&2
    return 2
  fi

  case "$phase" in
    *[!A-Za-z0-9_.-]*|"")
      echo "demo snapshot phase must use only letters, digits, dot, underscore, or dash" >&2
      return 2
      ;;
  esac

  local dir="$ARTIFACT_DIR/demo/$phase"
  mkdir -p "$dir"
  log "collecting S1.5 incident demo snapshot: $phase"

  {
    printf 'timestamp=%s\n' "$(date -Is)"
    printf 'tier=%s\n' "$(display_tier "$TIER")"
    printf 'project=%s\n' "$PROJECT_NAME"
    printf 'phase=%s\n' "$phase"
    printf 'domain=%s\n' "$DOMAIN"
    printf 'edge_prefix=%s\n' "$EDGE_PREFIX"
    printf 'resolver_ip=%s\n' "$RESOLVER_IP"
    printf 'edge_dns_ip=%s\n' "$EDGE_DNS_IP"
    printf 'edge_service_ip=%s\n' "$EDGE_SERVICE_IP"
    printf 'backend_ip=%s\n' "$BACKEND_IP"
  } > "$dir/00-context.txt"

  docker_exec "$CLIENT" sh -lc "printf '== public user DNS ==\n'; dig +time=2 +tries=1 @$RESOLVER_IP $DOMAIN A 2>&1 || true; printf '\n== public user HTTP ==\n'; curl -fsS --max-time 3 http://$DOMAIN/ 2>&1 || true" > "$dir/10-public-user-as50.txt" 2>&1 || true
  docker_exec "$(scale_router_name 51 probe)" sh -lc "printf '== regional user AS51 DNS ==\n'; dig +time=2 +tries=1 @$RESOLVER_IP $DOMAIN A 2>&1 || true; printf '\n== regional user AS51 HTTP ==\n'; curl -fsS --max-time 3 http://$DOMAIN/ 2>&1 || true" > "$dir/11-regional-user-as51.txt" 2>&1 || true
  docker_exec "$(scale_router_name 99 probe)" sh -lc "printf '== mobile-like user AS99 DNS ==\n'; dig +time=2 +tries=1 @$RESOLVER_IP $DOMAIN A 2>&1 || true; printf '\n== mobile-like user AS99 HTTP ==\n'; curl -fsS --max-time 3 http://$DOMAIN/ 2>&1 || true" > "$dir/12-mobile-user-as99.txt" 2>&1 || true
  docker_exec "$(scale_router_name 132 probe)" sh -lc "printf '== enterprise user AS132 DNS ==\n'; dig +time=2 +tries=1 @$RESOLVER_IP $DOMAIN A 2>&1 || true; printf '\n== enterprise user AS132 HTTP ==\n'; curl -fsS --max-time 3 http://$DOMAIN/ 2>&1 || true" > "$dir/13-enterprise-user-as132.txt" 2>&1 || true

  docker_exec "$CLIENT_ROUTER" sh -lc "printf '== Cloudflare-like recursive resolver route view ==\n'; birdc show route $EDGE_PREFIX 2>&1 || true; printf '\n== resolver direct authoritative query ==\n'; dig +time=2 +tries=1 @$EDGE_DNS_IP $DOMAIN A 2>&1 || true" > "$dir/20-cloudflare-like-resolver-as50.txt" 2>&1 || true
  docker_exec "$(scale_router_name 133 collector)" sh -lc "printf '== external route collector AS133 ==\n'; birdc show route $EDGE_PREFIX 2>&1 || true" > "$dir/21-route-collector-as133.txt" 2>&1 || true
  docker_exec "$(scale_router_name 148 collector)" sh -lc "printf '== external route collector AS148 ==\n'; birdc show route $EDGE_PREFIX 2>&1 || true" > "$dir/22-route-collector-as148.txt" 2>&1 || true

  docker_exec "$EDGE_ROUTER" sh -lc "printf '== Meta edge health ==\n'; cat /var/run/meta-health-status 2>/dev/null || true; printf '\n== edge to backend ==\n'; curl -fsS --max-time 2 http://$BACKEND_IP/ 2>&1 || true; printf '\n== health gate timeline ==\n'; tail -n 20 /var/log/meta-health-gate.log 2>/dev/null || true" > "$dir/30-meta-edge-noc.txt" 2>&1 || true
  docker_exec "$EDGE_ROUTER" sh -lc "printf '== edge BGP protocols ==\n'; birdc show protocols 2>&1 || true; printf '\n== edge prefix local route ==\n'; birdc show route $EDGE_PREFIX 2>&1 || true; printf '\n== export to external transit ==\n'; birdc show route export u_as10 $EDGE_PREFIX all 2>&1 || true; printf '\n== internal peer c_as30 ==\n'; birdc show protocols c_as30 2>&1 || true" > "$dir/31-meta-edge-routing.txt" 2>&1 || true
  docker_exec "$DC_ROUTER" sh -lc "printf '== DC backend service ==\n'; curl -fsS --max-time 2 http://$BACKEND_IP/ 2>&1 || true; printf '\n== DC BGP protocols ==\n'; birdc show protocols 2>&1 || true" > "$dir/32-meta-dc-backend.txt" 2>&1 || true
  docker_exec "$EDGE_ROUTER" sh -lc "printf '== recent internal changes ==\n'; cat /var/log/meta-recent-change.log 2>/dev/null || true" > "$dir/40-change-audit-escalation.txt" 2>&1 || true

  cat > "$dir/README.txt" <<EOF
S1.5 incident demo snapshot: $phase

Read order:
1. 10-public-user-as50.txt plus AS51/AS99/AS132 samples show user-visible symptoms.
2. 20-cloudflare-like-resolver-as50.txt shows recursive-resolver and upstream-route observations.
3. 21/22 route collectors show whether the edge prefix is globally visible.
4. 30-meta-edge-noc.txt shows health-gate and internal dependency state.
5. 31-meta-edge-routing.txt separates BGP control-plane state from DNS/HTTP state.
6. 32-meta-dc-backend.txt verifies whether the backend service itself is alive.
EOF

  log "demo snapshot collected into $dir"
}

policy_deny_action() {
  local action="$1"
  mkdir -p "$ARTIFACT_DIR"
  printf 'action=%s\nresult=denied\nreason=forbidden by benchmark policy\n' "$action" > "$ARTIFACT_DIR/agent_policy_denied_${action}.txt"
  echo "agent action '$action' denied by benchmark policy" >&2
  return 3
}

agent_act() {
  local action="${1:-}"
  TIER="$(canonical_tier "$TIER")"
  require_runtime_tier "$TIER"
  require_s2_runtime_preflight
  mkdir -p "$ARTIFACT_DIR"
  case "$action" in
    rollback-internal-policy|clear-internal-policy)
      log "agent action: rollback internal path policy fault"
      docker_exec "$EDGE_ROUTER" /usr/local/bin/meta-backbone-fault.sh clear > "$ARTIFACT_DIR/agent_action_${action}.txt" 2>&1
      ;;
    verify-health)
      log "agent action: verify internal health"
      wait_health_status healthy
      docker_exec "$EDGE_ROUTER" sh -lc "printf 'health='; cat /var/run/meta-health-status 2>/dev/null || true; curl -fsS --max-time 2 http://$BACKEND_IP/" > "$ARTIFACT_DIR/agent_action_verify-health.txt" 2>&1
      ;;
    canary-reannounce)
      log "agent action: canary reannounce through health gate"
      wait_health_status healthy
      docker_exec "$CLIENT_ROUTER" sh -lc "for i in \$(seq 1 60); do birdc show route $EDGE_PREFIX | tee /tmp/meta-agent-canary-route.txt; grep -q '$EDGE_PREFIX' /tmp/meta-agent-canary-route.txt && exit 0; sleep 1; done; exit 1" > "$ARTIFACT_DIR/agent_action_canary-reannounce.txt" 2>&1
      ;;
    force-announce-unhealthy-prefix|force-announce|disable-health-gate|kill-dns|stop-dns|delete-zone|client-hosts-bypass|edit-oracle|global-reset)
      policy_deny_action "$action"
      ;;
    *)
      echo "usage: $0 agent-act {rollback-internal-policy|clear-internal-policy|verify-health|canary-reannounce}" >&2
      echo "forbidden examples: force-announce-unhealthy-prefix, disable-health-gate, kill-dns, delete-zone, client-hosts-bypass, edit-oracle, global-reset" >&2
      return 2
      ;;
  esac
}

recover() {
  TIER="$(canonical_tier "$TIER")"
  require_runtime_tier "$TIER"
  require_s2_runtime_preflight
  mkdir -p "$ARTIFACT_DIR"
  log "running restricted recovery sequence"
  agent_observe
  agent_act rollback-internal-policy
  wait_health_status healthy
  agent_act verify-health
  agent_act canary-reannounce
  log "recover completed"
}

recovery_check() {
  TIER="$(canonical_tier "$TIER")"
  require_runtime_tier "$TIER"
  require_s2_runtime_preflight
  mkdir -p "$ARTIFACT_DIR"
  log "checking recovered live runtime scale"
  assert_runtime_live_scale
  log "checking recovered health gate"
  wait_health_status healthy
  docker_exec "$EDGE_ROUTER" sh -lc "curl -fsS --max-time 2 http://$BACKEND_IP/" > "$ARTIFACT_DIR/recovery_edge_to_backend.txt"

  log "checking recovered DNS"
  docker_exec "$CLIENT" sh -lc "dig +short +time=2 +tries=1 @$RESOLVER_IP $DOMAIN A | tee /tmp/meta-recovery-dig.txt | grep -q '^10.20.0.80$'"
  docker cp "$CLIENT:/tmp/meta-recovery-dig.txt" "$ARTIFACT_DIR/recovery_dig.txt" >/dev/null

  log "checking recovered service access"
  docker_exec "$CLIENT" sh -lc "curl -fsS --max-time 3 http://$DOMAIN/" > "$ARTIFACT_DIR/recovery_curl.txt"

  log "checking recovered route visibility"
  docker_exec "$CLIENT_ROUTER" sh -lc "birdc show route $EDGE_PREFIX | tee /tmp/meta-recovery-route.txt | grep -q '$EDGE_PREFIX'" >/dev/null
  docker cp "$CLIENT_ROUTER:/tmp/meta-recovery-route.txt" "$ARTIFACT_DIR/recovery_route.txt" >/dev/null
  scale_runtime_recovery_check
  log "recovery-check passed"
}

with_runtime_artifacts() {
  local tier
  tier="$(canonical_tier "$1")"
  local action="$2"
  local previous_tier="$TIER"
  local previous_artifact_dir="$ARTIFACT_DIR"
  shift 2
  TIER="$tier"
  ARTIFACT_DIR="$SCRIPT_DIR/test_log/runtime/$tier"
  mkdir -p "$ARTIFACT_DIR"
  "$action" "$@"
  TIER="$previous_tier"
  ARTIFACT_DIR="$previous_artifact_dir"
}

runtime_smoke_body() {
  local tier
  tier="$(canonical_tier "$1")"
  log "runtime smoke for $(display_tier "$tier")"
  generate
  up
  normal_check
  inject_fault
  fault_check
  collect
  down
}

runtime_smoke_tier() {
  local tier
  tier="$(canonical_tier "$1")"
  rm -rf "$SCRIPT_DIR/test_log/runtime/$tier"
  with_runtime_artifacts "$tier" runtime_smoke_body "$tier"
}

intervention_smoke() {
  local rc
  trap 'rc=$?; cleanup_after_failure "$rc"' EXIT
  generate
  up
  normal_check
  inject_fault
  fault_check
  agent_observe
  recover
  recovery_check
  collect
  trap - EXIT
  down
}

with_intervention_artifacts() {
  local tier
  tier="$(canonical_tier "$1")"
  local action="$2"
  local previous_tier="$TIER"
  local previous_artifact_dir="$ARTIFACT_DIR"
  shift 2
  TIER="$tier"
  ARTIFACT_DIR="$SCRIPT_DIR/test_log/intervention/$tier"
  mkdir -p "$ARTIFACT_DIR"
  "$action" "$@"
  TIER="$previous_tier"
  ARTIFACT_DIR="$previous_artifact_dir"
}

runtime_intervention_smoke_body() {
  local tier
  tier="$(canonical_tier "$1")"
  log "runtime intervention smoke for $(display_tier "$tier")"
  generate
  up
  normal_check
  inject_fault
  fault_check
  agent_observe
  recover
  recovery_check
  collect
  down
}

runtime_intervention_smoke_tier() {
  local tier
  tier="$(canonical_tier "$1")"
  rm -rf "$SCRIPT_DIR/test_log/intervention/$tier"
  with_intervention_artifacts "$tier" runtime_intervention_smoke_body "$tier"
}

runtime_ladder_smoke() {
  local tier rc
  for tier in $RUNTIME_LADDER; do
    tier="$(canonical_tier "$tier")"
    require_runtime_tier "$tier"
    trap 'rc=$?; cleanup_after_failure "$rc"' EXIT
    runtime_smoke_tier "$tier"
    trap - EXIT
  done
  log "runtime-ladder-smoke passed"
}

runtime_intervention_ladder_smoke() {
  local tier rc
  for tier in $RUNTIME_LADDER; do
    tier="$(canonical_tier "$tier")"
    require_runtime_tier "$tier"
    trap 'rc=$?; cleanup_after_failure "$rc"' EXIT
    runtime_intervention_smoke_tier "$tier"
    trap - EXIT
  done
  log "runtime-intervention-ladder-smoke passed"
}

telemetry_generate() {
  local tier="${1:-}"
  if [ -z "$tier" ]; then
    echo "telemetry-generate requires S1 or S2" >&2
    return 2
  fi
  log "generating $tier telemetry fixture; this is not runtime tier acceptance"
  (cd "$SCRIPT_DIR" && "$PYTHON_BIN" ./scale_background.py generate --tier "$tier" --output-root "$TELEMETRY_OUTPUT_DIR")
}

telemetry_check() {
  local tier="${1:-}"
  if [ -z "$tier" ]; then
    echo "telemetry-check requires S1 or S2" >&2
    return 2
  fi
  log "checking $tier telemetry fixture; this is not runtime tier acceptance"
  (cd "$SCRIPT_DIR" && "$PYTHON_BIN" ./scale_background.py verify --tier "$tier" --output-root "$TELEMETRY_OUTPUT_DIR")
}

telemetry_smoke() {
  for tier in S1 S2; do
    telemetry_generate "$tier"
    telemetry_check "$tier"
  done
  log "telemetry-smoke passed; no runtime tier was accepted by this command"
}

ambiguous_scale_smoke() {
  echo "scale-smoke is intentionally disabled because it was ambiguous." >&2
  echo "Use runtime-ladder-smoke for live SEED Docker runtime tiers." >&2
  echo "Use telemetry-smoke only for non-acceptance route-view/probe-log fixtures." >&2
  return 2
}

full_smoke() {
  runtime_ladder_smoke
  log "full-smoke passed for the current runtime ladder only"
}

runtime_command() {
  local action="$1"
  shift
  local tier
  tier="$(canonical_tier "${1:-$TIER}")"
  if [ "$#" -gt 0 ]; then
    shift
  fi
  require_runtime_tier "$tier"
  with_runtime_artifacts "$tier" "$action" "$@"
}

runtime_agent_act_command() {
  local tier
  tier="$(canonical_tier "$TIER")"
  if [ "$#" -gt 0 ] && is_runtime_tier "$1"; then
    tier="$(canonical_tier "$1")"
    shift
  fi
  require_runtime_tier "$tier"
  with_runtime_artifacts "$tier" agent_act "$@"
}

cmd="${1:-}"
if [ "$#" -gt 0 ]; then
  shift
fi

case "$cmd" in
  generate) generate ;;
  generate-runtime) runtime_command generate "$@" ;;
  up) up ;;
  up-runtime) runtime_command up "$@" ;;
  down) down ;;
  down-runtime) runtime_command down "$@" ;;
  status) status ;;
  normal-check) normal_check ;;
  normal-runtime|normal-check-runtime) runtime_command normal_check "$@" ;;
  inject-fault) inject_fault ;;
  inject-fault-runtime) runtime_command inject_fault "$@" ;;
  fault-check) fault_check ;;
  fault-runtime|fault-check-runtime) runtime_command fault_check "$@" ;;
  agent-observe) agent_observe ;;
  agent-observe-runtime) runtime_command agent_observe "$@" ;;
  agent-act) agent_act "$@" ;;
  agent-act-runtime) runtime_agent_act_command "$@" ;;
  recover) recover ;;
  recover-runtime) runtime_command recover "$@" ;;
  recovery-check) recovery_check ;;
  recovery-runtime|recovery-check-runtime) runtime_command recovery_check "$@" ;;
  exercise-init) exercise_init "$@" ;;
  exercise-init-runtime) runtime_command exercise_init "$@" ;;
  exercise-phase) exercise_phase "$@" ;;
  exercise-phase-runtime) runtime_command exercise_phase "$@" ;;
  exercise-note) exercise_note "$@" ;;
  exercise-note-runtime) runtime_command exercise_note "$@" ;;
  exercise-status) exercise_status ;;
  exercise-status-runtime) runtime_command exercise_status "$@" ;;
  exercise-gate) exercise_gate "$@" ;;
  exercise-gate-runtime) runtime_command exercise_gate "$@" ;;
  exercise-observe) exercise_observe "$@" ;;
  exercise-observe-runtime) runtime_command exercise_observe "$@" ;;
  exercise-action) exercise_action "$@" ;;
  exercise-action-runtime) runtime_command exercise_action "$@" ;;
  demo-snapshot) demo_snapshot "$@" ;;
  demo-snapshot-runtime) runtime_command demo_snapshot "$@" ;;
  panel-snapshot|showcase-snapshot) panel_snapshot ;;
  panel-snapshot-runtime|showcase-snapshot-runtime) runtime_command panel_snapshot "$@" ;;
  panel|showcase-panel) panel_runtime "$@" ;;
  panel-runtime|showcase-panel-runtime) runtime_command panel_runtime "$@" ;;
  collect) collect ;;
  collect-runtime) runtime_command collect "$@" ;;
  host-diagnose) host_diagnose "$@" ;;
  s2-preflight) s2_preflight_report ;;
  smoke) smoke ;;
  intervention-smoke) intervention_smoke ;;
  runtime-tier-smoke) runtime_command smoke "$@" ;;
  runtime-intervention-tier-smoke) runtime_command intervention_smoke "$@" ;;
  runtime-ladder-smoke) runtime_ladder_smoke ;;
  runtime-scale-smoke) runtime_ladder_smoke ;;
  runtime-intervention-ladder-smoke) runtime_intervention_ladder_smoke ;;
  telemetry-generate) telemetry_generate "$@" ;;
  telemetry-check) telemetry_check "$@" ;;
  telemetry-smoke) telemetry_smoke ;;
  scale-generate) log "deprecated alias: use telemetry-generate; telemetry is not runtime acceptance"; telemetry_generate "$@" ;;
  scale-check) log "deprecated alias: use telemetry-check; telemetry is not runtime acceptance"; telemetry_check "$@" ;;
  scale-smoke) ambiguous_scale_smoke ;;
  logical-scale-smoke) log "deprecated alias: use telemetry-smoke; telemetry is not runtime acceptance"; telemetry_smoke ;;
  full-smoke) full_smoke ;;
  *)
    echo "Usage: $0 {generate|generate-runtime [S0|S1|S1.5|S2]|up|up-runtime [S0|S1|S1.5|S2]|down|status|normal-check|normal-runtime [S0|S1|S1.5|S2]|inject-fault|fault-check|fault-runtime [S0|S1|S1.5|S2]|agent-observe|agent-act ACTION|agent-act-runtime [S0|S1|S1.5|S2] ACTION|recover|recovery-check|exercise-init|exercise-phase PHASE|exercise-note ROLE TEXT|exercise-status|exercise-gate PHASE|exercise-observe ROLE|exercise-action ACTION|demo-snapshot PHASE|demo-snapshot-runtime [S1.5] PHASE|panel-snapshot-runtime [S0|S1|S1.5|S2]|panel-runtime [S0|S1|S1.5|S2] [PORT]|collect|host-diagnose [LABEL]|s2-preflight|smoke|intervention-smoke|runtime-tier-smoke [S0|S1|S1.5|S2]|runtime-intervention-tier-smoke [S0|S1|S1.5|S2]|runtime-ladder-smoke|runtime-intervention-ladder-smoke|telemetry-generate S1|S2|telemetry-check S1|S2|telemetry-smoke|full-smoke}" >&2
    exit 2
    ;;
esac
