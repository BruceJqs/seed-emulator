#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

from seedemu.compiler import Docker, Platform
from seedemu.core import Action, Binding, Emulator, Filter
from seedemu.layers import Base, Ebgp, Ibgp, Ospf, PeerRelationship, Routing
from seedemu.services import WebService


SERVICE_CASES = {
    "b52": {
        "case_id": "b52",
        "slug": "aws_s3_control_plane",
        "prefix": "b52-",
        "domain": "s3-control.bench.test",
        "service_ip": "10.52.10.80",
        "frontend_asn": 52,
        "control_asn": 53,
        "origin_asn": 54,
        "normal": "S3 API PUT/GET/LIST healthy; index and placement quorum above threshold.",
        "fault": "maintenance selector removed excess index/placement capacity; API remains alive but returns control-plane errors.",
        "recovery": "freeze maintenance, restore index, run integrity check, restore placement, canary PUT, drain backlog.",
        "normal_state": """\
case_id=b52
incident_phase=normal
frontend_mode=serving
backend_origin=healthy
index_quorum=7/7
placement_quorum=5/5
object_shards=available
maintenance_selector=idle
capacity_registry=consistent
dependent_backlog=0
canary_put=ready
""",
        "fault_state": """\
case_id=b52
incident_phase=fault
frontend_mode=degraded
backend_origin=healthy
root_cause=maintenance_selector_removed_index_and_placement_capacity
index_quorum=2/7
placement_quorum=1/5
object_shards=available
maintenance_selector=unsafe_capacity_removal
capacity_registry=missing_capacity
dependent_backlog=growing
canary_put=blocked_until_capacity_restored
""",
        "recovery_state": """\
case_id=b52
incident_phase=recovery
frontend_mode=serving
backend_origin=healthy
root_cause=mitigated
maintenance_selector=frozen
index_quorum=7/7
placement_quorum=5/5
object_shards=available
capacity_registry=consistent
integrity_check=passed
canary_put=passed
dependent_backlog=drained
recovery_complete=yes
canary_passed=yes
""",
        "recovery_steps": """\
freeze maintenance selector
restore index quorum
run index/object integrity check
restore placement quorum
run canary PUT
drain dependent backlog
""",
    },
    "b53": {
        "case_id": "b53",
        "slug": "fastly_edge_config_bug",
        "prefix": "b53-",
        "domain": "fastly-customer.bench.test",
        "service_ip": "10.53.10.80",
        "frontend_asn": 53,
        "control_asn": 54,
        "origin_asn": 55,
        "normal": "Edge POPs proxy customer origins with valid runtime/config versions.",
        "fault": "legal customer config triggers latent edge runtime bug; origins remain healthy.",
        "recovery": "freeze distribution, rollback/disable trigger config, POP canary, full restore, hotfix note.",
        "normal_state": """\
case_id=b53
incident_phase=normal
frontend_mode=serving
origin_health=healthy
config_api=accepting
validator=passed
compiler=artifact_v42
distributor=stable
release_manager=normal
pop_error_rate=0_percent
canary_pop=ready
""",
        "fault_state": """\
case_id=b53
incident_phase=fault
frontend_mode=degraded
origin_health=healthy
root_cause=valid_customer_config_triggered_edge_runtime_bug
config_api=valid_config_accepted
validator=passed
compiler=artifact_v43
distributor=propagated_to_majority_pops
release_manager=release_v43_active
pop_error_rate=85_percent
canary_pop=blocked_until_distribution_frozen
""",
        "recovery_state": """\
case_id=b53
incident_phase=recovery
frontend_mode=serving
origin_health=healthy
root_cause=mitigated
config_api=frozen_for_incident
validator=passed
compiler=artifact_v42
distributor=rolled_back
release_manager=trigger_config_disabled
pop_error_rate=0_percent
canary_pop=passed
hotfix_note=recorded
recovery_complete=yes
canary_passed=yes
""",
        "recovery_steps": """\
freeze edge config distribution
disable triggering customer config
roll back compiler artifact
run POP canary
restore distribution
record hotfix note
""",
    },
    "b54": {
        "case_id": "b54",
        "slug": "cloudflare_feature_file_proxy",
        "prefix": "b54-",
        "domain": "cloudflare-customer.bench.test",
        "service_ip": "10.54.10.80",
        "frontend_asn": 54,
        "control_asn": 55,
        "origin_asn": 56,
        "normal": "Core proxy loads known-good Bot Management feature file and all tail services respond.",
        "fault": "feature file count/size exceeds runtime limit and propagates to core proxy.",
        "recovery": "stop generation/distribution, rollback known-good, kill switch/fail-small, canary, tail validation.",
        "normal_state": """\
case_id=b54
incident_phase=normal
frontend_mode=serving
origin_health=healthy
feature_db=consistent
feature_generator=normal
feature_distributor=stable
known_good_store=feature_set_20260606
feature_file_count=24000
feature_file_size_mb=18
core_proxy=healthy
tail_services=healthy
canary=ready
""",
        "fault_state": """\
case_id=b54
incident_phase=fault
frontend_mode=degraded
origin_health=healthy
root_cause=feature_file_count_and_size_exceeded_core_proxy_limit
feature_db=expanded_permissions
feature_generator=runaway
feature_distributor=global_bad_file
known_good_store=available
feature_file_count=1250000
feature_file_size_mb=920
core_proxy=5xx
tail_services=healthy_but_hidden_by_proxy
canary=blocked_until_known_good_rollback
""",
        "recovery_state": """\
case_id=b54
incident_phase=recovery
frontend_mode=serving
origin_health=healthy
root_cause=mitigated
feature_db=stable
feature_generator=stopped
feature_distributor=stopped_then_known_good
known_good_store=restored_feature_set_20260606
feature_file_count=24000
feature_file_size_mb=18
core_proxy=healthy
bot_module=fail_small
tail_services=validated
canary=passed
recovery_complete=yes
canary_passed=yes
""",
        "recovery_steps": """\
stop feature generation
stop global distribution
roll back known-good feature file
enable fail-small kill switch
run core proxy canary
validate KV Access Turnstile tail services
""",
    },
    "b57": {
        "case_id": "b57",
        "slug": "google_network_congestion",
        "prefix": "b57-",
        "domain": "google-workload.bench.test",
        "service_ip": "10.57.10.80",
        "frontend_asn": 57,
        "control_asn": 58,
        "origin_asn": 59,
        "normal": "Multi-region control plane jobs running; BGP sessions stable; workload probes succeed.",
        "fault": "maintenance automation deschedules network control plane; fail-static expires into route withdraw/congestion.",
        "recovery": "halt automation, drop noncritical/retry traffic, reschedule control plane, rebuild/distribute config, region verification.",
        "normal_state": """\
case_id=b57
incident_phase=normal
frontend_mode=serving
workload_health=healthy
maintenance_automation=idle
cluster_managers=scheduled
network_control_plane=running
config_store=consistent
route_distributor=stable
te_controller=balanced
bgp_state=stable
retry_traffic=normal
canary_region=ready
""",
        "fault_state": """\
case_id=b57
incident_phase=fault
frontend_mode=degraded
workload_health=healthy
root_cause=maintenance_automation_descheduled_network_control_plane
maintenance_automation=unsafe_global_deschedule
cluster_managers=missing_control_plane_jobs
network_control_plane=down
config_store=stale
route_distributor=fail_static_expired
te_controller=congested
bgp_state=withdrawn_or_degraded
retry_traffic=amplified
canary_region=blocked_until_control_plane_rescheduled
""",
        "recovery_state": """\
case_id=b57
incident_phase=recovery
frontend_mode=serving
workload_health=healthy
root_cause=mitigated
maintenance_automation=halted
cluster_managers=rescheduled
network_control_plane=running
config_store=rebuild_passed
route_distributor=distributed
te_controller=balanced
bgp_state=stable
retry_traffic=noncritical_dropped_then_normal
canary_region=passed
region_verification=passed
recovery_complete=yes
canary_passed=yes
""",
        "recovery_steps": """\
halt maintenance automation
drop noncritical retry traffic
reschedule network control-plane jobs
rebuild config store state
redistribute route and TE config
verify regions one by one
""",
    },
}


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
    "S1": {"clients": asn_range(80, 140, fill_to=60, fill_start=250), "ops": list(range(140, 152)), "noise": list(range(152, 210)) + [251, 252, 253, 254, 255, 256]},
    "S1_5": {"clients": asn_range(80, 155, fill_to=75, fill_start=250), "ops": list(range(155, 175)), "noise": list(range(175, 240)) + [251, 252, 253, 254]},
    "S2": {"clients": asn_range(80, 180, fill_to=100, fill_start=250), "ops": list(range(180, 220)), "noise": list(range(220, 250)) + list(range(260, 288))},
}


