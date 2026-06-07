#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

from seedemu.compiler import Docker, Platform
from seedemu.core import Action, Binding, Emulator, Filter
from seedemu.layers import Base, Ebgp, Ibgp, Ospf, PeerRelationship, Routing
from seedemu.services import WebService


CASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = CASE_DIR / "output"
CONTAINER_PREFIX = os.environ.get("B52_CONTAINER_PREFIX", "b52-")

SERVICE_IP = "10.52.10.80"
FRONTEND_ASN = 52
CONTROL_ASN = 53
ORIGIN_ASN = 54
TRANSIT_ASN = 50

INDEX_IPS = ["10.53.10.11", "10.53.10.12", "10.53.10.13", "10.53.10.14", "10.53.10.15"]
PLACEMENT_IPS = ["10.53.10.21", "10.53.10.22", "10.53.10.23"]
CAPACITY_REGISTRY_IP = "10.53.10.40"
MAINTENANCE_IP = "10.53.10.50"
STATUS_DASHBOARD_IP = "10.53.10.60"
OBJECT_SHARD_IP = "10.54.10.80"


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

MAINTENANCE_SCRIPT = """\
#!/bin/sh
set -eu
INDEX_IPS="__INDEX_IPS__"
PLACEMENT_IPS="__PLACEMENT_IPS__"
CAPACITY_IP="__CAPACITY_IP__"
LOG=/var/log/b52-maintenance-tool.log
RECOVERY_STEPS=/var/lib/b52/recovery_steps.txt
mkdir -p /var/lib/b52

write_log() {
    printf "%s %s\\n" "$(date -Is)" "$1" >> "$LOG"
}

post_node() {
    ip="$1"
    state="$2"
    curl -fsS --max-time 1 "http://$ip:8080/" >/dev/null 2>&1 || true
    docker_not_available=0
    :
}

set_node() {
    ip="$1"
    state="$2"
    # The service listens on each node, but state changes must happen inside
    # that node. We use ssh-free in-network control by sending a best-effort
    # HTTP probe first, then rely on local per-node scripts when invoked via
    # docker exec from b52ctl for runtime mutation.
    printf '%s %s\\n' "$ip" "$state" >> /var/lib/b52/pending_node_state.tsv
}

set_capacity() {
    phase="$1"
    curl -fsS --max-time 1 "http://$CAPACITY_IP:8080/" >/dev/null 2>&1 || true
    printf '%s\\n' "$phase" > /var/lib/b52/desired_capacity_phase
}

case "${1:-}" in
    dry-run)
        cat <<'EOF'
maintenance_tool=dry_run
requested_selector=subsystem=billing-sampler count=small
expected_removed=index=0 placement=0 billing=small
guardrails=minimum_capacity_and_rate_limit_expected
EOF
        ;;
    inject)
        : > /var/lib/b52/pending_node_state.tsv
        for ip in 10.53.10.11 10.53.10.12 10.53.10.13 10.53.10.21 10.53.10.22; do
            set_node "$ip" removed
        done
        set_capacity fault
        write_log "fault injected: selector expanded from billing to index/placement capacity"
        ;;
    recover)
        : > /var/lib/b52/pending_node_state.tsv
        for ip in $INDEX_IPS $PLACEMENT_IPS; do
            set_node "$ip" active
        done
        set_capacity recovery
        cat > "$RECOVERY_STEPS" <<'EOF'
freeze maintenance selector
restore index quorum
run index/object integrity check
restore placement quorum
run canary PUT
drain dependent backlog
EOF
        write_log "recovery staged: froze maintenance, restored index, integrity, placement, canary, backlog"
        ;;
    status)
        cat "$LOG" 2>/dev/null || true
        printf '\\n== pending_node_state ==\\n'
        cat /var/lib/b52/pending_node_state.tsv 2>/dev/null || true
        printf '\\n== desired_capacity_phase ==\\n'
        cat /var/lib/b52/desired_capacity_phase 2>/dev/null || true
        printf '\\n== recovery_steps ==\\n'
        cat "$RECOVERY_STEPS" 2>/dev/null || true
        ;;
    *)
        echo "usage: $0 dry-run|inject|recover|status" >&2
        exit 2
        ;;
esac
"""


