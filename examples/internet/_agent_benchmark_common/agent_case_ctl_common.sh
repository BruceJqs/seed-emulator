#!/usr/bin/env bash
set -euo pipefail

ab_init() {
  : "${CASE_ID:?CASE_ID is required before sourcing agent_case_ctl_common.sh}"
  : "${CASE_SLUG:?CASE_SLUG is required before sourcing agent_case_ctl_common.sh}"
  : "${CASE_GENERATOR:?CASE_GENERATOR is required before sourcing agent_case_ctl_common.sh}"
  : "${CONTAINER_PREFIX:?CONTAINER_PREFIX is required before sourcing agent_case_ctl_common.sh}"

  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)"
  ROOT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
  OUTPUT_DIR="$SCRIPT_DIR/output"
  PLATFORM="${PLATFORM:-amd}"
  if [ -n "${SEED_PYTHON:-}" ]; then
    PYTHON_BIN="$SEED_PYTHON"
  elif [ -x "$ROOT_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi
  PROJECT_NAME="${COMPOSE_PROJECT_NAME:-seed_${CASE_SLUG}_s0}"
  TIER="${TIER:-S0}"
  ARTIFACT_DIR="$SCRIPT_DIR/test_log/runtime/$(ab_canonical_tier "$TIER")"
  RUNTIME_LADDER="${RUNTIME_LADDER:-S0}"
}

ab_log() {
  printf '[%sctl] %s\n' "$CASE_ID" "$*"
}

ab_canonical_tier() {
  case "${1:-S0}" in
    S1.5|S1_5|S15|s1.5|s1_5|s15) printf '%s\n' "S1_5" ;;
    s0|S0) printf '%s\n' "S0" ;;
    s1|S1) printf '%s\n' "S1" ;;
    s2|S2) printf '%s\n' "S2" ;;
    *) printf '%s\n' "$1" ;;
  esac
}

ab_display_tier() {
  case "$(ab_canonical_tier "$1")" in
    S1_5) printf '%s\n' "S1.5" ;;
    *) printf '%s\n' "$(ab_canonical_tier "$1")" ;;
  esac
}

ab_require_tier() {
  case "$(ab_canonical_tier "${1:-}")" in
    S0|S1|S1_5|S2) return 0 ;;
    *)
      echo "unsupported runtime tier ${1:-}; expected S0, S1, S1.5, or S2" >&2
      return 2
      ;;
  esac
}

ab_runtime_min_containers() {
  if declare -F case_runtime_min_containers >/dev/null 2>&1; then
    case_runtime_min_containers "$(ab_canonical_tier "$1")"
    return
  fi
  case "$(ab_canonical_tier "$1")" in
    S0) printf '%s\n' 6 ;;
    S1) printf '%s\n' 110 ;;
    S1_5) printf '%s\n' 170 ;;
    S2) printf '%s\n' 900 ;;
    *) ab_require_tier "$1" ;;
  esac
}

ab_runtime_wait_seconds() {
  if declare -F case_runtime_wait_seconds >/dev/null 2>&1; then
    case_runtime_wait_seconds "$(ab_canonical_tier "$1")"
    return
  fi
  case "$(ab_canonical_tier "$1")" in
    S0) printf '%s\n' 35 ;;
    S1) printf '%s\n' 55 ;;
    S1_5) printf '%s\n' 75 ;;
    S2) printf '%s\n' 180 ;;
    *) ab_require_tier "$1" ;;
  esac
}

ab_runtime_attempts() {
  case "$(ab_canonical_tier "$1")" in
    S0) printf '%s\n' 45 ;;
    S1) printf '%s\n' 90 ;;
    S1_5) printf '%s\n' 140 ;;
    S2) printf '%s\n' 260 ;;
    *) ab_require_tier "$1" ;;
  esac
}

ab_compose_parallel_limit() {
  case "$(ab_canonical_tier "$1")" in
    S0|S1|S1_5) printf '%s\n' 32 ;;
    S2) printf '%s\n' 1 ;;
    *) ab_require_tier "$1" ;;
  esac
}

