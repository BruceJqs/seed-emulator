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
CONTAINER_PREFIX = os.environ.get("B53_CONTAINER_PREFIX", "b53-")

SERVICE_IP = "10.53.10.80"
FRONTEND_ASN = 53
CONTROL_ASN = 54
ORIGIN_ASN = 55
TRANSIT_ASN = 50

POP_IPS = [
    ("iad", "10.53.10.11", True),
    ("sjc", "10.53.10.12", True),
    ("lhr", "10.53.10.13", True),
    ("sin", "10.53.10.14", True),
    ("gru", "10.53.10.15", True),
    ("syd", "10.53.10.16", True),
    ("ams", "10.53.10.17", True),
    ("canary", "10.53.10.18", False),
]

CONTROL_COMPONENTS = [
    ("config-api", "10.54.10.11", "Config API"),
    ("validator", "10.54.10.12", "Config Validator"),
    ("compiler", "10.54.10.13", "Config Compiler"),
    ("distributor", "10.54.10.14", "Config Distributor"),
    ("release-manager", "10.54.10.15", "Release Manager"),
    ("status-dashboard", "10.54.10.16", "Status Dashboard"),
]

ORIGINS = [
    ("news", "10.55.10.80", "Customer Origin News"),
    ("api", "10.55.10.81", "Customer Origin API"),
    ("media", "10.55.10.82", "Customer Origin Media"),
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

STATE_DIR = pathlib.Path("/var/lib/b53")
STATE_FILE = STATE_DIR / "edge_frontend.env"
LAST_REQUEST = STATE_DIR / "last_request.txt"
LOG = pathlib.Path("/var/log/b53-edge-frontend.log")


def log(message):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as stream:
        stream.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {message}\\n")


def state_for(phase):
    if phase == "normal":
        return {
            "case_id": "b53",
            "incident_phase": "normal",
            "http_code": "200",
            "frontend_mode": "serving",
            "origin_health": "healthy",
            "runtime_version": "edge-runtime-vN",
            "config_version": "svc-news-v42",
            "pop_error_rate": "0_percent",
            "affected_pops": "0/8",
            "canary_pop": "ready",
        }
    if phase == "fault":
        return {
            "case_id": "b53",
            "incident_phase": "fault",
            "http_code": "503",
            "frontend_mode": "degraded",
            "origin_health": "healthy",
            "runtime_version": "edge-runtime-vN",
            "config_version": "svc-trigger-v43",
            "pop_error_rate": "85_percent",
            "affected_pops": "7/8",
            "canary_pop": "unaffected_control_pop",
            "root_cause": "valid_customer_config_triggered_edge_runtime_bug",
        }
    if phase == "recovery":
        return {
            "case_id": "b53",
            "incident_phase": "recovery",
            "http_code": "200",
            "frontend_mode": "serving",
            "origin_health": "healthy",
            "runtime_version": "edge-runtime-vN",
            "config_version": "svc-news-v42-rollback",
            "pop_error_rate": "0_percent",
            "affected_pops": "0/8",
            "canary_pop": "passed",
            "distribution": "frozen_then_rolled_back",
            "hotfix_note": "recorded",
            "recovery_complete": "yes",
            "canary_passed": "yes",
        }
    raise SystemExit(f"unknown phase {phase}")


def write_state(phase):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    values = state_for(phase)
    STATE_FILE.write_text("".join(f"{key}={value}\\n" for key, value in values.items()))
    log(f"phase={phase} code={values['http_code']} config={values['config_version']} affected={values['affected_pops']}")


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
    code = int(values["http_code"])
    if code == 200:
        body = (
            "FASTLY_EDGE_OK "
            f"config={values['config_version']} runtime={values['runtime_version']} "
            f"origin={values['origin_health']} pop_error_rate={values['pop_error_rate']}\\n"
        )
    else:
        body = (
            "FASTLY_EDGE_RUNTIME_ERROR "
            f"config={values['config_version']} runtime={values['runtime_version']} "
            f"origin={values['origin_health']} affected_pops={values['affected_pops']}\\n"
        )
    LAST_REQUEST.write_text(
        f"request_id={time.time_ns()}\\n"
        f"http_code={code}\\n"
        f"incident_phase={values['incident_phase']}\\n"
        f"frontend_mode={values['frontend_mode']}\\n"
        f"{body}"
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
    raise SystemExit("usage: b53-edge-frontend.sh normal|fault|recovery|status|serve")
"""


EDGE_POP_SCRIPT = """\
#!/usr/bin/env python3
import http.server
import pathlib
import sys
import time

POP = "__POP__"
AFFECTED = __AFFECTED__
STATE = pathlib.Path("/var/run/b53-pop-state.env")
LOG = pathlib.Path(f"/var/log/b53-edge-pop-{POP}.log")


def log(message):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as stream:
        stream.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} pop={POP} {message}\\n")


def state_for(phase):
    if phase == "normal":
        return {
            "pop": POP,
            "incident_phase": "normal",
            "http_code": "200",
            "edge_status": "serving",
            "runtime_version": "edge-runtime-vN",
            "config_version": "svc-news-v42",
            "config_loader": "stable",
            "origin_health": "healthy",
            "cache_hit_ratio": "warm",
            "pop_error_rate": "0_percent",
        }
    if phase == "fault":
        if AFFECTED:
            return {
                "pop": POP,
                "incident_phase": "fault",
                "http_code": "503",
                "edge_status": "runtime_error",
                "runtime_version": "edge-runtime-vN",
                "config_version": "svc-trigger-v43",
                "config_loader": "legal_config_loaded",
                "trigger_condition": "true",
                "origin_health": "healthy",
                "cache_hit_ratio": "not_relevant",
                "pop_error_rate": "5xx",
                "root_cause": "valid_customer_config_triggered_edge_runtime_bug",
            }
        return {
            "pop": POP,
            "incident_phase": "fault",
            "http_code": "200",
            "edge_status": "canary_unaffected",
            "runtime_version": "edge-runtime-vN",
            "config_version": "svc-news-v42",
            "config_loader": "distribution_guarded",
            "origin_health": "healthy",
            "cache_hit_ratio": "warm",
            "pop_error_rate": "0_percent",
        }
    if phase == "recovery":
        return {
            "pop": POP,
            "incident_phase": "recovery",
            "http_code": "200",
            "edge_status": "serving",
            "runtime_version": "edge-runtime-vN",
            "config_version": "svc-news-v42-rollback",
            "config_loader": "rolled_back",
            "origin_health": "healthy",
            "cache_hit_ratio": "warming",
            "pop_error_rate": "0_percent",
            "canary_passed": "yes",
        }
    raise SystemExit(f"unknown phase {phase}")


def write_state(phase):
    values = state_for(phase)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text("".join(f"{key}={value}\\n" for key, value in values.items()))
    log(f"phase={phase} code={values['http_code']} status={values['edge_status']} config={values['config_version']}")


def read_state():
    if not STATE.exists():
        write_state("normal")
    values = {}
    for line in STATE.read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        values = read_state()
        body = "".join(f"{key}={value}\\n" for key, value in values.items()).encode()
        self.send_response(int(values["http_code"]))
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
    if not STATE.exists():
        write_state("normal")
    sys.stdout.write(STATE.read_text())
    if LOG.exists():
        print("\\n== pop_log ==")
        sys.stdout.write(LOG.read_text())
elif cmd == "serve":
    write_state("normal")
    http.server.ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
else:
    raise SystemExit("usage: b53-edge-pop.sh normal|fault|recovery|status|serve")
"""


CONTROL_COMPONENT_SCRIPT = """\
#!/usr/bin/env python3
import http.server
import pathlib
import sys
import time

ROLE = "__ROLE__"
STATE = pathlib.Path(f"/var/run/b53-{ROLE}.env")
LOG = pathlib.Path(f"/var/log/b53-{ROLE}.log")


def log(message):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as stream:
        stream.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} role={ROLE} {message}\\n")