CAPACITY_SERVICE_SCRIPT = """\
#!/usr/bin/env python3
import http.server
import pathlib
import sys
import time

STATE_DIR = pathlib.Path("/var/lib/b52")
STATE_FILE = STATE_DIR / "capacity.env"
LOG = pathlib.Path("/var/log/b52-capacity-registry.log")


def log(message):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as stream:
        stream.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {message}\\n")


def state_for(phase):
    if phase == "normal":
        values = {
            "incident_phase": "normal",
            "frontend_mode": "serving",
            "backend_origin": "healthy",
            "object_shards": "available",
            "maintenance_selector": "idle",
            "capacity_registry": "consistent",
            "index_quorum": "5/5",
            "placement_quorum": "3/3",
            "integrity_check": "ready",
            "canary_put": "ready",
            "dependent_backlog": "0",
        }
    elif phase == "fault":
        values = {
            "incident_phase": "fault",
            "frontend_mode": "degraded",
            "backend_origin": "healthy",
            "object_shards": "available",
            "maintenance_selector": "unsafe_capacity_removal",
            "capacity_registry": "missing_capacity",
            "index_quorum": "2/5",
            "placement_quorum": "1/3",
            "integrity_check": "blocked",
            "canary_put": "blocked_until_capacity_restored",
            "dependent_backlog": "growing",
            "root_cause": "maintenance_selector_removed_index_and_placement_capacity",
        }
    elif phase == "recovery":
        values = {
            "incident_phase": "recovery",
            "frontend_mode": "serving",
            "backend_origin": "healthy",
            "object_shards": "available",
            "maintenance_selector": "frozen",
            "capacity_registry": "consistent",
            "index_quorum": "5/5",
            "placement_quorum": "3/3",
            "integrity_check": "passed",
            "canary_put": "passed",
            "dependent_backlog": "drained",
            "root_cause": "mitigated",
            "recovery_complete": "yes",
            "canary_passed": "yes",
        }
    else:
        raise SystemExit(f"unknown phase {phase}")
    values["case_id"] = "b52"
    return values


def write_state(phase):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    values = state_for(phase)
    STATE_FILE.write_text("".join(f"{key}={value}\\n" for key, value in values.items()))
    log(f"phase={phase} index={values['index_quorum']} placement={values['placement_quorum']}")


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if not STATE_FILE.exists():
            write_state("normal")
        body = STATE_FILE.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


def serve():
    http.server.ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()


cmd = sys.argv[1] if len(sys.argv) > 1 else ""
if cmd in ("init", "normal", "fault", "recovery"):
    write_state("normal" if cmd == "init" else cmd)
elif cmd == "status":
    if not STATE_FILE.exists():
        write_state("normal")
    sys.stdout.write(STATE_FILE.read_text())
elif cmd == "http":
    serve()
else:
    raise SystemExit("usage: b52-capacity-registry.sh init|normal|fault|recovery|status|http")
"""


SUBSYSTEM_SERVICE_SCRIPT = """\
#!/usr/bin/env python3
import http.server
import pathlib
import sys
import time

ROLE = "__ROLE__"
NODE = "__NODE__"
STATE = pathlib.Path("/var/run/b52-node-state")
LOG = pathlib.Path(f"/var/log/b52-{ROLE}-{NODE}.log")


def log(message):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as stream:
        stream.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} role={ROLE} node={NODE} {message}\\n")


def set_state(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(state + "\\n")
    log(f"state={state}")


def get_state():
    if not STATE.exists():
        set_state("active")
    return STATE.read_text().strip()


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        state = get_state()
        body = f"role={ROLE}\\nnode={NODE}\\nstatus={state}\\n".encode()
        self.send_response(200 if state == "active" else 503)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"
if cmd in ("active", "removed"):
    set_state(cmd)
elif cmd == "status":
    print(f"role={ROLE}")
    print(f"node={NODE}")
    print(f"status={get_state()}")
elif cmd == "serve":
    set_state("active")
    http.server.ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
else:
    raise SystemExit("usage: b52-subsystem-node.sh active|removed|status|serve")
"""