ab_env_flag_enabled() {
  case "${1:-0}" in
    1|true|TRUE|yes|YES|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

ab_first_line() {
  awk 'NR == 1 { first = $0 } END { if (NR > 0) print first }'
}

ab_last_line() {
  awk '{ last = $0 } END { if (NR > 0) print last }'
}

ab_take_lines() {
  local count="${1:?line count is required}"
  awk -v max="$count" 'NR <= max { print }'
}

ab_host_sysctl_value() {
  local key="$1"
  local path="/proc/sys/${key//.//}"
  if [ -r "$path" ]; then
    cat "$path"
  else
    printf '0\n'
  fi
}

ab_collect_host_diagnostics() {
  local dir="${1:-$ARTIFACT_DIR/host}"
  mkdir -p "$dir"
  {
    printf 'timestamp=%s\n' "$(date -Is)"
    printf 'case_id=%s\n' "$CASE_ID"
    printf 'project=%s\n' "$PROJECT_NAME"
    printf 'tier=%s\n' "$(ab_display_tier "$TIER")"
    printf '\n== uname ==\n'
    uname -a 2>&1 || true
    printf '\n== memory ==\n'
    free -h 2>&1 || true
    printf '\n== neighbor thresholds ==\n'
    for key in \
      net.ipv4.neigh.default.gc_thresh1 \
      net.ipv4.neigh.default.gc_thresh2 \
      net.ipv4.neigh.default.gc_thresh3; do
      printf '%s=%s\n' "$key" "$(ab_host_sysctl_value "$key")"
    done
    printf '\n== docker counts ==\n'
    printf 'running_containers=%s\n' "$(docker ps --format '{{.Names}}' 2>/dev/null | wc -l | tr -d ' ')"
    printf 'compose_project_containers=%s\n' "$(docker ps -a --filter "label=com.docker.compose.project=$PROJECT_NAME" --format '{{.Names}}' 2>/dev/null | wc -l | tr -d ' ')"
    printf 'case_named_containers=%s\n' "$(docker ps -a --filter "name=$CONTAINER_PREFIX" --format '{{.Names}}' 2>/dev/null | wc -l | tr -d ' ')"
    printf '\n== host neighbor count ==\n'
    ip -s neigh show 2>/dev/null | wc -l | tr -d ' ' || true
    printf '\n== docker system df ==\n'
    docker system df 2>&1 || true
  } > "$dir/host_status.txt" 2>&1 || true
  docker ps -a --format '{{.Names}}' > "$dir/docker_containers.txt" 2>&1 || true
  docker network ls --format '{{.Name}} {{.Driver}} {{.Scope}}' > "$dir/docker_networks.txt" 2>&1 || true
  ip -s neigh show > "$dir/host_neighbors.txt" 2>&1 || true
}

ab_s2_runtime_enabled() {
  local case_var="${CASE_ID^^}_ALLOW_S2_RUNTIME"
  ab_env_flag_enabled "${!case_var:-${AGENT_BENCH_ALLOW_S2_RUNTIME:-0}}"
}

ab_s2_preflight() {
  local previous_tier="$TIER"
  local previous_artifact_dir="$ARTIFACT_DIR"
  local report_dir gc1 gc2 gc3 rc
  rc=0
  TIER="S2"
  ARTIFACT_DIR="$SCRIPT_DIR/test_log/host_diagnostics/S2-preflight"
  report_dir="$ARTIFACT_DIR"
  mkdir -p "$report_dir"
  ab_collect_host_diagnostics "$report_dir"
  gc1="$(ab_host_sysctl_value net.ipv4.neigh.default.gc_thresh1)"
  gc2="$(ab_host_sysctl_value net.ipv4.neigh.default.gc_thresh2)"
  gc3="$(ab_host_sysctl_value net.ipv4.neigh.default.gc_thresh3)"
  {
    printf 'tier=S2\n'
    printf 'diagnostic_only=true\n'
    printf 'starts_containers=false\n'
    printf 'case_id=%s\n' "$CASE_ID"
    printf 'observed_gc_thresh1=%s\n' "$gc1"
    printf 'observed_gc_thresh2=%s\n' "$gc2"
    printf 'observed_gc_thresh3=%s\n' "$gc3"
    printf 'required_gc_thresh1=4096\n'
    printf 'required_gc_thresh2=8192\n'
    printf 'required_gc_thresh3=65536\n'
  } > "$report_dir/s2_preflight.txt"
  if ! ab_s2_runtime_enabled; then
    {
      echo "status=blocked"
      echo "reason=AGENT_BENCH_ALLOW_S2_RUNTIME or ${CASE_ID^^}_ALLOW_S2_RUNTIME is not set"
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
  ab_log "S2 preflight diagnostics collected into $report_dir"
  TIER="$previous_tier"
  ARTIFACT_DIR="$previous_artifact_dir"
  return "$rc"
}

ab_require_s2_preflight() {
  [ "$(ab_canonical_tier "$TIER")" = "S2" ] || return 0
  if ! ab_s2_runtime_enabled; then
    echo "S2 runtime is disabled by default for $CASE_ID; run s2-preflight and set AGENT_BENCH_ALLOW_S2_RUNTIME=1 only on a prepared host." >&2
    return 2
  fi
  local gc1 gc2 gc3
  gc1="$(ab_host_sysctl_value net.ipv4.neigh.default.gc_thresh1)"
  gc2="$(ab_host_sysctl_value net.ipv4.neigh.default.gc_thresh2)"
  gc3="$(ab_host_sysctl_value net.ipv4.neigh.default.gc_thresh3)"
  if [ "$gc1" -lt 4096 ] || [ "$gc2" -lt 8192 ] || [ "$gc3" -lt 65536 ]; then
    echo "S2 host preflight failed for $CASE_ID: gc_thresh1=$gc1 gc_thresh2=$gc2 gc_thresh3=$gc3" >&2
    return 2
  fi
}

ab_compose() {
  if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_PROJECT_NAME="$PROJECT_NAME" COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT:-$(ab_compose_parallel_limit "$TIER")}" DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 docker-compose "$@"
  elif docker compose version >/dev/null 2>&1; then
    COMPOSE_PROJECT_NAME="$PROJECT_NAME" COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT:-$(ab_compose_parallel_limit "$TIER")}" DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 docker compose "$@"
  else
    echo "docker-compose or docker compose is required" >&2
    return 1
  fi
}