CONTROL_SCRIPT = """\
#!/bin/sh
set -eu
STATE_FILE=/var/run/agent-case-state
LOG=/var/log/agent-case-control.log
STATUS_CONF=/etc/nginx/sites-available/default
WEB_ROOT=/var/www/html
DOMAIN_DIR=/var/lib/agent-case

write_log() {
    printf "%s %s\\n" "$(date -Is)" "$1" >> "$LOG"
}

write_domain_state() {
    state="$1"
    mkdir -p "$DOMAIN_DIR"
    case "$state" in
        normal)
            cat > "$DOMAIN_DIR/domain_state.env" <<'EOF'
__DOMAIN_NORMAL_STATE__
EOF
            : > "$DOMAIN_DIR/recovery_steps.txt"
            ;;
        fault)
            cat > "$DOMAIN_DIR/domain_state.env" <<'EOF'
__DOMAIN_FAULT_STATE__
EOF
            : > "$DOMAIN_DIR/recovery_steps.txt"
            ;;
        recovery)
            cat > "$DOMAIN_DIR/domain_state.env" <<'EOF'
__DOMAIN_RECOVERY_STATE__
EOF
            cat > "$DOMAIN_DIR/recovery_steps.txt" <<'EOF'
__RECOVERY_STEPS__
EOF
            ;;
        *)
            echo "unknown" > "$DOMAIN_DIR/domain_state.env"
            : > "$DOMAIN_DIR/recovery_steps.txt"
            ;;
    esac
}

publish_state() {
    state="$1"
    status="$2"
    body="$3"
    mkdir -p /var/run "$WEB_ROOT" "$(dirname "$STATUS_CONF")"
    echo "$state" > "$STATE_FILE"
    write_domain_state "$state"
    printf '%s\\n' "$body" > "$WEB_ROOT/index.html"
    cat > "$STATUS_CONF" <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    root $WEB_ROOT;
    location / {
        return $status /index.html;
    }
}
EOF
    nginx -t >/dev/null 2>&1 || true
    if pgrep nginx >/dev/null 2>&1; then
        service nginx reload >/dev/null 2>&1 || true
    else
        service nginx start >/dev/null 2>&1 || true
    fi
    write_log "state $state: $body"
}

case "${1:-}" in
    normal)
        publish_state normal 200 "__NORMAL__"
        ;;
    inject)
        publish_state fault 503 "__FAULT__"
        ;;
    recover)
        publish_state recovery 200 "__RECOVERY__"
        ;;
    status)
        printf '== state ==\\n'
        cat "$STATE_FILE" 2>/dev/null || echo normal
        printf '\\n== domain state ==\\n'
        cat "$DOMAIN_DIR/domain_state.env" 2>/dev/null || true
        printf '\\n== recovery steps ==\\n'
        cat "$DOMAIN_DIR/recovery_steps.txt" 2>/dev/null || true
        printf '\\n== log ==\\n'
        cat "$LOG" 2>/dev/null || true
        ;;
    *)
        echo "usage: $0 normal|inject|recover|status" >&2
        exit 2
        ;;
esac
"""