ROLE_STATES = {
    "config-api": {
        "normal": {
            "config_api": "accepting",
            "latest_config": "svc-news-v42",
            "customer_actor": "normal_customer_push",
            "trigger_condition": "absent",
        },
        "fault": {
            "config_api": "valid_config_accepted",
            "latest_config": "svc-trigger-v43",
            "customer_actor": "customer-trigger",
            "trigger_condition": "true",
            "schema_validation": "not_the_failure",
        },
        "recovery": {
            "config_api": "frozen_for_incident",
            "latest_config": "svc-news-v42",
            "trigger_config": "disabled",
            "distribution_policy": "freeze_new_customer_config",
        },
    },
    "validator": {
        "normal": {"validator": "passed", "legal_config": "true", "semantic_error": "none"},
        "fault": {"validator": "passed", "legal_config": "true", "semantic_error": "none", "important": "config_is_not_malicious"},
        "recovery": {"validator": "passed", "rollback_config": "approved", "canary_policy": "required"},
    },
    "compiler": {
        "normal": {"compiler": "artifact_v42", "runtime_sensitive_path": "inactive"},
        "fault": {"compiler": "artifact_v43", "runtime_sensitive_path": "active", "compiled_successfully": "yes"},
        "recovery": {"compiler": "artifact_v42", "rollback_artifact": "selected"},
    },
    "distributor": {
        "normal": {"distributor": "stable", "pop_coverage": "8/8", "affected_pops": "0/8", "pop_error_rate": "0_percent"},
        "fault": {
            "distributor": "propagated_to_majority_pops",
            "pop_coverage": "8/8",
            "affected_pops": "7/8",
            "pop_error_rate": "85_percent",
            "canary_pop": "held_back",
        },
        "recovery": {
            "distributor": "rolled_back",
            "distribution": "frozen_then_rolled_back",
            "pop_coverage": "8/8",
            "affected_pops": "0/8",
            "pop_error_rate": "0_percent",
            "canary_pop": "passed",
        },
    },
    "release-manager": {
        "normal": {
            "release_manager": "normal",
            "edge_runtime": "edge-runtime-vN",
            "runtime_deployed_at": "T-27d",
            "latent_bug": "untriggered",
        },
        "fault": {
            "release_manager": "release_v43_active",
            "edge_runtime": "edge-runtime-vN",
            "latent_bug": "triggered_by_legal_config",
            "root_cause": "valid_customer_config_triggered_edge_runtime_bug",
            "origin_health": "healthy",
        },
        "recovery": {
            "release_manager": "trigger_config_disabled",
            "edge_runtime": "edge-runtime-vN",
            "latent_bug": "mitigated_by_config_disable",
            "hotfix_note": "recorded",
            "canary_pop": "passed",
        },
    },
    "status-dashboard": {
        "normal": {"status_service": "normal", "public_message": "all_edge_pops_serving"},
        "fault": {
            "status_service": "incident_open",
            "public_message": "global_edge_error_spike_under_investigation",
            "origin_health": "healthy",
            "pop_error_rate": "85_percent",
        },
        "recovery": {
            "status_service": "recovery_verified",
            "public_message": "edge_errors_mitigated_after_config_rollback",
            "postmortem": "pending_runtime_hotfix",
        },
    },
}