ab_live_container_count() {
  docker ps --filter "label=com.docker.compose.project=$PROJECT_NAME" --format '{{.Names}}' | wc -l | tr -d ' '
}

ab_assert_live_scale() {
  local expected actual
  expected="$(ab_runtime_min_containers "$TIER")"
  actual="$(ab_live_container_count)"
  mkdir -p "$ARTIFACT_DIR"
  printf 'case_id=%s\ntier=%s\nproject=%s\nlive_containers=%s\nminimum_required=%s\n' \
    "$CASE_ID" "$(ab_display_tier "$TIER")" "$PROJECT_NAME" "$actual" "$expected" > "$ARTIFACT_DIR/runtime_container_count.txt"
  if [ "$actual" -lt "$expected" ]; then
    echo "$(ab_display_tier "$TIER") live container check failed for $CASE_ID: $actual < $expected" >&2
    return 1
  fi
  ab_log "$(ab_display_tier "$TIER") live container check passed: $actual >= $expected"
}

ab_generate() {
  TIER="$(ab_canonical_tier "$TIER")"
  ab_require_tier "$TIER"
  ab_require_s2_preflight
  ab_log "generating platform=$PLATFORM tier=$(ab_display_tier "$TIER")"
  export PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"
  (cd "$SCRIPT_DIR" && "$PYTHON_BIN" "./$CASE_GENERATOR" "$PLATFORM" "$TIER")
  printf '%s\n' "$TIER" > "$OUTPUT_DIR/.agent-benchmark-runtime-tier"
}

