#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

from seedemu.compiler import Docker, Platform
from seedemu.core import Emulator
from seedemu.layers import Base, Ebgp, Ibgp, Ospf, PeerRelationship, Routing


CASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = CASE_DIR / "output"
CONTAINER_PREFIX = os.environ.get("B57_CONTAINER_PREFIX", "b57-")

SERVICE_IP = "10.57.10.80"
SERVICE_PREFIX = "10.57.10.0/24"
FRONTEND_ASN = 57
CONTROL_ASN = 58
WORKLOAD_ASN = 59
TRANSIT_ASN = 50

REGION_FRONTENDS = [
    ("us-east1", "10.57.10.11", "US East 1 Frontend"),
    ("us-east4", "10.57.10.12", "US East 4 Frontend"),
    ("us-central1", "10.57.10.13", "US Central 1 Frontend"),
    ("us-west1", "10.57.10.14", "US West 1 Frontend"),
    ("us-west2", "10.57.10.15", "US West 2 Frontend"),
    ("eu-west1", "10.57.10.16", "EU West 1 Frontend"),
    ("asia-east1", "10.57.10.17", "Asia East 1 Frontend"),
    ("canary", "10.57.10.18", "Canary Region Frontend"),
]

CONTROL_COMPONENTS = [
    ("maintenance-automation", "10.58.10.11", "Maintenance Automation"),
    ("cluster-manager-loc-a", "10.58.10.12", "Cluster Manager Loc A"),
    ("cluster-manager-loc-b", "10.58.10.13", "Cluster Manager Loc B"),
    ("cluster-manager-loc-c", "10.58.10.14", "Cluster Manager Loc C"),
    ("network-control-plane-a", "10.58.10.21", "Network Control Plane A"),
    ("network-control-plane-b", "10.58.10.22", "Network Control Plane B"),
    ("network-control-plane-c", "10.58.10.23", "Network Control Plane C"),
    ("config-store", "10.58.10.31", "Config Store"),
    ("route-distributor", "10.58.10.32", "Route Distributor"),
    ("te-controller", "10.58.10.33", "TE Controller"),
    ("ops-tooling", "10.58.10.34", "Ops Tooling"),
]

WORKLOADS = [
    ("gce-api", "10.59.10.80", "GCE API Workload"),
    ("cloud-storage", "10.59.10.81", "Cloud Storage Workload"),
    ("app-engine", "10.59.10.82", "App Engine Workload"),
    ("vpn-endpoint", "10.59.10.83", "Cloud VPN Endpoint"),
    ("console", "10.59.10.84", "Cloud Console Workload"),
    ("customer-project", "10.59.10.85", "Customer Project Workload"),
]


def asn_range(start: int, stop: int, *, skip=(100,), fill_to: int | None = None, fill_start: int | None = None):
    asns = [asn for asn in range(start, stop) if asn not in skip]
    if fill_to is not None:
        next_asn = fill_start if fill_start is not None else stop
        while len(asns) < fill_to:
            if next_asn not in skip:
                asns.append(next_asn)
            next_asn += 1
    return asns


TIERS = {
    "S0": {"clients": list(range(80, 84)), "ops": [120], "noise": []},
    "S1": {
        "clients": asn_range(80, 140, fill_to=60, fill_start=250),
        "ops": list(range(140, 152)),
        "noise": list(range(152, 210)) + [251, 252, 253, 254, 255, 256],
    },
    "S1_5": {
        "clients": asn_range(80, 155, fill_to=75, fill_start=250),
        "ops": list(range(155, 175)),
        "noise": list(range(175, 240)) + [251, 252, 253, 254],
    },
    "S2": {
        "clients": asn_range(80, 180, fill_to=100, fill_start=250),
        "ops": list(range(180, 220)),
        "noise": list(range(220, 250)) + list(range(260, 288)),
    },
}