def state_for(phase):
    if phase not in ROLE_STATES[ROLE]:
        raise SystemExit(f"unknown phase {phase}")
    values = {"case_id": "b53", "component": ROLE, "incident_phase": phase}
    values.update(ROLE_STATES[ROLE][phase])
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
    raise SystemExit(f"usage: b53-{ROLE}.sh normal|fault|recovery|status|serve")
"""


ORIGIN_SCRIPT = """\
#!/usr/bin/env python3
import http.server

ORIGIN = "__ORIGIN__"


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = f"origin={ORIGIN}\\norigin_health=healthy\\ncustomer_service=serving\\n".encode()
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
            raise SystemExit("usage: fastly_edge_config_bug.py [amd|arm] [S0|S1|S1.5|S2]")
        args.pop(0)
    if args:
        tier = canonical_tier(args.pop(0))
    if args or tier not in TIERS:
        raise SystemExit("usage: fastly_edge_config_bug.py [amd|arm] [S0|S1|S1.5|S2]")
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
        base, FRONTEND_ASN, "10.53.10.0/24", "10.53.10.254", "10.100.0.53", "Fastly Public Edge Router"
    )
    control_as, _ = add_router_as(
        base, CONTROL_ASN, "10.54.10.0/24", "10.54.10.254", "10.100.0.54", "Fastly Control Plane Router"
    )
    origin_as, _ = add_router_as(
        base, ORIGIN_ASN, "10.55.10.0/24", "10.55.10.254", "10.100.0.55", "Customer Origin Router"
    )

    frontend_router.addSoftware("python3")
    frontend_router.setFile("/usr/local/bin/b53-edge-frontend.sh", EDGE_FRONTEND_SCRIPT)
    frontend_router.appendStartCommand("chmod +x /usr/local/bin/b53-edge-frontend.sh")
    frontend_router.appendStartCommand(f"ip addr add {SERVICE_IP}/32 dev lo || true")
    frontend_router.appendStartCommand("/usr/local/bin/b53-edge-frontend.sh serve", fork=True)

    for pop, ip, affected in POP_IPS:
        node = add_host(frontend_as, f"edge-pop-{pop}", ip, f"Edge POP {pop.upper()}")
        node.setFile(
            "/usr/local/bin/b53-edge-pop.sh",
            EDGE_POP_SCRIPT.replace("__POP__", pop).replace("__AFFECTED__", "True" if affected else "False"),
        )
        node.appendStartCommand("chmod +x /usr/local/bin/b53-edge-pop.sh")
        node.appendStartCommand("/usr/local/bin/b53-edge-pop.sh serve", fork=True)

    for role, ip, display in CONTROL_COMPONENTS:
        node = add_host(control_as, role, ip, display)
        node.setFile("/usr/local/bin/b53-control-component.sh", CONTROL_COMPONENT_SCRIPT.replace("__ROLE__", role))
        node.appendStartCommand("chmod +x /usr/local/bin/b53-control-component.sh")
        node.appendStartCommand("/usr/local/bin/b53-control-component.sh serve", fork=True)

    for origin, ip, display in ORIGINS:
        node = add_host(origin_as, f"origin-{origin}", ip, display)
        node.setFile("/usr/local/bin/b53-origin-server.sh", ORIGIN_SCRIPT.replace("__ORIGIN__", origin))
        node.appendStartCommand("chmod +x /usr/local/bin/b53-origin-server.sh")
        node.appendStartCommand("/usr/local/bin/b53-origin-server.sh", fork=True)

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