API_FRONTEND_SCRIPT = """\
#!/usr/bin/env python3
import http.server
import pathlib
import sys
import time

SERVICE_IP = "__SERVICE_IP__"
STATE_DIR = pathlib.Path("/var/lib/b52")
API_STATE = STATE_DIR / "api_state.env"
LAST_REQUEST = STATE_DIR / "last_request.txt"
LOG = pathlib.Path("/var/log/b52-api-frontend.log")


def log(message):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as stream:
        stream.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {message}\\n")


def state_for(phase):
    if phase == "normal":
        return {
            "incident_phase": "normal",
            "http_code": "200",
            "index_quorum": "5/5",
            "placement_quorum": "3/3",
            "object_shard": "healthy",
            "frontend_mode": "serving",
        }
    if phase == "fault":
        return {
            "incident_phase": "fault",
            "http_code": "503",
            "index_quorum": "2/5",
            "placement_quorum": "1/3",
            "object_shard": "healthy",
            "frontend_mode": "degraded",
            "root_cause": "maintenance_selector_removed_index_and_placement_capacity",
        }
    if phase == "recovery":
        return {
            "incident_phase": "recovery",
            "http_code": "200",
            "index_quorum": "5/5",
            "placement_quorum": "3/3",
            "object_shard": "healthy",
            "frontend_mode": "serving",
            "recovery_complete": "yes",
            "canary_passed": "yes",
        }
    raise SystemExit(f"unknown phase {phase}")


def write_state(phase):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    values = state_for(phase)
    API_STATE.write_text("".join(f"{key}={value}\\n" for key, value in values.items()))
    log(f"phase={phase} http_code={values['http_code']} index={values['index_quorum']} placement={values['placement_quorum']}")


def read_state():
    if not API_STATE.exists():
        write_state("normal")
    values = {}
    for line in API_STATE.read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def evaluate():
    values = read_state()
    code = int(values["http_code"])
    if code == 200:
        body = f"S3 API OK: index_quorum={values['index_quorum']} placement_quorum={values['placement_quorum']} object_shard={values['object_shard']}\\n"
    else:
        body = f"S3 API CONTROL_PLANE_UNAVAILABLE: index_quorum={values['index_quorum']} placement_quorum={values['placement_quorum']} object_shard={values['object_shard']}\\n"
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LAST_REQUEST.write_text(
        f"request_id={time.time_ns()}\\n"
        f"http_code={code}\\n"
        f"{body}"
        f"incident_phase={values['incident_phase']}\\n"
        f"frontend_mode={values['frontend_mode']}\\n"
    )
    return code, body.encode()


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        code, body = evaluate()
        self.send_response(code)
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
    if API_STATE.exists():
        print("== api_state ==")
        sys.stdout.write(API_STATE.read_text())
    if LAST_REQUEST.exists():
        print("\\n== last_request ==")
        sys.stdout.write(LAST_REQUEST.read_text())
    print("\\n== frontend log ==")
    if LOG.exists():
        sys.stdout.write(LOG.read_text())
elif cmd == "serve":
    write_state("normal")
    log(f"api frontend starting service_ip={SERVICE_IP}")
    http.server.ThreadingHTTPServer(("0.0.0.0", 80), Handler).serve_forever()
else:
    raise SystemExit("usage: b52-api-frontend.sh normal|fault|recovery|serve|status")
"""