def canonical_tier(value: str) -> str:
    upper = value.upper()
    if upper in ("S1.5", "S1_5", "S15"):
        return "S1_5"
    return upper


def parse_args():
    script = Path(sys.argv[0]).name
    case_id = os.environ.get("AGENT_CASE_ID", "").lower()
    platform = Platform.AMD64
    tier = "S0"
    args = list(sys.argv[1:])
    if args and args[0].lower() in SERVICE_CASES:
        case_id = args.pop(0).lower()
    if args:
        if args[0].lower() in ("amd", "amd64"):
            platform = Platform.AMD64
        elif args[0].lower() in ("arm", "arm64"):
            platform = Platform.ARM64
        else:
            raise SystemExit(f"usage: {script} [b52|b53|b54|b57] [amd|arm] [S0|S1|S1.5|S2]")
        args.pop(0)
    if args:
        tier = canonical_tier(args.pop(0))
    if args or case_id not in SERVICE_CASES or tier not in TIERS:
        raise SystemExit(f"usage: {script} [b52|b53|b54|b57] [amd|arm] [S0|S1|S1.5|S2]")
    return SERVICE_CASES[case_id], platform, tier


def router_as(base: Base, asn: int, prefix: str, router_ip: str, ix_ip: str, display: str):
    asys = base.createAutonomousSystem(asn)
    asys.createNetwork("net0", prefix)
    router = asys.createRouter("router")
    router.joinNetwork("net0", address=router_ip).joinNetwork("ix100", address=ix_ip)
    router.setDisplayName(display)
    router.addSoftware("curl")
    return asys, router


