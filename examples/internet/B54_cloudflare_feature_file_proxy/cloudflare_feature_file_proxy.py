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
CONTAINER_PREFIX = os.environ.get("B54_CONTAINER_PREFIX", "b54-")

SERVICE_IP = "10.54.10.80"
FRONTEND_ASN = 54
CONTROL_ASN = 55
ORIGIN_ASN = 56
TRANSIT_ASN = 50

POP_IPS = [
    ("iad", "10.54.10.11"),
    ("sjc", "10.54.10.12"),
    ("lhr", "10.54.10.13"),
    ("sin", "10.54.10.14"),
    ("gru", "10.54.10.15"),
    ("syd", "10.54.10.16"),
    ("ams", "10.54.10.17"),
    ("canary", "10.54.10.18"),
]

TAIL_SERVICES = [
    ("kv", "10.54.10.31", "Workers KV Gateway"),
    ("access", "10.54.10.32", "Access Gateway"),
    ("turnstile", "10.54.10.33", "Turnstile Service"),
    ("dashboard", "10.54.10.34", "Dashboard Service"),
]

CONTROL_COMPONENTS = [
    ("feature-db", "10.55.10.11", "Feature DB"),
    ("permission-rollout", "10.55.10.12", "Permission Rollout"),
    ("feature-generator", "10.55.10.13", "Feature Generator"),
    ("feature-distributor", "10.55.10.14", "Feature Distributor"),
    ("known-good-store", "10.55.10.15", "Known Good Store"),
    ("incident-console", "10.55.10.16", "Incident Console"),
    ("dashboard-control", "10.55.10.17", "Dashboard Control"),
]