ab_up() {
  TIER="$(ab_canonical_tier "$TIER")"
  ab_require_tier "$TIER"
  ab_require_s2_preflight
  if [ ! -f "$OUTPUT_DIR/docker-compose.yml" ] || [ "$(cat "$OUTPUT_DIR/.agent-benchmark-runtime-tier" 2>/dev/null || true)" != "$TIER" ]; then
    ab_generate
  fi
  ab_log "starting compose project $PROJECT_NAME"
  (cd "$OUTPUT_DIR" && ab_compose up -d --build)
  ab_log "waiting for routing and services"
  sleep "$(ab_runtime_wait_seconds "$TIER")"
}

ab_down() {
  if [ -f "$OUTPUT_DIR/docker-compose.yml" ]; then
    ab_log "stopping compose project $PROJECT_NAME"
    (cd "$OUTPUT_DIR" && ab_compose down)
  fi
}

ab_normal_check() {
  mkdir -p "$ARTIFACT_DIR"
  ab_assert_live_scale
  if declare -F case_normal_check >/dev/null 2>&1; then
    case_normal_check
  else
    echo "case_normal_check is not implemented for $CASE_ID" >&2
    return 2
  fi
}

ab_inject_fault() {
  mkdir -p "$ARTIFACT_DIR"
  if declare -F case_inject_fault >/dev/null 2>&1; then
    case_inject_fault
  else
    echo "case_inject_fault is not implemented for $CASE_ID" >&2
    return 2
  fi
}

ab_fault_check() {
  mkdir -p "$ARTIFACT_DIR"
  ab_assert_live_scale
  if declare -F case_fault_check >/dev/null 2>&1; then
    case_fault_check
  else
    echo "case_fault_check is not implemented for $CASE_ID" >&2
    return 2
  fi
}

ab_recovery_check() {
  mkdir -p "$ARTIFACT_DIR"
  ab_assert_live_scale
  if declare -F case_recovery_check >/dev/null 2>&1; then
    case_recovery_check
  else
    echo "case_recovery_check is not implemented for $CASE_ID" >&2
    return 2
  fi
}

ab_collect() {
  mkdir -p "$ARTIFACT_DIR"
  ab_log "collecting artifacts into $ARTIFACT_DIR"
  ab_collect_host_diagnostics "$ARTIFACT_DIR/host"
  if declare -F case_collect >/dev/null 2>&1; then
    case_collect || true
  fi
}

ab_safe_token() {
  case "${1:-}" in
    *[!A-Za-z0-9_.-]*|"") return 1 ;;
    *) return 0 ;;
  esac
}

ab_exercise_id() {
  local var="${CASE_ID^^}_EXERCISE_ID"
  local id="${!var:-${AGENT_BENCH_EXERCISE_ID:-current}}"
  if ! ab_safe_token "$id"; then
    echo "${var} must use only letters, digits, dot, underscore, or dash" >&2
    return 2
  fi
  printf '%s\n' "$id"
}

ab_exercise_dir() {
  printf '%s/exercise/%s\n' "$ARTIFACT_DIR" "$(ab_exercise_id)"
}

ab_exercise_stamp() {
  printf '%s_%s\n' "$(date -u +%Y%m%dT%H%M%SZ)" "$$"
}

ab_exercise_event() {
  local root
  root="$(ab_exercise_dir)"
  mkdir -p "$root"
  printf '%s\t%s\t%s\n' "$(date -Is)" "$1" "${2:-}" >> "$root/events.tsv"
}

ab_exercise_phase_allowed() {
  case "$1" in
    baseline|impact|user-frontline|frontline|provider-ops-triage|provider-ops|control-plane-change-audit|change-audit|mitigation|recovery-verification|postmortem)
      return 0 ;;
    *) return 1 ;;
  esac
}

ab_exercise_role_allowed() {
  case "$1" in
    public-users|frontline|provider-ops|network-ops|service-ops|control-plane|route-collectors|resolvers|botnet|customer|change-audit|all-roles)
      return 0 ;;
    *) return 1 ;;
  esac
}