def build_case(spec: dict, tier: str):
    cfg = TIERS[tier]
    emu = Emulator()
    base = Base()
    routing = Routing()
    ebgp = Ebgp()
    ibgp = Ibgp()
    ospf = Ospf()

    base.createInternetExchange(100)

    transit_as, _ = router_as(base, 50, "10.50.0.0/24", "10.50.0.254", "10.100.0.50", "Transit Router")
    frontend_as, frontend_router = router_as(
        base,
        spec["frontend_asn"],
        f"10.{spec['frontend_asn']}.10.0/24",
        f"10.{spec['frontend_asn']}.10.254",
        f"10.100.0.{spec['frontend_asn']}",
        "Public Service Frontend Router",
    )
    control_as, control_router = router_as(
        base,
        spec["control_asn"],
        f"10.{spec['control_asn']}.10.0/24",
        f"10.{spec['control_asn']}.10.254",
        f"10.100.0.{spec['control_asn']}",
        "Control Plane Router",
    )
    origin_as, origin_router = router_as(
        base,
        spec["origin_asn"],
        f"10.{spec['origin_asn']}.10.0/24",
        f"10.{spec['origin_asn']}.10.254",
        f"10.100.0.{spec['origin_asn']}",
        "Backend Or Origin Router",
    )
    origin_as.createHost("backend").joinNetwork("net0", address=f"10.{spec['origin_asn']}.10.80")

    for asn in (spec["frontend_asn"], spec["control_asn"], spec["origin_asn"]):
        ebgp.addPrivatePeering(100, 50, asn, abRelationship=PeerRelationship.Provider)

    for asn in cfg["clients"]:
        router_as(base, asn, f"10.{asn}.0.0/24", f"10.{asn}.0.254", f"10.100.0.{asn}", f"Client Probe Router {asn}")
        ebgp.addPrivatePeering(100, 50, asn, abRelationship=PeerRelationship.Provider)

    for asn in cfg["ops"]:
        router_as(base, asn, f"10.{asn}.0.0/24", f"10.{asn}.0.254", f"10.100.0.{asn}", f"Observer Ops Router {asn}")
        ebgp.addPrivatePeering(100, 50, asn, abRelationship=PeerRelationship.Provider)

    for asn in cfg["noise"]:
        router_as(base, asn, f"10.{asn}.0.0/24", f"10.{asn}.0.254", f"10.100.0.{asn}", f"Background Router {asn}")
        ebgp.addPrivatePeering(100, 50, asn, abRelationship=PeerRelationship.Provider)

    control = (
        CONTROL_SCRIPT
        .replace("__NORMAL__", spec["normal"])
        .replace("__FAULT__", spec["fault"])
        .replace("__RECOVERY__", spec["recovery"])
        .replace("__DOMAIN_NORMAL_STATE__", spec["normal_state"].rstrip())
        .replace("__DOMAIN_FAULT_STATE__", spec["fault_state"].rstrip())
        .replace("__DOMAIN_RECOVERY_STATE__", spec["recovery_state"].rstrip())
        .replace("__RECOVERY_STEPS__", spec["recovery_steps"].rstrip())
    )
    frontend_router.addSoftware("nginx-light")
    frontend_router.appendStartCommand(f"ip addr add {spec['service_ip']}/32 dev lo || true")
    frontend_router.setFile("/usr/local/bin/agent-case-control.sh", control)
    frontend_router.setFile("/etc/nginx/sites-available/default", "server { listen 80 default_server; listen [::]:80 default_server; root /var/www/html; location / { return 200 /index.html; } }\\n")
    frontend_router.appendStartCommand("chmod +x /usr/local/bin/agent-case-control.sh")
    frontend_router.appendStartCommand("/usr/local/bin/agent-case-control.sh normal")

    web = WebService()
    web.install("backend").setIndexContent(f"{spec['slug']} backend/origin remains healthy for root-cause contrast.\\n")

    emu.addLayer(base)
    emu.addLayer(routing)
    emu.addLayer(ebgp)
    emu.addLayer(ibgp)
    emu.addLayer(ospf)
    emu.addLayer(web)
    emu.addBinding(Binding("backend", filter=Filter(asn=spec["origin_asn"], nodeName="backend"), action=Action.FIRST))
    return emu


def run():
    spec, platform, tier = parse_args()
    emu = build_case(spec, tier)
    emu.render()
    case_dir = Path(os.environ.get("AGENT_CASE_DIR", Path.cwd())).resolve()
    docker = Docker(
        platform=platform,
        namingScheme=f"{spec['prefix']}as{{asn}}{{role}}-{{displayName}}-{{primaryIp}}",
        internetMapEnabled=False,
    )
    emu.compile(docker, str(case_dir / "output"), override=True)


if __name__ == "__main__":
    run()