ORIGINS = [
    ("shop", "10.56.10.80", "Customer Origin Shop"),
    ("api", "10.56.10.81", "Customer Origin API"),
    ("media", "10.56.10.82", "Customer Origin Media"),
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


CORE_FRONTEND_SCRIPT = """\
#!/usr/bin/env python3
import http.server
import pathlib
import sys
import time

STATE_DIR = pathlib.Path("/var/lib/b54")
STATE_FILE = STATE_DIR / "core_frontend.env"
LAST_REQUEST = STATE_DIR / "last_request.txt"
LOG = pathlib.Path("/var/log/b54-core-frontend.log")


def log(message):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as stream:
        stream.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {message}\\n")


def state_for(phase):
    if phase == "normal":
        return {
            "case_id": "b54",
            "incident_phase": "normal",
            "http_code": "200",
            "frontend_mode": "serving",
            "origin_health": "healthy",
            "feature_hash": "known_good_20260606",
            "feature_file_count": "24000",
            "feature_file_size_mb": "18",
            "bot_module": "scoring",
            "core_proxy": "healthy",
            "tail_services": "healthy",
            "pop_error_rate": "0_percent",
        }
    if phase == "fault":
        return {
            "case_id": "b54",
            "incident_phase": "fault",
            "http_code": "503",
            "frontend_mode": "degraded",
            "origin_health": "healthy",
            "feature_hash": "bad_feature_file_20260606",
            "feature_file_count": "1250000",
            "feature_file_size_mb": "920",
            "bot_module": "load_limit_failure",
            "core_proxy": "5xx",
            "tail_services": "degraded_by_core_proxy",
            "pop_error_rate": "global_5xx",
            "root_cause": "feature_file_count_and_size_exceeded_core_proxy_limit",
        }
    if phase == "recovery":
        return {
            "case_id": "b54",
            "incident_phase": "recovery",
            "http_code": "200",
            "frontend_mode": "serving",
            "origin_health": "healthy",
            "feature_hash": "known_good_20260606",
            "feature_file_count": "24000",
            "feature_file_size_mb": "18",
            "bot_module": "fail_small",
            "core_proxy": "healthy",
            "tail_services": "validated",
            "pop_error_rate": "0_percent",
            "known_good_store": "restored_feature_set_20260606",
            "canary": "passed",
            "recovery_complete": "yes",
            "canary_passed": "yes",
        }
    raise SystemExit(f"unknown phase {phase}")


def write_state(phase):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    values = state_for(phase)
    STATE_FILE.write_text("".join(f"{key}={value}\\n" for key, value in values.items()))
    log(f"phase={phase} code={values['http_code']} feature_count={values['feature_file_count']} core_proxy={values['core_proxy']}")


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
            "CLOUDFLARE_CORE_PROXY_OK "
            f"feature_hash={values['feature_hash']} count={values['feature_file_count']} "
            f"bot_module={values['bot_module']} origin={values['origin_health']}\\n"
        )
    else:
        body = (
            "CLOUDFLARE_CORE_PROXY_5XX "
            f"feature_hash={values['feature_hash']} count={values['feature_file_count']} "
            f"bot_module={values['bot_module']} origin={values['origin_health']}\\n"
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
    print("== core_frontend_state ==")
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
    raise SystemExit("usage: b54-core-frontend.sh normal|fault|recovery|status|serve")
"""


EDGE_POP_SCRIPT = """\
#!/usr/bin/env python3
import http.server
import pathlib
import sys
import time

POP = "__POP__"
STATE = pathlib.Path("/var/run/b54-pop-state.env")
LOG = pathlib.Path(f"/var/log/b54-core-pop-{POP}.log")


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
            "core_proxy": "healthy",
            "bot_module": "scoring",
            "feature_hash": "known_good_20260606",
            "feature_file_count": "24000",
            "feature_file_size_mb": "18",
            "origin_health": "healthy",
            "tail_dependency": "healthy",
        }
    if phase == "fault":
        return {
            "pop": POP,
            "incident_phase": "fault",
            "http_code": "503",
            "core_proxy": "5xx",
            "bot_module": "load_limit_failure",
            "feature_hash": "bad_feature_file_20260606",
            "feature_file_count": "1250000",
            "feature_file_size_mb": "920",
            "origin_health": "healthy",
            "tail_dependency": "degraded_by_core_proxy",
            "root_cause": "feature_file_count_and_size_exceeded_core_proxy_limit",
        }
    if phase == "recovery":
        return {
            "pop": POP,
            "incident_phase": "recovery",
            "http_code": "200",
            "core_proxy": "healthy",
            "bot_module": "fail_small",
            "feature_hash": "known_good_20260606",
            "feature_file_count": "24000",
            "feature_file_size_mb": "18",
            "origin_health": "healthy",
            "tail_dependency": "validated",
            "canary_passed": "yes",
        }
    raise SystemExit(f"unknown phase {phase}")


def write_state(phase):
    values = state_for(phase)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text("".join(f"{key}={value}\\n" for key, value in values.items()))
    log(f"phase={phase} code={values['http_code']} core_proxy={values['core_proxy']} count={values['feature_file_count']}")


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
    raise SystemExit("usage: b54-core-pop.sh normal|fault|recovery|status|serve")
"""


CONTROL_COMPONENT_SCRIPT = """\
#!/usr/bin/env python3
import http.server
import pathlib
import sys
import time

ROLE = "__ROLE__"
STATE = pathlib.Path(f"/var/run/b54-{ROLE}.env")
LOG = pathlib.Path(f"/var/log/b54-{ROLE}.log")


def log(message):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as stream:
        stream.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} role={ROLE} {message}\\n")


ROLE_STATES = {
    "feature-db": {
        "normal": {"feature_db": "consistent", "permission_view": "stable", "duplicate_entries": "0"},
        "fault": {
            "feature_db": "expanded_permissions",
            "permission_view": "changed",
            "duplicate_entries": "many",
            "root_input": "db_permission_rollout_changed_generator_query_results",
        },
        "recovery": {"feature_db": "stable", "permission_view": "frozen", "duplicate_entries": "0"},
    },
    "permission-rollout": {
        "normal": {"permission_rollout": "idle", "db_change": "none"},
        "fault": {"permission_rollout": "new_acl_active", "db_change": "expanded_bot_feature_query_scope"},
        "recovery": {"permission_rollout": "halted", "db_change": "frozen_pending_review"},
    },
    "feature-generator": {
        "normal": {
            "feature_generator": "normal",
            "feature_file_count": "24000",
            "feature_file_size_mb": "18",
            "feature_hash": "known_good_20260606",
        },
        "fault": {
            "feature_generator": "runaway",
            "feature_file_count": "1250000",
            "feature_file_size_mb": "920",
            "feature_hash": "bad_feature_file_20260606",
            "schema_valid": "true",
        },
        "recovery": {
            "feature_generator": "stopped",
            "feature_file_count": "24000",
            "feature_file_size_mb": "18",
            "feature_hash": "known_good_20260606",
        },
    },
    "feature-distributor": {
        "normal": {
            "feature_distributor": "stable",
            "distributed_hash": "known_good_20260606",
            "pop_coverage": "8/8",
            "core_proxy": "healthy",
        },
        "fault": {
            "feature_distributor": "global_bad_file",
            "distributed_hash": "bad_feature_file_20260606",
            "pop_coverage": "8/8",
            "core_proxy": "5xx",
            "tail_services": "degraded_by_core_proxy",
        },
        "recovery": {
            "feature_distributor": "stopped_then_known_good",
            "distributed_hash": "known_good_20260606",
            "pop_coverage": "8/8",
            "core_proxy": "healthy",
            "canary": "passed",
        },
    },
    "known-good-store": {
        "normal": {"known_good_store": "feature_set_20260606", "rollback_ready": "yes"},
        "fault": {"known_good_store": "available", "rollback_ready": "yes", "bad_hash": "bad_feature_file_20260606"},
        "recovery": {"known_good_store": "restored_feature_set_20260606", "rollback_ready": "used"},
    },
    "incident-console": {
        "normal": {"incident_console": "quiet", "ddos_hypothesis": "not_active"},
        "fault": {
            "incident_console": "open",
            "initial_hypothesis": "possible_ddos_noise",
            "evidence": "origin_healthy_bad_feature_hash_shared_by_pops",
        },
        "recovery": {"incident_console": "mitigated", "postmortem": "validate_internal_generated_artifacts_like_user_input"},
    },
    "dashboard-control": {
        "normal": {"dashboard_control": "available", "access": "available", "turnstile": "available", "kv": "available"},
        "fault": {"dashboard_control": "degraded", "access": "degraded", "turnstile": "degraded", "kv": "degraded"},
        "recovery": {"dashboard_control": "available", "access": "validated", "turnstile": "validated", "kv": "validated"},
    },
}


def state_for(phase):
    if phase not in ROLE_STATES[ROLE]:
        raise SystemExit(f"unknown phase {phase}")
    values = {"case_id": "b54", "component": ROLE, "incident_phase": phase}
    values.update(ROLE_STATES[ROLE][phase])
    if phase == "fault":
        values.setdefault("root_cause", "feature_file_count_and_size_exceeded_core_proxy_limit")
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
    raise SystemExit(f"usage: b54-{ROLE}.sh normal|fault|recovery|status|serve")
"""


TAIL_SERVICE_SCRIPT = """\
#!/usr/bin/env python3
import http.server
import pathlib
import sys
import time

SERVICE = "__SERVICE__"
STATE = pathlib.Path(f"/var/run/b54-tail-{SERVICE}.env")
LOG = pathlib.Path(f"/var/log/b54-tail-{SERVICE}.log")


def log(message):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as stream:
        stream.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} service={SERVICE} {message}\\n")


def state_for(phase):
    if phase == "normal":
        return {
            "service": SERVICE,
            "incident_phase": "normal",
            "http_code": "200",
            "tail_service_status": "healthy",
            "dependency": "core_proxy_healthy",
        }
    if phase == "fault":
        return {
            "service": SERVICE,
            "incident_phase": "fault",
            "http_code": "503",
            "tail_service_status": "degraded_by_core_proxy",
            "dependency": "bad_feature_file_in_core_proxy_path",
            "root_cause": "feature_file_count_and_size_exceeded_core_proxy_limit",
        }
    if phase == "recovery":
        return {
            "service": SERVICE,
            "incident_phase": "recovery",
            "http_code": "200",
            "tail_service_status": "validated",
            "dependency": "known_good_feature_file",
            "canary_passed": "yes",
        }
    raise SystemExit(f"unknown phase {phase}")


def write_state(phase):
    values = state_for(phase)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text("".join(f"{key}={value}\\n" for key, value in values.items()))
    log(f"phase={phase} code={values['http_code']}")


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
        print("\\n== tail_log ==")
        sys.stdout.write(LOG.read_text())
elif cmd == "serve":
    write_state("normal")
    http.server.ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
else:
    raise SystemExit("usage: b54-tail-service.sh normal|fault|recovery|status|serve")
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
            raise SystemExit("usage: cloudflare_feature_file_proxy.py [amd|arm] [S0|S1|S1.5|S2]")
        args.pop(0)
    if args:
        tier = canonical_tier(args.pop(0))
    if args or tier not in TIERS:
        raise SystemExit("usage: cloudflare_feature_file_proxy.py [amd|arm] [S0|S1|S1.5|S2]")
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
        base, FRONTEND_ASN, "10.54.10.0/24", "10.54.10.254", "10.100.0.54", "Cloudflare Core Proxy Router"
    )
    control_as, _ = add_router_as(
        base, CONTROL_ASN, "10.55.10.0/24", "10.55.10.254", "10.100.0.55", "Cloudflare Control Plane Router"
    )
    origin_as, _ = add_router_as(
        base, ORIGIN_ASN, "10.56.10.0/24", "10.56.10.254", "10.100.0.56", "Customer Origin Router"
    )

    frontend_router.addSoftware("python3")
    frontend_router.setFile("/usr/local/bin/b54-core-frontend.sh", CORE_FRONTEND_SCRIPT)
    frontend_router.appendStartCommand("chmod +x /usr/local/bin/b54-core-frontend.sh")
    frontend_router.appendStartCommand(f"ip addr add {SERVICE_IP}/32 dev lo || true")
    frontend_router.appendStartCommand("/usr/local/bin/b54-core-frontend.sh serve", fork=True)

    for pop, ip in POP_IPS:
        node = add_host(frontend_as, f"core-pop-{pop}", ip, f"Core Proxy POP {pop.upper()}")
        node.setFile("/usr/local/bin/b54-core-pop.sh", EDGE_POP_SCRIPT.replace("__POP__", pop))
        node.appendStartCommand("chmod +x /usr/local/bin/b54-core-pop.sh")
        node.appendStartCommand("/usr/local/bin/b54-core-pop.sh serve", fork=True)

    for service, ip, display in TAIL_SERVICES:
        node = add_host(frontend_as, f"tail-{service}", ip, display)
        node.setFile("/usr/local/bin/b54-tail-service.sh", TAIL_SERVICE_SCRIPT.replace("__SERVICE__", service))
        node.appendStartCommand("chmod +x /usr/local/bin/b54-tail-service.sh")
        node.appendStartCommand("/usr/local/bin/b54-tail-service.sh serve", fork=True)

    for role, ip, display in CONTROL_COMPONENTS:
        node = add_host(control_as, role, ip, display)
        node.setFile("/usr/local/bin/b54-control-component.sh", CONTROL_COMPONENT_SCRIPT.replace("__ROLE__", role))
        node.appendStartCommand("chmod +x /usr/local/bin/b54-control-component.sh")
        node.appendStartCommand("/usr/local/bin/b54-control-component.sh serve", fork=True)

    for origin, ip, display in ORIGINS:
        node = add_host(origin_as, f"origin-{origin}", ip, display)
        node.setFile("/usr/local/bin/b54-origin-server.sh", ORIGIN_SCRIPT.replace("__ORIGIN__", origin))
        node.appendStartCommand("chmod +x /usr/local/bin/b54-origin-server.sh")
        node.appendStartCommand("/usr/local/bin/b54-origin-server.sh", fork=True)

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