ab_exercise_init() {
  local root
  root="$(ab_exercise_dir)"
  mkdir -p "$root/observations" "$root/actions" "$root/gates"
  {
    printf 'exercise_id=%s\n' "$(ab_exercise_id)"
    printf 'case_id=%s\n' "$CASE_ID"
    printf 'tier=%s\n' "$(ab_display_tier "$TIER")"
    printf 'project=%s\n' "$PROJECT_NAME"
    printf 'status=initialized\n'
    printf 'phase=not_started\n'
    printf 'created_at=%s\n' "$(date -Is)"
  } > "$root/state.env"
  ab_exercise_event "init" "project=$PROJECT_NAME tier=$(ab_display_tier "$TIER")"
  cat > "$root/README.txt" <<EOF
Interactive incident exercise workspace for $CASE_ID.

Use exercise-phase-runtime, exercise-observe-runtime, exercise-note-runtime,
exercise-gate-runtime, and exercise-action-runtime to record a staged
investigation. This ledger is part of the runtime acceptance surface; it is not
a static pass/fail summary.
EOF
  ab_log "exercise initialized at $root"
}

ab_exercise_phase() {
  local phase="${1:-}"
  local root
  if ! ab_safe_token "$phase" || ! ab_exercise_phase_allowed "$phase"; then
    echo "usage: $0 exercise-phase-runtime [TIER] PHASE" >&2
    return 2
  fi
  root="$(ab_exercise_dir)"
  mkdir -p "$root"
  if [ -f "$root/state.env" ]; then
    grep -v '^phase=' "$root/state.env" > "$root/state.env.tmp" || true
    mv "$root/state.env.tmp" "$root/state.env"
  fi
  printf 'phase=%s\n' "$phase" >> "$root/state.env"
  ab_exercise_event "phase" "$phase"
  ab_log "exercise phase set to $phase"
}

ab_exercise_note() {
  local role="${1:-}"
  local root
  shift || true
  if ! ab_safe_token "$role" || [ "$#" -eq 0 ]; then
    echo "usage: $0 exercise-note-runtime [TIER] ROLE TEXT..." >&2
    return 2
  fi
  root="$(ab_exercise_dir)"
  mkdir -p "$root"
  printf '%s\t%s\t%s\n' "$(date -Is)" "$role" "$*" >> "$root/notes.tsv"
  ab_exercise_event "note" "role=$role"
  ab_log "exercise note recorded for $role"
}