STATUS_DASHBOARD_SCRIPT = """\
#!/usr/bin/env python3
import http.server
import urllib.request

CAPACITY_IP = "__CAPACITY_IP__"


def fetch_capacity():
    try:
        with urllib.request.urlopen(f"http://{CAPACITY_IP}:8080/", timeout=0.8) as response:
            return response.read().decode(errors="replace")
    except Exception as exc:
        return f"capacity_registry=unreachable\\nerror={exc}\\n"


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        state = fetch_capacity()
        if "incident_phase=fault" in state:
            headline = "S3 status dashboard delayed: control-plane capacity event under investigation"
        elif "incident_phase=recovery" in state:
            headline = "S3 status dashboard: recovery verified after staged canary"
        else:
            headline = "S3 status dashboard: normal"
        body = f"{headline}\\n\\n{state}".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


http.server.ThreadingHTTPServer(("0.0.0.0", 80), Handler).serve_forever()
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
            raise SystemExit("usage: aws_s3_control_plane.py [amd|arm] [S0|S1|S1.5|S2]")
        args.pop(0)
    if args:
        tier = canonical_tier(args.pop(0))
    if args or tier not in TIERS:
        raise SystemExit("usage: aws_s3_control_plane.py [amd|arm] [S0|S1|S1.5|S2]")
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
    web = WebService()

    base.createInternetExchange(100)

    add_router_as(base, TRANSIT_ASN, "10.50.0.0/24", "10.50.0.254", "10.100.0.50", "Transit Router")
    frontend_as, frontend_router = add_router_as(
        base, FRONTEND_ASN, "10.52.10.0/24", "10.52.10.254", "10.100.0.52", "S3 Public API Router"
    )
    control_as, _ = add_router_as(
        base, CONTROL_ASN, "10.53.10.0/24", "10.53.10.254", "10.100.0.53", "S3 Control Plane Router"
    )
    origin_as, _ = add_router_as(
        base, ORIGIN_ASN, "10.54.10.0/24", "10.54.10.254", "10.100.0.54", "S3 Object Shard Router"
    )

    api = add_host(frontend_as, "api-frontend", "10.52.10.81", "S3 API Frontend Observer")
    api.setFile("/usr/local/share/b52-api-frontend-note.txt", "Public API service runs on the S3 Public API Router VIP 10.52.10.80 for cross-AS reachability.\n")

    frontend_router.addSoftware("python3")
    frontend_router.addSoftware("curl")
    frontend_router.setFile(
        "/usr/local/bin/b52-api-frontend.sh",
        API_FRONTEND_SCRIPT.replace("__SERVICE_IP__", SERVICE_IP)
        .replace("__INDEX_IPS__", " ".join(INDEX_IPS))
        .replace("__PLACEMENT_IPS__", " ".join(PLACEMENT_IPS))
        .replace("__CAPACITY_IP__", CAPACITY_REGISTRY_IP)
        .replace("__OBJECT_SHARD_IP__", OBJECT_SHARD_IP),
    )
    frontend_router.appendStartCommand("chmod +x /usr/local/bin/b52-api-frontend.sh")
    frontend_router.appendStartCommand(f"ip addr add {SERVICE_IP}/32 dev lo || true")
    frontend_router.appendStartCommand("/usr/local/bin/b52-api-frontend.sh serve", fork=True)

    for idx, ip in enumerate(INDEX_IPS, start=1):
        node = add_host(control_as, f"index-{idx}", ip, f"Index Subsystem {idx}")
        node.setFile(
            "/usr/local/bin/b52-subsystem-node.sh",
            SUBSYSTEM_SERVICE_SCRIPT.replace("__ROLE__", "index").replace("__NODE__", str(idx)),
        )
        node.appendStartCommand("chmod +x /usr/local/bin/b52-subsystem-node.sh")
        node.appendStartCommand("/usr/local/bin/b52-subsystem-node.sh serve", fork=True)

    for idx, ip in enumerate(PLACEMENT_IPS, start=1):
        node = add_host(control_as, f"placement-{idx}", ip, f"Placement Subsystem {idx}")
        node.setFile(
            "/usr/local/bin/b52-subsystem-node.sh",
            SUBSYSTEM_SERVICE_SCRIPT.replace("__ROLE__", "placement").replace("__NODE__", str(idx)),
        )
        node.appendStartCommand("chmod +x /usr/local/bin/b52-subsystem-node.sh")
        node.appendStartCommand("/usr/local/bin/b52-subsystem-node.sh serve", fork=True)

    registry = add_host(control_as, "capacity-registry", CAPACITY_REGISTRY_IP, "Capacity Registry")
    registry.setFile("/usr/local/bin/b52-capacity-registry.sh", CAPACITY_SERVICE_SCRIPT)
    registry.appendStartCommand("chmod +x /usr/local/bin/b52-capacity-registry.sh")
    registry.appendStartCommand("/usr/local/bin/b52-capacity-registry.sh init")
    registry.appendStartCommand("while true; do /usr/local/bin/b52-capacity-registry.sh http; done", fork=True)

    maintenance = add_host(control_as, "maintenance-tool", MAINTENANCE_IP, "Maintenance Tool")
    maintenance.setFile(
        "/usr/local/bin/b52-maintenance-tool.sh",
        MAINTENANCE_SCRIPT.replace("__INDEX_IPS__", " ".join(INDEX_IPS))
        .replace("__PLACEMENT_IPS__", " ".join(PLACEMENT_IPS))
        .replace("__CAPACITY_IP__", CAPACITY_REGISTRY_IP),
    )
    maintenance.appendStartCommand("chmod +x /usr/local/bin/b52-maintenance-tool.sh")

    dashboard = add_host(control_as, "status-dashboard", STATUS_DASHBOARD_IP, "Status Dashboard")
    dashboard.setFile(
        "/usr/local/bin/b52-status-dashboard.sh",
        STATUS_DASHBOARD_SCRIPT.replace("__CAPACITY_IP__", CAPACITY_REGISTRY_IP),
    )
    dashboard.appendStartCommand("chmod +x /usr/local/bin/b52-status-dashboard.sh")
    dashboard.appendStartCommand("/usr/local/bin/b52-status-dashboard.sh", fork=True)

    origin_as.createHost("object-shard").joinNetwork("net0", address=OBJECT_SHARD_IP).setDisplayName("Object Storage Shard")
    web.install("object-shard").setIndexContent("object_shard=healthy\nstored_object=benchmark-canary\n")

    for asn in (FRONTEND_ASN, CONTROL_ASN, ORIGIN_ASN):
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
    emu.addLayer(web)
    emu.addBinding(Binding("object-shard", filter=Filter(asn=ORIGIN_ASN, nodeName="object-shard"), action=Action.FIRST))
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