EDGE_FRONTEND_SCRIPT = """\
#!/usr/bin/env python3
import http.server
import pathlib
import sys
import time

STATE_DIR = pathlib.Path("/var/lib/b57")
STATE_FILE = STATE_DIR / "edge_frontend.env"
LAST_REQUEST = STATE_DIR / "last_request.txt"
LOG = pathlib.Path("/var/log/b57-edge-frontend.log")


def log(message):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as stream:
        stream.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {message}\\n")


def state_for(phase):
    if phase == "normal":
        return {
            "case_id": "b57",
            "incident_phase": "normal",
            "http_code": "200",
            "frontend_mode": "serving",
            "workload_health": "healthy",
            "maintenance_automation": "idle",
            "cluster_managers": "scheduled",
            "network_control_plane": "running",
            "config_store": "consistent",
            "route_distributor": "stable",
            "te_controller": "balanced",
            "bgp_state": "stable",
            "retry_traffic": "normal",
            "packet_loss_matrix": "low",
        }
    if phase == "fault":
        return {
            "case_id": "b57",
            "incident_phase": "fault",
            "http_code": "200",
            "frontend_mode": "locally_alive_but_external_route_withdrawn",
            "workload_health": "healthy",
            "maintenance_automation": "unsafe_global_deschedule",
            "cluster_managers": "missing_control_plane_jobs",
            "network_control_plane": "down",
            "config_store": "stale",
            "route_distributor": "fail_static_expired",
            "te_controller": "congested",
            "bgp_state": "withdrawn_or_degraded",
            "retry_traffic": "amplified",
            "packet_loss_matrix": "east_central_high",
            "root_cause": "maintenance_automation_descheduled_network_control_plane",
        }
    if phase == "recovery":
        return {
            "case_id": "b57",
            "incident_phase": "recovery",
            "http_code": "200",
            "frontend_mode": "serving",
            "workload_health": "healthy",
            "maintenance_automation": "halted",
            "cluster_managers": "rescheduled",
            "network_control_plane": "running",
            "config_store": "rebuild_passed",
            "route_distributor": "distributed",
            "te_controller": "balanced",
            "bgp_state": "stable",
            "retry_traffic": "noncritical_dropped_then_normal",
            "packet_loss_matrix": "low",
            "region_verification": "passed",
            "recovery_complete": "yes",
            "canary_passed": "yes",
        }
    raise SystemExit(f"unknown phase {phase}")


def write_state(phase):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    values = state_for(phase)
    STATE_FILE.write_text("".join(f"{key}={value}\\n" for key, value in values.items()))
    log(f"phase={phase} ncp={values['network_control_plane']} bgp={values['bgp_state']} te={values['te_controller']}")


def read_state():
    if not STATE_FILE.exists():
        write_state("normal")
    values = {}
    for line in STATE_FILE.read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def evaluate():
    values = read_state()
    body = (
        "GOOGLE_EDGE_FRONTEND_ALIVE "
        f"phase={values['incident_phase']} ncp={values['network_control_plane']} "
        f"bgp={values['bgp_state']} te={values['te_controller']} workload={values['workload_health']}\\n"
    )
    LAST_REQUEST.write_text(
        f"request_id={time.time_ns()}\\n"
        f"http_code=200\\n"
        f"incident_phase={values['incident_phase']}\\n"
        f"frontend_mode={values['frontend_mode']}\\n"
        f"{body}"
    )
    return body.encode()


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = evaluate()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"
if cmd in ("normal", "fault", "recovery"):
    write_state(cmd)
elif cmd == "status":
    if not STATE_FILE.exists():
        write_state("normal")
    print("== edge_frontend_state ==")
    sys.stdout.write(STATE_FILE.read_text())
    if LAST_REQUEST.exists():
        print("\\n== last_request ==")
        sys.stdout.write(LAST_REQUEST.read_text())
    if LOG.exists():
        print("\\n== frontend_log ==")
        sys.stdout.write(LOG.read_text())
elif cmd == "serve":
    write_state("normal")
    http.server.ThreadingHTTPServer(("0.0.0.0", 80), Handler).serve_forever()
else:
    raise SystemExit("usage: b57-edge-frontend.sh normal|fault|recovery|status|serve")
"""