ab_exercise_status() {
  local root
  root="$(ab_exercise_dir)"
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

ab_exercise_observe() {
  local role="${1:-}"
  local root obsdir stamp nested
  if ! ab_safe_token "$role" || ! ab_exercise_role_allowed "$role"; then
    echo "usage: $0 exercise-observe-runtime [TIER] ROLE" >&2
    return 2
  fi
  ab_assert_live_scale
  root="$(ab_exercise_dir)"
  stamp="$(ab_exercise_stamp)"
  obsdir="$root/observations/${stamp}_${role}"
  mkdir -p "$obsdir"
  {
    printf 'timestamp=%s\n' "$(date -Is)"
    printf 'exercise_id=%s\n' "$(ab_exercise_id)"
    printf 'case_id=%s\n' "$CASE_ID"
    printf 'role=%s\n' "$role"
    printf 'tier=%s\n' "$(ab_display_tier "$TIER")"
    printf 'project=%s\n' "$PROJECT_NAME"
  } > "$obsdir/context.txt"
  if [ "$role" = "all-roles" ]; then
    for nested in public-users provider-ops network-ops service-ops control-plane change-audit; do
      case_exercise_observe_one "$nested" "$obsdir/$nested" || true
    done
  elif [ "$role" = "frontline" ]; then
    for nested in public-users provider-ops route-collectors resolvers; do
      case_exercise_observe_one "$nested" "$obsdir/$nested" || true
    done
  else
    case_exercise_observe_one "$role" "$obsdir"
  fi
  ab_exercise_event "observe" "role=$role dir=$obsdir"
  ab_log "exercise observation collected for $role into $obsdir"
}

ab_exercise_observation_count() {
  local root="$1"
  local role="$2"
  find "$root/observations" -type d \( -name "*_$role" -o -name "$role" \) 2>/dev/null | wc -l | tr -d ' '
}

ab_exercise_success_action_count() {
  local root="$1"
  local action="$2"
  local count dir
  count=0
  while IFS= read -r dir; do
    [ -f "$dir/result.env" ] || continue
    if grep -q '^result_code=0$' "$dir/result.env"; then
      count=$((count + 1))
    fi
  done < <(find "$root/actions" -maxdepth 1 -type d -name "*_$action" 2>/dev/null)
  printf '%s\n' "$count"
}

ab_exercise_gate_require_observation() {
  local root="$1" role="$2" report="$3" count
  count="$(ab_exercise_observation_count "$root" "$role")"
  if [ "$count" -gt 0 ]; then
    printf 'ok observation role=%s count=%s\n' "$role" "$count" >> "$report"
    return 0
  fi
  printf 'missing observation role=%s\n' "$role" >> "$report"
  return 1
}

ab_exercise_gate_require_action() {
  local root="$1" action="$2" report="$3" count
  count="$(ab_exercise_success_action_count "$root" "$action")"
  if [ "$count" -gt 0 ]; then
    printf 'ok action action=%s success_count=%s\n' "$action" "$count" >> "$report"
    return 0
  fi
  printf 'missing successful action action=%s\n' "$action" >> "$report"
  return 1
}

ab_exercise_gate_require_notes() {
  local root="$1" report="$2"
  if [ -s "$root/notes.tsv" ]; then
    printf 'ok notes file=%s\n' "$root/notes.tsv" >> "$report"
    return 0
  fi
  printf 'missing operator notes file=%s\n' "$root/notes.tsv" >> "$report"
  return 1
}

ab_exercise_gate() {
  local phase="${1:-}"
  local root report rc
  if ! ab_safe_token "$phase" || ! ab_exercise_phase_allowed "$phase"; then
    echo "usage: $0 exercise-gate-runtime [TIER] PHASE" >&2
    return 2
  fi
  root="$(ab_exercise_dir)"
  mkdir -p "$root/gates"
  report="$root/gates/$(ab_exercise_stamp)_$phase.txt"
  rc=0
  {
    printf 'timestamp=%s\n' "$(date -Is)"
    printf 'exercise_id=%s\n' "$(ab_exercise_id)"
    printf 'case_id=%s\n' "$CASE_ID"
    printf 'phase=%s\n' "$phase"
    printf 'tier=%s\n' "$(ab_display_tier "$TIER")"
    printf 'project=%s\n\n' "$PROJECT_NAME"
  } > "$report"
  case "$phase" in
    baseline)
      ab_exercise_gate_require_observation "$root" public-users "$report" || rc=1
      ab_exercise_gate_require_observation "$root" provider-ops "$report" || rc=1
      ;;
    impact|user-frontline|frontline)
      ab_exercise_gate_require_observation "$root" public-users "$report" || rc=1
      ab_exercise_gate_require_notes "$root" "$report" || rc=1
      ;;
    provider-ops-triage|provider-ops)
      ab_exercise_gate_require_observation "$root" public-users "$report" || rc=1
      ab_exercise_gate_require_observation "$root" provider-ops "$report" || rc=1
      ab_exercise_gate_require_observation "$root" network-ops "$report" || rc=1
      ab_exercise_gate_require_notes "$root" "$report" || rc=1
      ;;
    control-plane-change-audit|change-audit)
      ab_exercise_gate_require_observation "$root" control-plane "$report" || rc=1
      ab_exercise_gate_require_observation "$root" change-audit "$report" || rc=1
      ab_exercise_gate_require_notes "$root" "$report" || rc=1
      ;;
    mitigation)
      ab_exercise_gate_require_action "$root" mitigate "$report" || rc=1
      ab_exercise_gate_require_notes "$root" "$report" || rc=1
      ;;
    recovery-verification)
      ab_exercise_gate_require_action "$root" validate-recovery "$report" || rc=1
      ab_exercise_gate_require_observation "$root" public-users "$report" || rc=1
      ;;
    postmortem)
      ab_exercise_gate_require_notes "$root" "$report" || rc=1
      ab_exercise_gate_require_action "$root" validate-recovery "$report" || rc=1
      ;;
  esac
  if [ "$rc" -eq 0 ]; then
    echo "gate=passed" >> "$report"
    ab_exercise_event "gate" "phase=$phase result=passed report=$report"
  else
    echo "gate=failed" >> "$report"
    ab_exercise_event "gate" "phase=$phase result=failed report=$report"
  fi
  cat "$report"
  return "$rc"
}

