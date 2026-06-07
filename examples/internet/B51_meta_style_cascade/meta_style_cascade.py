#!/usr/bin/env python3
import os
import sys
from pathlib import Path

from seedemu.compiler import Docker, DockerImage, Platform, ROUTER_IMAGE, ROUTER_IMAGE_ARM64
from seedemu.core import Emulator, Binding, Filter, Action
from seedemu.layers import Base, Routing, Ebgp, Ibgp, Ospf, PeerRelationship
from seedemu.services import DomainNameService, DomainNameCachingService, WebService


CASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = CASE_DIR / "output"
DOMAIN = "meta-bench.test."
FQDN = "www.meta-bench.test"
EDGE_DNS_IP = "10.20.0.53"
EDGE_ROUTER_NET_IP = "10.20.0.254"
EDGE_SERVICE_IP = "10.20.0.80"
RESOLVER_IP = "10.50.0.53"
BACKEND_IP = "10.30.0.80"
CONTAINER_PREFIX = os.environ.get("B51_CONTAINER_PREFIX", "b51-")
ROUTER_SERVICE_IMAGE_ARM = "b51-router-services-base-arm"
ROUTER_SERVICE_IMAGE_AMD = "b51-router-services-base-amd"
S2_LOCAL_AS_SECOND_BASE = 220
S2_LOCAL_AS_SECOND_LIMIT = 224
S2_IX_SECOND = 225
INTERNET_MAP_CONTAINER = os.environ.get("B51_INTERNET_MAP_CONTAINER", "meta-cascade-internet-map")

RUNTIME_TIERS = {
    "S0": {
        "transit_shard_asns": [],
        "probe_asns": [],
        "collector_asns": [],
        "noise_asns": [],
    },
    "S1": {
        # 122 added AS roles plus the 4 core AS roles. With the route-view host
        # and two IX route servers this starts at least 129 live runtime
        # containers. This is the only accepted S1 runtime target in this
        # first-round case.
        "transit_shard_asns": [],
        "probe_asns": list(range(51, 91)),
        "collector_asns": list(range(110, 122)),
        "noise_asns": [
            *range(130, 150),
            *range(151, 153),
            *range(154, 200),
            *range(206, 208),
        ],
    },
    "S1_5": {
        # 218 added AS roles plus the 4 core AS roles. With the route-view host
        # and two IX route servers this targets 225 live runtime containers.
        # This is the first intermediate tier between S1 and the guarded S2
        # prototype, and intentionally keeps a single external IX below /24
        # capacity instead of jumping to the 1023-container S2 layout.
        "transit_shard_asns": [],
        "probe_asns": [
            *range(51, 100),
            *range(102, 133),
        ],
        "collector_asns": list(range(133, 149)),
        "noise_asns": [
            *range(149, 200),
            *range(200, 250),
            *range(250, 255),
            *range(31, 47),
        ],
    },
    "S2": {
        # 996 scale AS roles plus ten S2 transit shards and the 4 core AS roles.
        # With the route-view host and twelve IX route servers this targets 1023
        # live runtime containers on a local Docker host. It is a guarded
        # prototype and not an accepted tier until normal/fault/recovery checks
        # pass on a prepared host or distributed runtime.
        "transit_shard_asns": list(range(210, 220)),
        "probe_asns": list(range(300, 660)),
        "collector_asns": list(range(700, 712)),
        "noise_asns": list(range(800, 1424)),
    },
}