ROUTE_CONTROL_SCRIPT = """\
#!/bin/sh
set -eu
PEER="u_as50"
SERVICE_PREFIX="__SERVICE_PREFIX__"
LOG=/var/log/b57-route-control.log
STATE=/var/lib/b57/route_control.env
mkdir -p /var/lib/b57

write_log() {
    printf "%s %s\\n" "$(date -Is)" "$1" >> "$LOG"
}

wait_bird() {
    while ! birdc show status >/dev/null 2>&1; do
        sleep 1
    done
}

write_state() {
    phase="$1"
    case "$phase" in
        normal)
            cat > "$STATE" <<EOF
case_id=b57
incident_phase=normal
bgp_state=stable
external_route=$SERVICE_PREFIX visible
fail_static_timer=not_triggered
packet_loss_matrix=low
EOF
            ;;
        fault)
            cat > "$STATE" <<EOF
case_id=b57
incident_phase=fault
bgp_state=withdrawn_or_degraded
external_route=$SERVICE_PREFIX withdrawn
fail_static_timer=expired
packet_loss_matrix=east_central_high
root_cause=maintenance_automation_descheduled_network_control_plane
EOF
            ;;
        recovery)
            cat > "$STATE" <<EOF
case_id=b57
incident_phase=recovery
bgp_state=stable
external_route=$SERVICE_PREFIX visible
fail_static_timer=restored
packet_loss_matrix=low
region_verification=passed
recovery_complete=yes
canary_passed=yes
EOF
            ;;
    esac
}

case "${1:-}" in
    normal)
        wait_bird
        birdc en "$PEER" >/tmp/b57-route-control.log 2>&1 || true
        write_state normal
        write_log "normal: edge transit BGP peer $PEER enabled; service prefix visible"
        ;;
    fault)
        wait_bird
        birdc dis "$PEER" >/tmp/b57-route-control.log 2>&1 || true
        write_state fault
        write_log "fault: disabled edge transit BGP peer $PEER after fail-static expiration"
        ;;
    recovery)
        wait_bird
        birdc en "$PEER" >/tmp/b57-route-control.log 2>&1 || true
        write_state recovery
        write_log "recovery: re-enabled edge transit BGP peer $PEER after control-plane rebuild"
        ;;
    status)
        cat "$STATE" 2>/dev/null || true
        printf '\\n== peer ==\\n'
        birdc show protocols "$PEER" 2>&1 || true
        printf '\\n== service route ==\\n'
        birdc show route "$SERVICE_PREFIX" all 2>&1 || true
        printf '\\n== log ==\\n'
        cat "$LOG" 2>/dev/null || true
        ;;
    *)
        echo "usage: $0 normal|fault|recovery|status" >&2
        exit 2
        ;;
esac
""".replace("__SERVICE_PREFIX__", SERVICE_PREFIX)


REGION_FRONTEND_SCRIPT = """\
#!/usr/bin/env python3
import http.server
import pathlib
import sys
import time

REGION = "__REGION__"
STATE = pathlib.Path("/var/run/b57-region-frontend.env")
LOG = pathlib.Path(f"/var/log/b57-region-{REGION}.log")


def log(message):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as stream:
        stream.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} region={REGION} {message}\\n")


def state_for(phase):
    if phase == "normal":
        return {
            "region": REGION,
            "incident_phase": "normal",
            "region_frontend": "serving",
            "packet_loss": "low",
            "api_5xx": "low",
            "retry_traffic": "normal",
        }
    if phase == "fault":
        return {
            "region": REGION,
            "incident_phase": "fault",
            "region_frontend": "locally_alive",
            "packet_loss": "high_on_us_backbone",
            "api_5xx": "elevated_from_network_loss",
            "retry_traffic": "amplified",
            "root_cause": "maintenance_automation_descheduled_network_control_plane",
        }
    if phase == "recovery":
        return {
            "region": REGION,
            "incident_phase": "recovery",
            "region_frontend": "serving",
            "packet_loss": "low",
            "api_5xx": "low",
            "retry_traffic": "normal",
            "region_verification": "passed",
            "canary_passed": "yes",
        }
    raise SystemExit(f"unknown phase {phase}")


def write_state(phase):
    values = state_for(phase)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text("".join(f"{key}={value}\\n" for key, value in values.items()))
    log(f"phase={phase} region_frontend={values['region_frontend']} packet_loss={values['packet_loss']}")


def read_state():
    if not STATE.exists():
        write_state("normal")
    return STATE.read_text()


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = read_state().encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"
if cmd in ("normal", "fault", "recovery"):
    write_state(cmd)
elif cmd == "status":
    sys.stdout.write(read_state())
    if LOG.exists():
        print("\\n== region_log ==")
        sys.stdout.write(LOG.read_text())
elif cmd == "serve":
    write_state("normal")
    http.server.ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
else:
    raise SystemExit("usage: b57-region-frontend.sh normal|fault|recovery|status|serve")
"""