ab_forbidden_action() {
  case "$1" in
    kill-dns|stop-dns|delete-zone|client-hosts-bypass|edit-oracle|edit-scorer|force-announce|force-announce-unhealthy-prefix|global-reset|kill-origin|restart-all-services|skip-canary|clear-client-cache-as-fix)
      return 0 ;;
    *) return 1 ;;
  esac
}

ab_exercise_action_known() {
  case "$1" in
    inject-fault|mitigate|validate-recovery|recover|rollback|apply-filter|withdraw-leak|activate-scrubber|activate-secondary|freeze-distribution|rollback-known-good|halt-automation|restore-control-plane)
      return 0 ;;
    *)
      ab_forbidden_action "$1"
      ;;
  esac
}

ab_exercise_action() {
  local action="${1:-}"
  local root action_dir stamp rc
  if ! ab_safe_token "$action" || ! ab_exercise_action_known "$action"; then
    echo "unknown exercise action: $action" >&2
    return 2
  fi
  root="$(ab_exercise_dir)"
  mkdir -p "$root/actions"
  stamp="$(ab_exercise_stamp)"
  action_dir="$root/actions/${stamp}_${action}"
  mkdir -p "$action_dir"
  {
    printf 'timestamp=%s\n' "$(date -Is)"
    printf 'case_id=%s\n' "$CASE_ID"
    printf 'action=%s\n' "$action"
    printf 'tier=%s\n' "$(ab_display_tier "$TIER")"
    printf 'project=%s\n' "$PROJECT_NAME"
  } > "$action_dir/context.env"
  if ab_forbidden_action "$action"; then
    {
      echo "result_code=3"
      echo "result=policy_denied"
      echo "reason=forbidden shortcut action"
    } > "$action_dir/result.env"
    echo "policy denied action=$action" > "$action_dir/output.txt"
    ab_exercise_event "action" "action=$action result=policy_denied dir=$action_dir"
    cat "$action_dir/output.txt" >&2
    return 3
  fi
  rc=0
  if declare -F case_exercise_action >/dev/null 2>&1; then
    case_exercise_action "$action" > "$action_dir/output.txt" 2>&1 || rc=$?
  else
    echo "case_exercise_action is not implemented for $CASE_ID" > "$action_dir/output.txt"
    rc=2
  fi
  {
    printf 'result_code=%s\n' "$rc"
    if [ "$rc" -eq 0 ]; then
      echo "result=success"
    else
      echo "result=failed"
    fi
  } > "$action_dir/result.env"
  ab_exercise_event "action" "action=$action result_code=$rc dir=$action_dir"
  cat "$action_dir/output.txt"
  return "$rc"
}

ab_runtime_command() {
  local fn="$1"
  shift || true
  if [ "$#" -gt 0 ] && ab_require_tier "$1" >/dev/null 2>&1; then
    TIER="$(ab_canonical_tier "$1")"
    shift
  else
    TIER="$(ab_canonical_tier "$TIER")"
  fi
  ARTIFACT_DIR="$SCRIPT_DIR/test_log/runtime/$TIER"
  "$fn" "$@"
}