HEALTH_GATE_SCRIPT = """\
#!/bin/sh
set -eu

STATUS_FILE=/var/run/meta-health-status
LOG_FILE=/var/log/meta-health-gate.log
BACKEND_IP="__BACKEND_IP__"
EXTERNAL_PEER="u_as10"
CHECK_INTERVAL="${CHECK_INTERVAL:-2}"
FAIL_THRESHOLD="${FAIL_THRESHOLD:-2}"

write_status() {
    printf "%s\\n" "$1" > "$STATUS_FILE"
}

write_log() {
    printf "%s %s\\n" "$(date -Is)" "$1" >> "$LOG_FILE"
}

set_external_peer() {
    action="$1"
    if [ "$action" = "withdraw" ]; then
        birdc dis "$EXTERNAL_PEER" >/tmp/meta-health-birdc.log 2>&1 || true
    else
        birdc en "$EXTERNAL_PEER" >/tmp/meta-health-birdc.log 2>&1 || true
    fi
}

probe_backend() {
    curl -fsS --max-time 1 "http://$BACKEND_IP/" >/dev/null 2>&1
}

wait_for_bird() {
    while ! birdc show status >/dev/null 2>&1; do
        sleep 1
    done
}

mkdir -p /var/run
: > "$LOG_FILE"
write_status "starting"
write_log "health gate starting; backend=$BACKEND_IP external_peer=$EXTERNAL_PEER"
wait_for_bird
write_log "bird control socket ready"

fail_count=0
last_state=unknown

while true; do
    if probe_backend; then
        fail_count=0
        if [ "$last_state" != "healthy" ]; then
            set_external_peer announce
            write_status healthy
            write_log "state=healthy backend_reachable=true action=announce_external_peer"
            last_state=healthy
        else
            write_status healthy
        fi
    else
        fail_count=$((fail_count + 1))
        if [ "$fail_count" -ge "$FAIL_THRESHOLD" ]; then
            if [ "$last_state" != "unhealthy" ]; then
                set_external_peer withdraw
                write_status unhealthy
                write_log "state=unhealthy backend_reachable=false action=withdraw_external_peer"
                last_state=unhealthy
            else
                write_status unhealthy
            fi
        else
            write_status "degraded:$fail_count"
            write_log "state=degraded backend_reachable=false fail_count=$fail_count"
        fi
    fi
    sleep "$CHECK_INTERVAL"
done
""".replace("__BACKEND_IP__", BACKEND_IP)


FAULT_SCRIPT = """\
#!/bin/sh
set -eu
LOG_FILE=/var/log/meta-recent-change.log
INTERNAL_PEER="c_as30"

write_log() {
    printf "%s %s\\n" "$(date -Is)" "$1" >> "$LOG_FILE"
}

case "${1:-}" in
    inject)
        birdc dis "$INTERNAL_PEER"
        write_log "inject internal path policy fault: disabled BGP peer $INTERNAL_PEER"
        ;;
    clear)
        birdc en "$INTERNAL_PEER"
        write_log "clear internal path policy fault: enabled BGP peer $INTERNAL_PEER"
        ;;
    status)
        birdc s p
        ;;
    *)
        echo "usage: $0 inject|clear|status" >&2
        exit 2
        ;;
esac
"""


CLIENT_PROBE_SCRIPT = """\
#!/bin/sh
set -eu
DOMAIN="__DOMAIN__"
RESOLVER="__RESOLVER_IP__"

echo "== dig =="
dig +time=2 +tries=1 @"$RESOLVER" "$DOMAIN" A
echo "== curl =="
curl -fsS --max-time 3 "http://$DOMAIN/"
""".replace("__DOMAIN__", FQDN).replace("__RESOLVER_IP__", RESOLVER_IP)


RESOLVER_FORWARDER_CONFIG = f"""\
zone "{DOMAIN}" {{ type forward; forward only; forwarders {{ {EDGE_DNS_IP}; }}; }};
"""


NAMED_DEFAULT_IPV4_SINGLE_WORKER = """\
RESOLVCONF=no
OPTIONS="-u bind -4 -n 1 -U 1"
"""


EDGE_NAMED_OPTIONS = f"""\
options {{
    directory "/var/cache/bind";
    recursion no;
    dnssec-validation no;
    empty-zones-enable no;
    allow-query {{ any; }};
    allow-update {{ any; }};
    listen-on port 53 {{ 127.0.0.1; {EDGE_DNS_IP}; {EDGE_SERVICE_IP}; {EDGE_ROUTER_NET_IP}; }};
    listen-on-v6 {{ none; }};
    minimal-responses yes;
}};
"""


RESOLVER_NAMED_OPTIONS = f"""\
options {{
    directory "/var/cache/bind";
    recursion yes;
    dnssec-validation no;
    empty-zones-enable no;
    allow-query {{ any; }};
    allow-recursion {{ any; }};
    allow-query-cache {{ any; }};
    listen-on port 53 {{ 127.0.0.1; {RESOLVER_IP}; 10.50.0.254; }};
    listen-on-v6 {{ none; }};
    minimal-responses yes;
}};
"""