CONTROL_COMPONENT_SCRIPT = """\
#!/usr/bin/env python3
import http.server
import pathlib
import sys
import time

ROLE = "__ROLE__"
STATE = pathlib.Path(f"/var/run/b57-{ROLE}.env")
LOG = pathlib.Path(f"/var/log/b57-{ROLE}.log")


def log(message):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as stream:
        stream.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} role={ROLE} {message}\\n")


ROLE_STATES = {
    "maintenance-automation": {
        "normal": {"maintenance_automation": "idle", "selector_scope": "single_physical_location", "dry_run": "safe"},
        "fault": {
            "maintenance_automation": "unsafe_global_deschedule",
            "selector_scope": "cross_location_multiple_clusters",
            "bug": "maintenance_event_selector_crossed_location_boundary",
        },
        "recovery": {"maintenance_automation": "halted", "selector_scope": "blocked_pending_fix", "dry_run": "disabled"},
    },
    "cluster-manager-loc-a": {
        "normal": {"cluster_manager": "scheduled", "location": "loc-a", "network_control_plane_jobs": "running"},
        "fault": {"cluster_manager": "descheduled", "location": "loc-a", "network_control_plane_jobs": "missing"},
        "recovery": {"cluster_manager": "rescheduled", "location": "loc-a", "network_control_plane_jobs": "running"},
    },
    "cluster-manager-loc-b": {
        "normal": {"cluster_manager": "scheduled", "location": "loc-b", "network_control_plane_jobs": "running"},
        "fault": {"cluster_manager": "descheduled", "location": "loc-b", "network_control_plane_jobs": "missing"},
        "recovery": {"cluster_manager": "rescheduled", "location": "loc-b", "network_control_plane_jobs": "running"},
    },
    "cluster-manager-loc-c": {
        "normal": {"cluster_manager": "scheduled", "location": "loc-c", "network_control_plane_jobs": "running"},
        "fault": {"cluster_manager": "descheduled", "location": "loc-c", "network_control_plane_jobs": "missing"},
        "recovery": {"cluster_manager": "rescheduled", "location": "loc-c", "network_control_plane_jobs": "running"},
    },
    "network-control-plane-a": {
        "normal": {"network_control_plane": "running", "replica": "a", "config_generation": "current"},
        "fault": {"network_control_plane": "down", "replica": "a", "config_generation": "stopped"},
        "recovery": {"network_control_plane": "running", "replica": "a", "config_generation": "current"},
    },
    "network-control-plane-b": {
        "normal": {"network_control_plane": "running", "replica": "b", "config_generation": "current"},
        "fault": {"network_control_plane": "down", "replica": "b", "config_generation": "stopped"},
        "recovery": {"network_control_plane": "running", "replica": "b", "config_generation": "current"},
    },
    "network-control-plane-c": {
        "normal": {"network_control_plane": "running", "replica": "c", "config_generation": "current"},
        "fault": {"network_control_plane": "down", "replica": "c", "config_generation": "stopped"},
        "recovery": {"network_control_plane": "running", "replica": "c", "config_generation": "current"},
    },
    "config-store": {
        "normal": {"config_store": "consistent", "snapshot_age": "fresh"},
        "fault": {"config_store": "stale", "snapshot_age": "expired_after_fail_static"},
        "recovery": {"config_store": "rebuild_passed", "snapshot_age": "fresh"},
    },
    "route-distributor": {
        "normal": {"route_distributor": "stable", "bgp_state": "stable"},
        "fault": {"route_distributor": "fail_static_expired", "bgp_state": "withdrawn_or_degraded"},
        "recovery": {"route_distributor": "distributed", "bgp_state": "stable"},
    },
    "te-controller": {
        "normal": {"te_controller": "balanced", "noncritical_traffic": "normal", "retry_traffic": "normal"},
        "fault": {"te_controller": "congested", "noncritical_traffic": "competing", "retry_traffic": "amplified"},
        "recovery": {"te_controller": "balanced", "noncritical_traffic": "dropped_then_restored", "retry_traffic": "normal"},
    },
    "ops-tooling": {
        "normal": {"ops_tooling": "fresh", "metrics_delay": "low", "status_comms": "normal"},
        "fault": {"ops_tooling": "delayed_by_congestion", "metrics_delay": "high", "status_comms": "impaired"},
        "recovery": {"ops_tooling": "fresh", "metrics_delay": "low", "status_comms": "normal"},
    },
}


def state_for(phase):
    if phase not in ROLE_STATES[ROLE]:
        raise SystemExit(f"unknown phase {phase}")
    values = {"case_id": "b57", "component": ROLE, "incident_phase": phase}
    values.update(ROLE_STATES[ROLE][phase])
    if phase == "fault":
        values.setdefault("root_cause", "maintenance_automation_descheduled_network_control_plane")
    if phase == "recovery":
        values["recovery_complete"] = "yes"
        values["canary_passed"] = "yes"
    return values


def write_state(phase):
    values = state_for(phase)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text("".join(f"{key}={value}\\n" for key, value in values.items()))
    log(f"phase={phase}")


def read_state():
    if not STATE.exists():
        write_state("normal")
    return STATE.read_text()


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = read_state().encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"
if cmd in ("normal", "fault", "recovery"):
    write_state(cmd)
elif cmd == "status":
    sys.stdout.write(read_state())
    if LOG.exists():
        print("\\n== component_log ==")
        sys.stdout.write(LOG.read_text())
elif cmd == "serve":
    write_state("normal")
    http.server.ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
else:
    raise SystemExit(f"usage: b57-{ROLE}.sh normal|fault|recovery|status|serve")
"""


