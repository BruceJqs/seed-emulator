#!/usr/bin/env python3
import os
import sys
from pathlib import Path

from seedemu.compiler import Docker, Platform
from seedemu.core import Emulator
from seedemu.layers import Base, Ebgp, Ibgp, Ospf, PeerRelationship, Routing


CASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = CASE_DIR / "output"
CONTAINER_PREFIX = os.environ.get("B55_CONTAINER_PREFIX", "b55-")

VICTIM_PREFIX = "10.55.0.0/24"
LEAK_PREFIX = "10.55.0.0/25"
VICTIM_IP = "10.55.0.80"


RUNTIME_TIERS = {
    "S0": {
        "unfiltered_probe_asns": [80, 81],
        "filtered_probe_asns": [90],
        "collector_asns": [101],
        "noise_asns": [],
    },
    "S1": {
        "unfiltered_probe_asns": list(range(80, 126)),
        "filtered_probe_asns": list(range(126, 146)),
        "collector_asns": list(range(160, 170)),
        "noise_asns": list(range(170, 231)),
    },
    "S1_5": {
        "unfiltered_probe_asns": list(range(80, 145)),
        "filtered_probe_asns": list(range(145, 170)),
        "collector_asns": list(range(170, 186)),
        "noise_asns": list(range(186, 250)),
    },
    "S2": {
        "unfiltered_probe_asns": list(range(80, 170)),
        "filtered_probe_asns": list(range(170, 220)),
        "collector_asns": list(range(220, 245)),
        "noise_asns": list(range(245, 255)),
    },
}


def _asn_range(start: int, stop: int, *, skip=(100,), fill_to: int | None = None, fill_start: int | None = None):
    asns = [asn for asn in range(start, stop) if asn not in skip]
    if fill_to is not None:
        next_asn = fill_start if fill_start is not None else stop
        while len(asns) < fill_to:
            if next_asn not in skip:
                asns.append(next_asn)
            next_asn += 1
    return asns


RUNTIME_TIERS["S1"]["unfiltered_probe_asns"] = _asn_range(80, 126, fill_to=46, fill_start=250)
RUNTIME_TIERS["S1_5"]["unfiltered_probe_asns"] = _asn_range(80, 145, fill_to=65, fill_start=250)
RUNTIME_TIERS["S2"]["unfiltered_probe_asns"] = _asn_range(80, 170, fill_to=90, fill_start=255)


LEAK_STATIC_BIRD = f"""

protocol static leaked_more_specific {{
    ipv4 {{
        table t_direct;
        import all;
        export none;
    }};
    route {LEAK_PREFIX} blackhole;
}}
"""


DQE_CONTROL_SCRIPT = """\
#!/bin/sh
set -eu
LOG=/var/log/b55-route-leak-change.log
PEER="u_as703"

write_log() {
    printf "%s %s\\n" "$(date -Is)" "$1" >> "$LOG"
}

wait_bird() {
    while ! birdc show status >/dev/null 2>&1; do
        sleep 1
    done
}

case "${1:-}" in
    init-normal)
        wait_bird
        birdc dis "$PEER" >/tmp/b55-dqe-control.log 2>&1 || true
        write_log "normal guard: disabled DQE export session $PEER so leaked more-specific stays local"
        ;;
    inject)
        birdc en "$PEER" >/tmp/b55-dqe-control.log 2>&1 || true
        write_log "fault injected: enabled DQE export session $PEER for leaked more-specific"
        ;;
    clear)
        birdc dis "$PEER" >/tmp/b55-dqe-control.log 2>&1 || true
        write_log "mitigation: disabled DQE export session $PEER and withdrew leaked more-specific from Verizon path"
        ;;
    status)
        birdc show protocols "$PEER" 2>&1 || true
        birdc show route __LEAK_PREFIX__ all 2>&1 || true
        ;;
    *)
        echo "usage: $0 init-normal|inject|clear|status" >&2
        exit 2
        ;;
esac
""".replace("__LEAK_PREFIX__", LEAK_PREFIX)


VICTIM_ROUTER_HTTP_SCRIPT = """\
#!/bin/sh
set -eu
VIP="__VICTIM_IP__"
LOG=/var/log/b55-victim-router-http.log
ip addr add "$VIP/32" dev lo 2>/dev/null || true
while true; do
    body="B55 victim CDN edge is healthy on router VIP $VIP; diagnose BGP path selection.\\n"
    length="$(printf "%s" "$body" | wc -c | tr -d ' ')"
    {
        printf 'HTTP/1.1 200 OK\\r\\n'
        printf 'Content-Type: text/plain\\r\\n'
        printf 'Content-Length: %s\\r\\n' "$length"
        printf 'Connection: close\\r\\n'
        printf '\\r\\n'
        printf "%s" "$body"
    } | nc -N -l -p 80 >> "$LOG" 2>&1 || true
done
""".replace("__VICTIM_IP__", VICTIM_IP)


def _canonical_tier(value: str) -> str:
    upper = value.upper()
    if upper in ("S1.5", "S1_5", "S15"):
        return "S1_5"
    return upper


def _parse_args():
    platform = Platform.AMD64
    tier = "S0"
    if len(sys.argv) > 1:
        if sys.argv[1].lower() in ("amd", "amd64"):
            platform = Platform.AMD64
        elif sys.argv[1].lower() in ("arm", "arm64"):
            platform = Platform.ARM64
        else:
            raise SystemExit("usage: verizon_route_leak.py [amd|arm] [S0|S1|S1.5|S2]")
    if len(sys.argv) > 2:
        tier = _canonical_tier(sys.argv[2])
        if tier not in RUNTIME_TIERS:
            raise SystemExit("usage: verizon_route_leak.py [amd|arm] [S0|S1|S1.5|S2]")
    if len(sys.argv) > 3:
        raise SystemExit("usage: verizon_route_leak.py [amd|arm] [S0|S1|S1.5|S2]")
    return platform, tier