def _canonical_tier(value):
    tier = value.upper()
    if tier in ("S1.5", "S1_5", "S15"):
        return "S1_5"
    return tier


def _parse_args():
    script_name = os.path.basename(__file__)
    platform = Platform.AMD64
    tier = "S0"
    supported_tiers = "S0|S1|S1.5|S2"
    if len(sys.argv) == 1:
        return platform, tier
    if len(sys.argv) in (2, 3):
        value = sys.argv[1].lower()
        if value in ("amd", "amd64"):
            platform = Platform.AMD64
        elif value in ("arm", "arm64"):
            platform = Platform.ARM64
        else:
            print(f"Usage: {script_name} [amd|arm] [{supported_tiers}]", file=sys.stderr)
            sys.exit(1)
        if len(sys.argv) == 3:
            tier = _canonical_tier(sys.argv[2])
            if tier not in RUNTIME_TIERS:
                print(f"Usage: {script_name} [amd|arm] [{supported_tiers}]", file=sys.stderr)
                sys.exit(1)
        return platform, tier
    print(f"Usage: {script_name} [amd|arm] [{supported_tiers}]", file=sys.stderr)
    sys.exit(1)


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        print(f"{name} must be an integer, got {value!r}", file=sys.stderr)
        sys.exit(2)


def _network_for_asn(asn):
    if asn < 256:
        return f"10.{asn}.0.0/24", f"10.{asn}.0.254"

    idx = asn - 256
    second = S2_LOCAL_AS_SECOND_BASE + (idx // 256)
    third = idx % 256
    if second > S2_LOCAL_AS_SECOND_LIMIT:
        raise ValueError(
            f"ASN {asn} is outside the local 10.{S2_LOCAL_AS_SECOND_BASE}.0.0/16-"
            f"10.{S2_LOCAL_AS_SECOND_LIMIT}.0.0/16 IPAM range"
        )
    return f"10.{second}.{third}.0/24", f"10.{second}.{third}.254"


def _ix_prefix_for_tier(tier, ix_id):
    if tier == "S2":
        return f"10.{S2_IX_SECOND}.{ix_id - 100}.0/24"
    return "auto"


def _ix_peer_address_for_tier(tier, ix_id, host_octet):
    if tier == "S2":
        return f"10.{S2_IX_SECOND}.{ix_id - 100}.{host_octet}"
    return None


def _external_ix_ids_for_tier(tier):
    if tier == "S2":
        return [100, *range(102, 112)]
    return [100]


def _scale_ix_ids_for_tier(tier):
    if tier == "S2":
        return list(range(102, 112))
    return [100]


def _scale_ix_assignment(tier, scale_index):
    ix_ids = _scale_ix_ids_for_tier(tier)
    ix_id = ix_ids[scale_index % len(ix_ids)]
    if tier == "S2":
        host_octet = 150 + (scale_index // len(ix_ids))
        if host_octet > 249:
            raise ValueError("S2 scale IX assignment exceeded 100 peers per IX")
        return ix_id, _ix_peer_address_for_tier(tier, ix_id, host_octet)
    return ix_id, None


def _scale_provider_asn_for_ix(tier, ix_id, shard_by_ix):
    if tier == "S2":
        return shard_by_ix[ix_id]
    return 10


def build_case(tier="S0"):
    tier = _canonical_tier(tier)
    if tier not in RUNTIME_TIERS:
        raise ValueError(f"unknown runtime tier {tier}")
    tier_cfg = RUNTIME_TIERS[tier]

    emu = Emulator()
    base = Base()
    routing = Routing()
    ebgp = Ebgp()
    ibgp = Ibgp()
    ospf = Ospf()

    external_ix_ids = _external_ix_ids_for_tier(tier)
    for ix_id in external_ix_ids:
        ix = base.createInternetExchange(ix_id, prefix=_ix_prefix_for_tier(tier, ix_id))
        ix.getPeeringLan().setDisplayName("External IX" if ix_id == 100 else f"S2 External IX {ix_id}")

    ix101 = base.createInternetExchange(101, prefix=_ix_prefix_for_tier(tier, 101))
    ix101.getPeeringLan().setDisplayName("Internal Backbone IX")

    transit_as = base.createAutonomousSystem(10)
    transit_as.createNetwork("net0", "10.10.0.0/24")
    transit_router = transit_as.createRouter("r100").joinNetwork("net0")
    for ix_id in external_ix_ids:
        transit_router.joinNetwork(f"ix{ix_id}")
    route_view = transit_as.createHost("route-view").joinNetwork("net0", address="10.10.0.100")
    route_view.setDisplayName("External Route View")

    shard_by_ix = {}
    for ix_id, shard_asn in zip(_scale_ix_ids_for_tier(tier), tier_cfg["transit_shard_asns"]):
        prefix, router_ip = _network_for_asn(shard_asn)
        shard_as = base.createAutonomousSystem(shard_asn)
        shard_as.createNetwork("net0", prefix)
        shard_router = shard_as.createRouter("shard-router")
        shard_router.joinNetwork("net0", address=router_ip)
        ix_address = _ix_peer_address_for_tier(tier, ix_id, 20)
        shard_router.joinNetwork(f"ix{ix_id}", address=ix_address) if ix_address else shard_router.joinNetwork(f"ix{ix_id}")
        shard_router.setDisplayName(f"S2 Transit Shard Router {shard_asn}")
        shard_router.setLabel("benchmark.roles", "s2-transit-shard")
        shard_by_ix[ix_id] = shard_asn
        ebgp.addPrivatePeering(ix_id, 10, shard_asn, abRelationship=PeerRelationship.Provider)

    edge_as = base.createAutonomousSystem(20)
    edge_as.createNetwork("edge-net", "10.20.0.0/24")
    edge_router = edge_as.createRouter("edge-router")
    edge_router.joinNetwork("edge-net", address=EDGE_ROUTER_NET_IP).joinNetwork("ix100").joinNetwork("ix101")
    edge_router.setDisplayName("Edge Health Gate Router")
    edge_router.addSoftware("curl")
    edge_router.appendStartCommand(f"ip addr add {EDGE_DNS_IP}/32 dev lo || true")
    edge_router.appendStartCommand(f"ip addr add {EDGE_SERVICE_IP}/32 dev lo || true")
    edge_router.setFile("/usr/local/bin/meta-health-gate.sh", HEALTH_GATE_SCRIPT)
    edge_router.setFile("/usr/local/bin/meta-backbone-fault.sh", FAULT_SCRIPT)
    edge_router.setFile("/usr/local/share/meta-edge-named-options.conf", EDGE_NAMED_OPTIONS)
    edge_router.setFile("/etc/default/named", NAMED_DEFAULT_IPV4_SINGLE_WORKER)
    edge_router.appendStartCommand("chmod +x /usr/local/bin/meta-health-gate.sh /usr/local/bin/meta-backbone-fault.sh")
    edge_router.appendStartCommand("cp /usr/local/share/meta-edge-named-options.conf /etc/bind/named.conf.options")
    edge_router.appendStartCommand("CHECK_INTERVAL=2 FAIL_THRESHOLD=2 /usr/local/bin/meta-health-gate.sh", fork=True)
    edge_router.setLabel(
        "benchmark.roles",
        "edge-health-gate,edge-authoritative-dns,edge-service-entry",
    )

    dc_as = base.createAutonomousSystem(30)
    dc_as.createNetwork("dc-net", "10.30.0.0/24")
    dc_router = dc_as.createRouter("dc-router")
    dc_router.joinNetwork("dc-net").joinNetwork("ix101")
    dc_router.setDisplayName("DC Backend Router")
    dc_router.appendStartCommand(f"ip addr add {BACKEND_IP}/32 dev lo || true")
    dc_router.setLabel("benchmark.role", "dc-backend")

    client_as = base.createAutonomousSystem(50)
    client_as.createNetwork("net0", "10.50.0.0/24")
    client_router = client_as.createRouter("client-router")
    client_router.joinNetwork("net0").joinNetwork("ix100")
    client_router.addSoftware("curl")
    client_router.appendStartCommand(f"ip addr add {RESOLVER_IP}/32 dev lo || true")
    client_router.setFile("/usr/local/bin/meta-client-probe.sh", CLIENT_PROBE_SCRIPT)
    client_router.setFile("/usr/local/share/meta-resolver-forward.conf", RESOLVER_FORWARDER_CONFIG)
    client_router.setFile("/usr/local/share/meta-resolver-named-options.conf", RESOLVER_NAMED_OPTIONS)
    client_router.setFile("/etc/default/named", NAMED_DEFAULT_IPV4_SINGLE_WORKER)
    client_router.appendStartCommand("chmod +x /usr/local/bin/meta-client-probe.sh")
    client_router.appendStartCommand("cp /usr/local/share/meta-resolver-named-options.conf /etc/bind/named.conf.options")
    client_router.appendStartCommand("cp /usr/local/share/meta-resolver-forward.conf /etc/bind/named.conf.local")
    client_router.setLabel("benchmark.roles", "external-client-probe,recursive-resolver")

    scale_index = 0

    for asn in tier_cfg["probe_asns"]:
        prefix, router_ip = _network_for_asn(asn)
        ix_id, ix_address = _scale_ix_assignment(tier, scale_index)
        scale_index += 1
        probe_as = base.createAutonomousSystem(asn)
        probe_as.createNetwork("net0", prefix)
        probe_router = probe_as.createRouter("probe-router")
        probe_router.joinNetwork("net0", address=router_ip)
        probe_router.joinNetwork(f"ix{ix_id}", address=ix_address) if ix_address else probe_router.joinNetwork(f"ix{ix_id}")
        probe_router.setDisplayName(f"Scale Probe Router {asn}")
        probe_router.addSoftware("curl")
        probe_router.addSoftware("dnsutils")
        probe_router.appendStartCommand(f"printf 'nameserver {RESOLVER_IP}\\n' > /etc/resolv.conf")
        probe_router.setFile("/usr/local/bin/meta-client-probe.sh", CLIENT_PROBE_SCRIPT)
        probe_router.appendStartCommand("chmod +x /usr/local/bin/meta-client-probe.sh")
        probe_router.setLabel("benchmark.roles", f"{tier.lower()}-external-probe")
        ebgp.addPrivatePeering(ix_id, _scale_provider_asn_for_ix(tier, ix_id, shard_by_ix), asn, abRelationship=PeerRelationship.Provider)

    for asn in tier_cfg["collector_asns"]:
        prefix, router_ip = _network_for_asn(asn)
        ix_id, ix_address = _scale_ix_assignment(tier, scale_index)
        scale_index += 1
        collector_as = base.createAutonomousSystem(asn)
        collector_as.createNetwork("net0", prefix)
        collector_router = collector_as.createRouter("collector-router")
        collector_router.joinNetwork("net0", address=router_ip)
        collector_router.joinNetwork(f"ix{ix_id}", address=ix_address) if ix_address else collector_router.joinNetwork(f"ix{ix_id}")
        collector_router.setDisplayName(f"Scale Route Collector {asn}")
        collector_router.setLabel("benchmark.roles", f"{tier.lower()}-route-collector")
        ebgp.addPrivatePeering(ix_id, _scale_provider_asn_for_ix(tier, ix_id, shard_by_ix), asn, abRelationship=PeerRelationship.Provider)

    for asn in tier_cfg["noise_asns"]:
        prefix, router_ip = _network_for_asn(asn)
        ix_id, ix_address = _scale_ix_assignment(tier, scale_index)
        scale_index += 1
        noise_as = base.createAutonomousSystem(asn)
        noise_as.createNetwork("net0", prefix)
        noise_router = noise_as.createRouter("noise-router")
        noise_router.joinNetwork("net0", address=router_ip)
        noise_router.joinNetwork(f"ix{ix_id}", address=ix_address) if ix_address else noise_router.joinNetwork(f"ix{ix_id}")
        noise_router.setDisplayName(f"Scale Noise Router {asn}")
        noise_router.setLabel("benchmark.roles", f"{tier.lower()}-background-noise")
        ebgp.addPrivatePeering(ix_id, _scale_provider_asn_for_ix(tier, ix_id, shard_by_ix), asn, abRelationship=PeerRelationship.Provider)

    web = WebService()
    web.install("edge-service-web").setIndexContent(
        "meta-style edge entry reachable from {nodeName} in AS{asn}\\n"
    ).setServerNames([FQDN])
    web.install("dc-backend-web").setIndexContent(
        "meta-style backend dependency healthy at {nodeName} in AS{asn}\\n"
    )

    dns = DomainNameService()
    dns.install("edge-auth").addZone(DOMAIN, createNsAndSoa=False).setMaster()
    dns.getZone(DOMAIN).addRecord("$TTL 1")
    dns.getZone(DOMAIN).addRecord("@ A {}".format(EDGE_SERVICE_IP))
    dns.getZone(DOMAIN).addRecord("www A {}".format(EDGE_SERVICE_IP))
    dns.getZone(DOMAIN).addRecord("@ SOA ns1.{} admin.{} 1 900 900 1800 60".format(DOMAIN, DOMAIN))
    dns.getZone(DOMAIN).addRecord("ns1.{} A {}".format(DOMAIN, EDGE_DNS_IP))
    dns.getZone(DOMAIN).addRecord("@ NS ns1.{}".format(DOMAIN))

    ldns = DomainNameCachingService(autoRoot=False)
    ldns_server = ldns.install("recursive-resolver")
    ldns_server.setNameServerOnNodesByAsns([50])

    ebgp.addPrivatePeering(100, 10, 20, abRelationship=PeerRelationship.Provider)
    ebgp.addPrivatePeering(100, 10, 50, abRelationship=PeerRelationship.Provider)
    ebgp.addPrivatePeering(101, 20, 30, abRelationship=PeerRelationship.Provider)

    emu.addLayer(base)
    emu.addLayer(routing)
    emu.addLayer(ebgp)
    emu.addLayer(ibgp)
    emu.addLayer(ospf)
    emu.addLayer(web)
    emu.addLayer(dns)
    emu.addLayer(ldns)

    emu.addBinding(Binding("edge-service-web", filter=Filter(asn=20, nodeName="edge-router", allowBound=True), action=Action.FIRST))
    emu.addBinding(Binding("dc-backend-web", filter=Filter(asn=30, nodeName="dc-router"), action=Action.FIRST))
    emu.addBinding(Binding("edge-auth", filter=Filter(asn=20, nodeName="edge-router", allowBound=True), action=Action.FIRST))
    emu.addBinding(Binding("recursive-resolver", filter=Filter(asn=50, nodeName="client-router", allowBound=True), action=Action.FIRST))

    return emu, [edge_router, dc_router, client_router]


def build_emulator() -> Emulator:
    emu, _ = build_case()
    return emu


def _router_service_image(platform: Platform) -> DockerImage:
    if platform == Platform.ARM64:
        image_name = ROUTER_SERVICE_IMAGE_ARM
        image_dir = CASE_DIR / "router-service-image-arm"
        subset = ROUTER_IMAGE_ARM64
    else:
        image_name = ROUTER_SERVICE_IMAGE_AMD
        image_dir = CASE_DIR / "router-service-image-amd"
        subset = ROUTER_IMAGE

    return DockerImage(
        image_name,
        ["bind9", "nginx-light"],
        local=True,
        dirName=os.path.relpath(image_dir, OUTPUT_DIR),
        subset=subset,
    )


def run(dumpfile=None):
    platform, tier = _parse_args()
    emu, service_routers = build_case(tier)
    if dumpfile is not None:
        emu.dump(dumpfile)
        return

    emu.render()
    internet_map_enabled = _env_flag("B51_ENABLE_INTERNET_MAP")
    internet_map_port = _env_int("B51_INTERNET_MAP_PORT", 8080)
    docker = Docker(
        platform=platform,
        namingScheme=f"{CONTAINER_PREFIX}as{{asn}}{{role}}-{{displayName}}-{{primaryIp}}",
        internetMapEnabled=False,
    )
    if internet_map_enabled:
        docker.attachInternetMap(
            port_forwarding=f"{internet_map_port}:8080/tcp",
            env=["CONSOLE=true"],
            node_name=INTERNET_MAP_CONTAINER,
        )
    router_service_image = _router_service_image(platform)
    docker.addImage(router_service_image, priority=0)
    for router in service_routers:
        docker.setImageOverride(router, router_service_image.getName())
    emu.compile(docker, str(OUTPUT_DIR), override=True)


if __name__ == "__main__":
    run()