WORKLOAD_SCRIPT = """\
#!/usr/bin/env python3
import http.server
import pathlib
import sys
import time

WORKLOAD = "__WORKLOAD__"
STATE = pathlib.Path(f"/var/run/b57-workload-{WORKLOAD}.env")
LOG = pathlib.Path(f"/var/log/b57-workload-{WORKLOAD}.log")


def log(message):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as stream:
        stream.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} workload={WORKLOAD} {message}\\n")


def state_for(phase):
    values = {
        "workload": WORKLOAD,
        "incident_phase": phase,
        "http_code": "200",
        "workload_health": "healthy",
        "process_state": "alive",
    }
    if phase == "fault":
        values["user_symptom"] = "timeouts_from_network_path_not_local_process"
    if phase == "recovery":
        values["region_verification"] = "passed"
        values["canary_passed"] = "yes"
    return values


def write_state(phase):
    values = state_for(phase)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text("".join(f"{key}={value}\\n" for key, value in values.items()))
    log(f"phase={phase}")


def read_state():
    if not STATE.exists():
        write_state("normal")
    return STATE.read_text()


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = read_state().encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"
if cmd in ("normal", "fault", "recovery"):
    write_state(cmd)
elif cmd == "status":
    sys.stdout.write(read_state())
    if LOG.exists():
        print("\\n== workload_log ==")
        sys.stdout.write(LOG.read_text())
elif cmd == "serve":
    write_state("normal")
    http.server.ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
else:
    raise SystemExit("usage: b57-workload.sh normal|fault|recovery|status|serve")
"""


def canonical_tier(value: str) -> str:
    upper = value.upper()
    if upper in ("S1.5", "S1_5", "S15"):
        return "S1_5"
    return upper


def parse_args():
    platform = Platform.AMD64
    tier = "S0"
    args = list(sys.argv[1:])
    if args:
        if args[0].lower() in ("amd", "amd64"):
            platform = Platform.AMD64
        elif args[0].lower() in ("arm", "arm64"):
            platform = Platform.ARM64
        else:
            raise SystemExit("usage: google_network_congestion.py [amd|arm] [S0|S1|S1.5|S2]")
        args.pop(0)
    if args:
        tier = canonical_tier(args.pop(0))
    if args or tier not in TIERS:
        raise SystemExit("usage: google_network_congestion.py [amd|arm] [S0|S1|S1.5|S2]")
    return platform, tier


def add_router_as(base: Base, asn: int, prefix: str, router_ip: str, ix_ip: str, display: str):
    asys = base.createAutonomousSystem(asn)
    asys.createNetwork("net0", prefix)
    router = asys.createRouter("router")
    router.joinNetwork("net0", address=router_ip).joinNetwork("ix100", address=ix_ip)
    router.setDisplayName(display)
    router.addSoftware("curl")
    router.addSoftware("netcat-openbsd")
    return asys, router


def add_host(asys, name: str, ip: str, display: str, software: tuple[str, ...] = ("curl", "netcat-openbsd", "python3")):
    host = asys.createHost(name).joinNetwork("net0", address=ip)
    host.setDisplayName(display)
    for package in software:
        host.addSoftware(package)
    return host