def _access_prefix(asn: int) -> str:
    return f"10.{asn}.0.0/24"


def _access_ip(asn: int) -> str:
    return f"10.{asn}.0.254"


def _join_ix(router, address: str):
    router.joinNetwork("ix100", address=address)
    return router


def _add_router_as(base: Base, asn: int, net_name: str, prefix: str, router_ip: str, ix_ip: str, display: str):
    asys = base.createAutonomousSystem(asn)
    asys.createNetwork(net_name, prefix)
    router = asys.createRouter("router")
    router.joinNetwork(net_name, address=router_ip)
    _join_ix(router, ix_ip)
    router.setDisplayName(display)
    router.addSoftware("curl")
    return asys, router


def build_case(tier: str):
    tier_cfg = RUNTIME_TIERS[tier]
    emu = Emulator()
    base = Base()
    routing = Routing()
    ebgp = Ebgp()
    ibgp = Ibgp()
    ospf = Ospf()

    base.createInternetExchange(100)

    victim_as, victim_router = _add_router_as(
        base, 55, "net0", VICTIM_PREFIX, "10.55.0.254", "10.100.0.55", "Victim CDN Router"
    )
    victim_router.setFile("/usr/local/bin/b55-victim-router-http.sh", VICTIM_ROUTER_HTTP_SCRIPT)
    victim_router.appendStartCommand("chmod +x /usr/local/bin/b55-victim-router-http.sh")
    victim_router.appendStartCommand("/usr/local/bin/b55-victim-router-http.sh", fork=True)

    _add_router_as(base, 56, "net0", "10.56.0.0/24", "10.56.0.254", "10.100.0.56", "Legitimate Transit Router")
    _add_router_as(base, 57, "net0", "10.57.0.0/24", "10.57.0.254", "10.100.0.57", "Filtered Transit Router")
    _add_router_as(base, 701, "net0", "10.70.1.0/24", "10.70.1.254", "10.100.0.71", "Verizon AS701 Router")
    _add_router_as(base, 703, "net0", "10.70.3.0/24", "10.70.3.254", "10.100.0.73", "Allegheny Customer Router")
    _, dqe_router = _add_router_as(base, 702, "net0", "10.70.2.0/24", "10.70.2.254", "10.100.0.72", "DQE BGP Optimizer Router")
    dqe_router.setFile("/usr/local/bin/b55-dqe-control.sh", DQE_CONTROL_SCRIPT)
    dqe_router.appendStartCommand("chmod +x /usr/local/bin/b55-dqe-control.sh")

    # Legitimate aggregate path.
    ebgp.addPrivatePeering(100, 56, 55, abRelationship=PeerRelationship.Provider)
    ebgp.addPrivatePeering(100, 57, 55, abRelationship=PeerRelationship.Provider)

    # Leak chain: DQE customer -> Allegheny -> Verizon.
    ebgp.addPrivatePeering(100, 703, 702, abRelationship=PeerRelationship.Provider)
    ebgp.addPrivatePeering(100, 701, 703, abRelationship=PeerRelationship.Provider)

    for asn in tier_cfg["unfiltered_probe_asns"]:
        _add_router_as(
            base,
            asn,
            "net0",
            _access_prefix(asn),
            _access_ip(asn),
            f"10.100.0.{asn}",
            f"Unfiltered Probe Router {asn}",
        )
        ebgp.addPrivatePeering(100, 56, asn, abRelationship=PeerRelationship.Provider)
        ebgp.addPrivatePeering(100, 701, asn, abRelationship=PeerRelationship.Provider)

    for asn in tier_cfg["filtered_probe_asns"]:
        _add_router_as(
            base,
            asn,
            "net0",
            _access_prefix(asn),
            _access_ip(asn),
            f"10.100.0.{asn}",
            f"Filtered Probe Router {asn}",
        )
        ebgp.addPrivatePeering(100, 57, asn, abRelationship=PeerRelationship.Provider)

    for asn in tier_cfg["collector_asns"]:
        _add_router_as(
            base,
            asn,
            "net0",
            _access_prefix(asn),
            _access_ip(asn),
            f"10.100.0.{asn}",
            f"Route Collector Router {asn}",
        )
        ebgp.addPrivatePeering(100, 701, asn, abRelationship=PeerRelationship.Provider)
        ebgp.addPrivatePeering(100, 56, asn, abRelationship=PeerRelationship.Provider)

    for asn in tier_cfg["noise_asns"]:
        _add_router_as(
            base,
            asn,
            "net0",
            _access_prefix(asn),
            _access_ip(asn),
            f"10.100.0.{asn}",
            f"Background AS Router {asn}",
        )
        ebgp.addPrivatePeering(100, 56, asn, abRelationship=PeerRelationship.Provider)

    emu.addLayer(base)
    emu.addLayer(routing)
    emu.addLayer(ebgp)
    emu.addLayer(ibgp)
    emu.addLayer(ospf)
    return emu, dqe_router


def run():
    platform, tier = _parse_args()
    emu, dqe_router = build_case(tier)
    emu.render()

    dqe_router.appendFile("/etc/bird/bird.conf", LEAK_STATIC_BIRD)
    dqe_router.appendStartCommand("/usr/local/bin/b55-dqe-control.sh init-normal", fork=True)

    docker = Docker(
        platform=platform,
        namingScheme=f"{CONTAINER_PREFIX}as{{asn}}{{role}}-{{displayName}}-{{primaryIp}}",
        internetMapEnabled=False,
    )
    emu.compile(docker, str(OUTPUT_DIR), override=True)


if __name__ == "__main__":
    run()