ab_smoke() {
  local rc
  trap 'rc=$?; ab_collect || true; ab_down || true; exit "$rc"' EXIT
  ab_generate
  ab_up
  ab_normal_check
  ab_exercise_init

  ab_exercise_phase baseline
  ab_exercise_observe public-users
  ab_exercise_observe provider-ops
  ab_exercise_note operator "baseline: public users and provider operations recorded normal pre-incident evidence"
  ab_exercise_gate baseline

  ab_exercise_action inject-fault
  ab_fault_check

  ab_exercise_phase impact
  ab_exercise_observe public-users
  ab_exercise_note frontline "impact: external users now report degraded service while the exercise has not used privileged root-cause knowledge"
  ab_exercise_gate impact

  ab_exercise_phase user-frontline
  ab_exercise_observe frontline
  ab_exercise_note frontline "frontline: compare user symptoms against provider-owned health and routing/control-plane observations"
  ab_exercise_gate user-frontline

  ab_exercise_phase provider-ops-triage
  ab_exercise_observe public-users
  ab_exercise_observe provider-ops
  ab_exercise_observe network-ops
  ab_exercise_note provider-ops "triage: service-owner and network views narrow the incident without changing clients, oracles, or root services"
  ab_exercise_gate provider-ops-triage

  ab_exercise_phase control-plane-change-audit
  ab_exercise_observe control-plane
  ab_exercise_observe change-audit
  ab_exercise_note control-plane "change-audit: the next allowed action must address the simulated control-plane or policy fault, not shortcut user-visible symptoms"
  ab_exercise_gate control-plane-change-audit

  ab_exercise_phase mitigation
  ab_exercise_action mitigate
  ab_exercise_note operator "mitigation: applied the case-defined constrained recovery action after staged evidence gates passed"
  ab_exercise_gate mitigation

  ab_exercise_phase recovery-verification
  ab_exercise_action validate-recovery
  ab_exercise_observe public-users
  ab_exercise_observe provider-ops
  ab_exercise_observe network-ops
  ab_exercise_note operator "recovery-verification: external users, provider views, and control-plane evidence were rechecked after mitigation"
  ab_exercise_gate recovery-verification

  ab_exercise_phase postmortem
  ab_exercise_note operator "postmortem: live sequence completed baseline, impact, triage, change audit, mitigation, and recovery verification"
  ab_exercise_gate postmortem

  ab_collect
  trap - EXIT
  ab_down
}

ab_main() {
  local cmd="${1:-}"
  shift || true
  case "$cmd" in
    generate|generate-runtime) ab_runtime_command ab_generate "$@" ;;
    up|up-runtime) ab_runtime_command ab_up "$@" ;;
    down|down-runtime) ab_runtime_command ab_down "$@" ;;
    normal|normal-check|normal-runtime|normal-check-runtime) ab_runtime_command ab_normal_check "$@" ;;
    inject-fault|inject-fault-runtime) ab_runtime_command ab_inject_fault "$@" ;;
    fault|fault-check|fault-runtime|fault-check-runtime) ab_runtime_command ab_fault_check "$@" ;;
    recovery|recover|recovery-runtime|recovery-check|recovery-check-runtime) ab_runtime_command ab_recovery_check "$@" ;;
    collect|collect-runtime) ab_runtime_command ab_collect "$@" ;;
    exercise-init|exercise-init-runtime) ab_runtime_command ab_exercise_init "$@" ;;
    exercise-phase|exercise-phase-runtime) ab_runtime_command ab_exercise_phase "$@" ;;
    exercise-note|exercise-note-runtime) ab_runtime_command ab_exercise_note "$@" ;;
    exercise-status|exercise-status-runtime) ab_runtime_command ab_exercise_status "$@" ;;
    exercise-observe|exercise-observe-runtime) ab_runtime_command ab_exercise_observe "$@" ;;
    exercise-gate|exercise-gate-runtime) ab_runtime_command ab_exercise_gate "$@" ;;
    exercise-action|exercise-action-runtime) ab_runtime_command ab_exercise_action "$@" ;;
    smoke|runtime-smoke) ab_runtime_command ab_smoke "$@" ;;
    s2-preflight) ab_s2_preflight ;;
    *)
      echo "Usage: $0 {generate-runtime|up-runtime|normal-runtime|inject-fault-runtime|fault-runtime|exercise-init-runtime|exercise-phase-runtime|exercise-observe-runtime|exercise-note-runtime|exercise-gate-runtime|exercise-action-runtime|recovery-runtime|collect-runtime|down-runtime|s2-preflight} [S0|S1|S1.5|S2]" >&2
      return 2
      ;;
  esac
}