def build_case(tier: str):
    cfg = TIERS[tier]
    emu = Emulator()
    base = Base()
    routing = Routing()
    ebgp = Ebgp()
    ibgp = Ibgp()
    ospf = Ospf()

    base.createInternetExchange(100)

    add_router_as(base, TRANSIT_ASN, "10.50.0.0/24", "10.50.0.254", "10.100.0.50", "Transit Router")
    frontend_as, frontend_router = add_router_as(
        base, FRONTEND_ASN, SERVICE_PREFIX, "10.57.10.254", "10.100.0.57", "Google Edge Router"
    )
    control_as, _ = add_router_as(
        base, CONTROL_ASN, "10.58.10.0/24", "10.58.10.254", "10.100.0.58", "Google Network Control Plane Router"
    )
    workload_as, _ = add_router_as(
        base, WORKLOAD_ASN, "10.59.10.0/24", "10.59.10.254", "10.100.0.59", "Google Workload Router"
    )

    frontend_router.addSoftware("python3")
    frontend_router.setFile("/usr/local/bin/b57-edge-frontend.sh", EDGE_FRONTEND_SCRIPT)
    frontend_router.setFile("/usr/local/bin/b57-route-control.sh", ROUTE_CONTROL_SCRIPT)
    frontend_router.appendStartCommand("chmod +x /usr/local/bin/b57-edge-frontend.sh /usr/local/bin/b57-route-control.sh")
    frontend_router.appendStartCommand(f"ip addr add {SERVICE_IP}/32 dev lo || true")
    frontend_router.appendStartCommand("/usr/local/bin/b57-edge-frontend.sh serve", fork=True)
    frontend_router.appendStartCommand("/usr/local/bin/b57-route-control.sh normal", fork=True)

    for region, ip, display in REGION_FRONTENDS:
        node = add_host(frontend_as, f"region-{region}", ip, display)
        node.setFile("/usr/local/bin/b57-region-frontend.sh", REGION_FRONTEND_SCRIPT.replace("__REGION__", region))
        node.appendStartCommand("chmod +x /usr/local/bin/b57-region-frontend.sh")
        node.appendStartCommand("/usr/local/bin/b57-region-frontend.sh serve", fork=True)

    for role, ip, display in CONTROL_COMPONENTS:
        node = add_host(control_as, role, ip, display)
        node.setFile("/usr/local/bin/b57-control-component.sh", CONTROL_COMPONENT_SCRIPT.replace("__ROLE__", role))
        node.appendStartCommand("chmod +x /usr/local/bin/b57-control-component.sh")
        node.appendStartCommand("/usr/local/bin/b57-control-component.sh serve", fork=True)

    for workload, ip, display in WORKLOADS:
        node = add_host(workload_as, workload, ip, display)
        node.setFile("/usr/local/bin/b57-workload.sh", WORKLOAD_SCRIPT.replace("__WORKLOAD__", workload))
        node.appendStartCommand("chmod +x /usr/local/bin/b57-workload.sh")
        node.appendStartCommand("/usr/local/bin/b57-workload.sh serve", fork=True)

    for asn in (FRONTEND_ASN, CONTROL_ASN, WORKLOAD_ASN):
        ebgp.addPrivatePeering(100, TRANSIT_ASN, asn, abRelationship=PeerRelationship.Provider)

    for asn in cfg["clients"]:
        add_router_as(base, asn, f"10.{asn}.0.0/24", f"10.{asn}.0.254", f"10.100.0.{asn}", f"Client Probe Router {asn}")
        ebgp.addPrivatePeering(100, TRANSIT_ASN, asn, abRelationship=PeerRelationship.Provider)

    for asn in cfg["ops"]:
        add_router_as(base, asn, f"10.{asn}.0.0/24", f"10.{asn}.0.254", f"10.100.0.{asn}", f"Observer Ops Router {asn}")
        ebgp.addPrivatePeering(100, TRANSIT_ASN, asn, abRelationship=PeerRelationship.Provider)

    for asn in cfg["noise"]:
        add_router_as(base, asn, f"10.{asn}.0.0/24", f"10.{asn}.0.254", f"10.100.0.{asn}", f"Background Router {asn}")
        ebgp.addPrivatePeering(100, TRANSIT_ASN, asn, abRelationship=PeerRelationship.Provider)

    emu.addLayer(base)
    emu.addLayer(routing)
    emu.addLayer(ebgp)
    emu.addLayer(ibgp)
    emu.addLayer(ospf)
    return emu


def run():
    platform, tier = parse_args()
    emu = build_case(tier)
    emu.render()
    docker = Docker(
        platform=platform,
        namingScheme=f"{CONTAINER_PREFIX}as{{asn}}{{role}}-{{displayName}}-{{primaryIp}}",
        internetMapEnabled=False,
    )
    emu.compile(docker, str(OUTPUT_DIR), override=True)


if __name__ == "__main__":
    run()
