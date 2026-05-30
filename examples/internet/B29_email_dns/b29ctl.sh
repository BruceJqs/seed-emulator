#!/usr/bin/env bash
# Unified controller for B29 Email (DNS-first) example
# Usage:
#   bash b29ctl.sh start [--platform arm|amd]
#   bash b29ctl.sh stop
#   bash b29ctl.sh status
#   bash b29ctl.sh test [--all] [--pairs file]
#   bash b29ctl.sh generate [--platform arm|amd]
#   bash b29ctl.sh doctor
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/output"
PLATFORM="auto" # default; override with --platform amd|arm; 'auto' uses uname
PYTHON_BIN="${SEED_PYTHON:-}"
ARGS=()

COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-${SEED_B29_PROJECT_NAME:-b29}}"
SEED_B29_NETWORK_PREFIX="${SEED_B29_NETWORK_PREFIX:-$COMPOSE_PROJECT_NAME}"
export COMPOSE_PROJECT_NAME
export SEED_B29_NETWORK_PREFIX

if [ -z "$PYTHON_BIN" ]; then
  if [ -x "$ROOT_DIR/.venv/bin/python3" ]; then
    PYTHON_BIN="$ROOT_DIR/.venv/bin/python3"
  elif [ -x "$ROOT_DIR/.venv-seed/bin/python3" ]; then
    PYTHON_BIN="$ROOT_DIR/.venv-seed/bin/python3"
  else
    PYTHON_BIN="python3"
  fi
fi

log() { echo -e "[b29ctl] $*"; }
warn() { echo -e "[b29ctl] WARN: $*" >&2; }

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    echo "docker compose/docker-compose not found" >&2
    return 1
  fi
}

have_compose() {
  if docker compose version >/dev/null 2>&1 || command -v docker-compose >/dev/null 2>&1; then
    return 0
  fi
  echo "docker compose/docker-compose not found" >&2
  return 1
}

b29_doctor() {
  echo "--- B29 host checks ---"
  have_compose || return 1

  local rc=0
  if command -v sysctl >/dev/null 2>&1; then
    local br_nf br_nf6
    br_nf="$(sysctl -n net.bridge.bridge-nf-call-iptables 2>/dev/null || echo unknown)"
    br_nf6="$(sysctl -n net.bridge.bridge-nf-call-ip6tables 2>/dev/null || echo unknown)"
    echo "net.bridge.bridge-nf-call-iptables=$br_nf"
    echo "net.bridge.bridge-nf-call-ip6tables=$br_nf6"
    if [ "$br_nf" != "0" ] || [ "$br_nf6" != "0" ]; then
      warn "WSL/Docker bridge netfilter can block SEED multi-bridge forwarding."
      warn "Run: sudo sysctl -w net.bridge.bridge-nf-call-iptables=0 net.bridge.bridge-nf-call-ip6tables=0"
      rc=1
    fi
  else
    warn "sysctl not found; skip bridge netfilter check"
  fi

  if ! docker info >/dev/null 2>&1; then
    warn "Docker daemon is not reachable"
    rc=1
  fi

  return "$rc"
}

b29_generate() {
  log "Generating emulation (platform=$PLATFORM) ..."
  export PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"
  "$PYTHON_BIN" "$SCRIPT_DIR/email_realistic.py" "$PLATFORM"
  log "Generation complete: $OUTPUT_DIR"
}

b29_up() {
  have_compose || { echo "Please install docker-compose"; exit 1; }
  b29_doctor || warn "Continuing anyway; cross-AS DNS/mail may fail until the host check is fixed."
  if [ ! -f "$OUTPUT_DIR/docker-compose.yml" ]; then
    b29_generate
  fi
  log "Starting network (project=$COMPOSE_PROJECT_NAME, compose up -d) ..."
  (cd "$OUTPUT_DIR" && compose up -d)
  log "Provisioning Roundcube accounts ..."
  "$SCRIPT_DIR/manage_roundcube.sh" accounts || true
  log "Starting Roundcube ..."
  if "$SCRIPT_DIR/manage_roundcube.sh" start; then
    log "Done. Map: http://localhost:18080/pro/home  Roundcube: http://localhost:8082"
  else
    warn "Roundcube did not start. The B29 mail/DNS network is still running."
    warn "Retry later with: bash manage_roundcube.sh start"
    log "Done. Map: http://localhost:18080/pro/home  Roundcube: pending"
  fi
}

b29_down() {
  have_compose || { echo "Please install docker-compose"; exit 1; }
  log "Stopping Roundcube ..."
  "$SCRIPT_DIR/manage_roundcube.sh" stop || true
  if [ -f "$OUTPUT_DIR/docker-compose.yml" ]; then
    log "Stopping network (project=$COMPOSE_PROJECT_NAME, compose down) ..."
    (cd "$OUTPUT_DIR" && compose down)
  else
    log "No output/docker-compose.yml; skip network down"
  fi
  log "Stopped."
}

b29_status() {
  have_compose || true
  if [ -f "$OUTPUT_DIR/docker-compose.yml" ]; then
    echo "--- Network status ---"
    (cd "$OUTPUT_DIR" && compose ps || true)
  else
    echo "No output/docker-compose.yml yet"
  fi
  echo "--- Roundcube status ---"
  "$SCRIPT_DIR/manage_roundcube.sh" status || true
}

b29_test() {
  # Proxy to run_cross_tests.sh with given args
  bash "$SCRIPT_DIR/run_cross_tests.sh" "$@"
}

# Parse args
CMD="${1:-start}"; shift || true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --platform) PLATFORM="${2:-arm}"; shift 2;;
    *) ARGS+=("$1"); shift;;
  esac
done

case "$CMD" in
  start|up)
    b29_up
    ;;
  stop|down)
    b29_down
    ;;
  status)
    b29_status
    ;;
  doctor|check)
    b29_doctor
    ;;
  test)
    b29_test "${ARGS[@]}"
    ;;
  generate|gen|build)
    b29_generate
    ;;
  restart)
    b29_down; b29_up
    ;;
  *)
    echo "Usage: bash b29ctl.sh {start|stop|status|test|generate|restart|doctor} [--platform auto|arm|amd]"
    exit 1
    ;;
esac
