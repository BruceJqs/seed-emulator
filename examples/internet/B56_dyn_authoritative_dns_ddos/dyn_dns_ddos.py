#!/usr/bin/env python3
import os
import sys
from pathlib import Path

from seedemu.compiler import Docker, DockerImage, Platform, ROUTER_IMAGE, ROUTER_IMAGE_ARM64
from seedemu.core import Action, Binding, Emulator, Filter
from seedemu.layers import Base, Ebgp, Ibgp, Ospf, PeerRelationship, Routing
from seedemu.services import DomainNameCachingService, DomainNameService


CASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = CASE_DIR / "output"
CONTAINER_PREFIX = os.environ.get("B56_CONTAINER_PREFIX", "b56-")
ROUTER_IMAGE_AMD = "b56-router-dns-base-amd"
ROUTER_IMAGE_ARM = "b56-router-dns-base-arm"

DOMAIN = "customer-a.test."
FQDN = "www.customer-a.test"
SECONDARY_DOMAIN = "customer-b.test."
SECONDARY_FQDN = "www.customer-b.test"
DYNAUTH_IP = "10.56.10.53"
SECONDARY_AUTH_IP = "10.56.20.53"
RESOLVER_IP = "10.56.30.53"
ORIGIN_IP = "10.56.40.80"


RUNTIME_TIERS = {
    "S0": {"client_asns": [80, 81, 82], "bot_asns": [120, 121, 122, 123], "collector_asns": [150], "noise_asns": []},
    "S1": {"client_asns": list(range(80, 132)), "bot_asns": list(range(132, 188)), "collector_asns": list(range(188, 198)), "noise_asns": list(range(198, 230)) + [230, 231]},
    "S1_5": {"client_asns": list(range(80, 145)), "bot_asns": list(range(145, 215)), "collector_asns": list(range(215, 231)), "noise_asns": list(range(231, 250)) + [251, 252]},
    "S2": {"client_asns": list(range(80, 180)), "bot_asns": list(range(180, 245)), "collector_asns": list(range(245, 255)), "noise_asns": [60, 61]},
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


RUNTIME_TIERS["S1"]["client_asns"] = _asn_range(80, 132, fill_to=52, fill_start=250)
RUNTIME_TIERS["S1_5"]["client_asns"] = _asn_range(80, 145, fill_to=65, fill_start=250)
RUNTIME_TIERS["S2"]["client_asns"] = _asn_range(80, 180, fill_to=100, fill_start=255)


NAMED_DEFAULT_IPV4_SINGLE_WORKER = """\
RESOLVCONF=no
OPTIONS="-u bind -4 -n 1 -U 1"
"""


DYNAUTH_NAMED_OPTIONS = f"""\
options {{
    directory "/var/cache/bind";
    recursion no;
    dnssec-validation no;
    empty-zones-enable no;
    allow-query {{ any; }};
    allow-update {{ any; }};
    listen-on port 53 {{ 127.0.0.1; {DYNAUTH_IP}; 10.56.10.254; }};
    listen-on-v6 {{ none; }};
    minimal-responses yes;
}};
"""


SECONDARY_NAMED_OPTIONS = f"""\
options {{
    directory "/var/cache/bind";
    recursion no;
    dnssec-validation no;
    empty-zones-enable no;
    allow-query {{ any; }};
    allow-update {{ any; }};
    listen-on port 53 {{ 127.0.0.1; {SECONDARY_AUTH_IP}; 10.56.20.254; }};
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
    listen-on port 53 {{ 127.0.0.1; {RESOLVER_IP}; 10.56.30.254; }};
    listen-on-v6 {{ none; }};
    minimal-responses yes;
}};
"""


RESOLVER_FORWARDER_CONFIG = f"""\
zone "{DOMAIN}" {{ type forward; forward only; forwarders {{ {DYNAUTH_IP}; }}; }};
zone "{SECONDARY_DOMAIN}" {{ type forward; forward only; forwarders {{ {SECONDARY_AUTH_IP}; }}; }};
"""


DYNAUTH_CONTROL_SCRIPT = """\
#!/bin/sh
set -eu
LOG=/var/log/b56-dyn-ddos.log
DYNAUTH_IP="__DYNAUTH_IP__"
BOT_CIDR="10.145.0.0/16"

write_log() {
    printf "%s %s\\n" "$(date -Is)" "$1" >> "$LOG"
}

case "${1:-}" in
    inject)
        iptables -I INPUT -p udp --dport 53 -d "$DYNAUTH_IP" -j DROP || true
        iptables -I INPUT -p tcp --dport 53 -d "$DYNAUTH_IP" -j REJECT || true
        write_log "fault injected: authoritative path overloaded; fresh lookups to Dyn anycast DNS are dropped"
        ;;
    scrub)
        iptables -D INPUT -p udp --dport 53 -d "$DYNAUTH_IP" -j DROP 2>/dev/null || true
        iptables -D INPUT -p tcp --dport 53 -d "$DYNAUTH_IP" -j REJECT 2>/dev/null || true
        write_log "mitigation applied: scrubber/rate-limit simulation removed broad authoritative drop"
        ;;
    status)
        printf '== iptables ==\\n'
        iptables -S INPUT 2>&1 || true
        printf '\\n== named process ==\\n'
        pgrep -a named 2>&1 || true
        printf '\\n== local auth query ==\\n'
        dig +short +time=1 +tries=1 @"$DYNAUTH_IP" __FQDN__ A 2>&1 || true
        ;;
    *)
        echo "usage: $0 inject|scrub|status" >&2
        exit 2
        ;;
esac
""".replace("__DYNAUTH_IP__", DYNAUTH_IP).replace("__FQDN__", FQDN)


BOT_SCRIPT = """\
#!/bin/sh
set -eu
TARGET="__DYNAUTH_IP__"
QNAME="__FQDN__"
LOG=/var/log/b56-bot-traffic.log
case "${1:-}" in
    burst)
        count="${2:-30}"
        i=0
        while [ "$i" -lt "$count" ]; do
            dig +time=1 +tries=1 @"$TARGET" "$QNAME" A >/dev/null 2>&1 || true
            i=$((i + 1))
        done
        printf "%s sent %s synthetic DNS queries to %s\\n" "$(date -Is)" "$count" "$TARGET" >> "$LOG"
        ;;
    *)
        echo "usage: $0 burst [count]" >&2
        exit 2
        ;;
esac
""".replace("__DYNAUTH_IP__", DYNAUTH_IP).replace("__FQDN__", FQDN)


ORIGIN_ROUTER_HTTP_SCRIPT = """\
#!/bin/sh
set -eu
VIP="__ORIGIN_IP__"
LOG=/var/log/b56-origin-router-http.log
ip addr add "$VIP/32" dev lo 2>/dev/null || true
while true; do
    body="B56 customer origin is healthy; DNS authoritative reachability is the incident domain.\\n"
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
""".replace("__ORIGIN_IP__", ORIGIN_IP)


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
            raise SystemExit("usage: dyn_dns_ddos.py [amd|arm] [S0|S1|S1.5|S2]")
    if len(sys.argv) > 2:
        tier = _canonical_tier(sys.argv[2])
        if tier not in RUNTIME_TIERS:
            raise SystemExit("usage: dyn_dns_ddos.py [amd|arm] [S0|S1|S1.5|S2]")
    if len(sys.argv) > 3:
        raise SystemExit("usage: dyn_dns_ddos.py [amd|arm] [S0|S1|S1.5|S2]")
    return platform, tier


def _router_as(base: Base, asn: int, prefix: str, router_ip: str, ix_ip: str, display: str):
    asys = base.createAutonomousSystem(asn)
    asys.createNetwork("net0", prefix)
    router = asys.createRouter("router")
    router.joinNetwork("net0", address=router_ip).joinNetwork("ix100", address=ix_ip)
    router.setDisplayName(display)
    router.addSoftware("curl")
    router.addSoftware("dnsutils")
    return asys, router


def build_case(tier: str):
    cfg = RUNTIME_TIERS[tier]
    emu = Emulator()
    base = Base()
    routing = Routing()
    ebgp = Ebgp()
    ibgp = Ibgp()
    ospf = Ospf()

    base.createInternetExchange(100)

    _, transit_router = _router_as(base, 50, "10.56.50.0/24", "10.56.50.254", "10.100.0.50", "Internet Transit Router")

    dyn_as, dyn_router = _router_as(base, 56, "10.56.10.0/24", "10.56.10.254", "10.100.0.56", "Dyn Anycast Authoritative DNS Router")
    dyn_router.appendStartCommand(f"ip addr add {DYNAUTH_IP}/32 dev lo || true")
    dyn_router.setFile("/usr/local/share/b56-dyn-named-options.conf", DYNAUTH_NAMED_OPTIONS)
    dyn_router.setFile("/etc/default/named", NAMED_DEFAULT_IPV4_SINGLE_WORKER)
    dyn_router.setFile("/usr/local/bin/b56-dyn-ddos-control.sh", DYNAUTH_CONTROL_SCRIPT)
    dyn_router.appendStartCommand("chmod +x /usr/local/bin/b56-dyn-ddos-control.sh")
    dyn_router.appendStartCommand("cp /usr/local/share/b56-dyn-named-options.conf /etc/bind/named.conf.options")

    sec_as, secondary_router = _router_as(base, 57, "10.56.20.0/24", "10.56.20.254", "10.100.0.57", "Secondary Authoritative DNS Router")
    secondary_router.appendStartCommand(f"ip addr add {SECONDARY_AUTH_IP}/32 dev lo || true")
    secondary_router.setFile("/usr/local/share/b56-secondary-named-options.conf", SECONDARY_NAMED_OPTIONS)
    secondary_router.setFile("/etc/default/named", NAMED_DEFAULT_IPV4_SINGLE_WORKER)
    secondary_router.appendStartCommand("cp /usr/local/share/b56-secondary-named-options.conf /etc/bind/named.conf.options")

    resolver_as, resolver_router = _router_as(base, 58, "10.56.30.0/24", "10.56.30.254", "10.100.0.58", "Recursive Resolver Router")
    resolver_router.appendStartCommand(f"ip addr add {RESOLVER_IP}/32 dev lo || true")
    resolver_router.setFile("/usr/local/share/b56-resolver-forward.conf", RESOLVER_FORWARDER_CONFIG)
    resolver_router.setFile("/usr/local/share/b56-resolver-named-options.conf", RESOLVER_NAMED_OPTIONS)
    resolver_router.setFile("/etc/default/named", NAMED_DEFAULT_IPV4_SINGLE_WORKER)
    resolver_router.appendStartCommand("cp /usr/local/share/b56-resolver-named-options.conf /etc/bind/named.conf.options")
    resolver_router.appendStartCommand("cp /usr/local/share/b56-resolver-forward.conf /etc/bind/named.conf.local")

    _, origin_router = _router_as(base, 59, "10.56.40.0/24", "10.56.40.254", "10.100.0.59", "Customer Origin Router")
    origin_router.setFile("/usr/local/bin/b56-origin-router-http.sh", ORIGIN_ROUTER_HTTP_SCRIPT)
    origin_router.appendStartCommand("chmod +x /usr/local/bin/b56-origin-router-http.sh")
    origin_router.appendStartCommand("/usr/local/bin/b56-origin-router-http.sh", fork=True)

    for asn in [56, 57, 58, 59]:
        ebgp.addPrivatePeering(100, 50, asn, abRelationship=PeerRelationship.Provider)

    for asn in cfg["client_asns"]:
        _, router = _router_as(base, asn, f"10.{asn}.0.0/24", f"10.{asn}.0.254", f"10.100.0.{asn}", f"Client Probe Router {asn}")
        router.appendStartCommand(f"printf 'nameserver {RESOLVER_IP}\\n' > /etc/resolv.conf")
        ebgp.addPrivatePeering(100, 50, asn, abRelationship=PeerRelationship.Provider)

    for asn in cfg["bot_asns"]:
        _, router = _router_as(base, asn, f"10.{asn}.0.0/24", f"10.{asn}.0.254", f"10.100.0.{asn}", f"Botnet IoT Router {asn}")
        router.setFile("/usr/local/bin/b56-bot-query.sh", BOT_SCRIPT)
        router.appendStartCommand("chmod +x /usr/local/bin/b56-bot-query.sh")
        ebgp.addPrivatePeering(100, 50, asn, abRelationship=PeerRelationship.Provider)

    for asn in cfg["collector_asns"]:
        _router_as(base, asn, f"10.{asn}.0.0/24", f"10.{asn}.0.254", f"10.100.0.{asn}", f"DNS Route Collector Router {asn}")
        ebgp.addPrivatePeering(100, 50, asn, abRelationship=PeerRelationship.Provider)

    for asn in cfg["noise_asns"]:
        _router_as(base, asn, f"10.{asn}.0.0/24", f"10.{asn}.0.254", f"10.100.0.{asn}", f"Background Router {asn}")
        ebgp.addPrivatePeering(100, 50, asn, abRelationship=PeerRelationship.Provider)

    dns = DomainNameService()
    dns.install("dyn-auth").addZone(DOMAIN, createNsAndSoa=False).setMaster()
    dns.getZone(DOMAIN).addRecord("$TTL 30")
    dns.getZone(DOMAIN).addRecord(f"@ A {ORIGIN_IP}")
    dns.getZone(DOMAIN).addRecord(f"www A {ORIGIN_IP}")
    dns.getZone(DOMAIN).addRecord(f"@ SOA ns1.{DOMAIN} admin.{DOMAIN} 1 30 30 60 30")
    dns.getZone(DOMAIN).addRecord(f"ns1.{DOMAIN} A {DYNAUTH_IP}")
    dns.getZone(DOMAIN).addRecord(f"@ NS ns1.{DOMAIN}")

    dns.install("secondary-auth").addZone(SECONDARY_DOMAIN, createNsAndSoa=False).setMaster()
    dns.getZone(SECONDARY_DOMAIN).addRecord("$TTL 30")
    dns.getZone(SECONDARY_DOMAIN).addRecord(f"@ A {ORIGIN_IP}")
    dns.getZone(SECONDARY_DOMAIN).addRecord(f"www A {ORIGIN_IP}")
    dns.getZone(SECONDARY_DOMAIN).addRecord(f"@ SOA ns1.{SECONDARY_DOMAIN} admin.{SECONDARY_DOMAIN} 1 30 30 60 30")
    dns.getZone(SECONDARY_DOMAIN).addRecord(f"ns1.{SECONDARY_DOMAIN} A {SECONDARY_AUTH_IP}")
    dns.getZone(SECONDARY_DOMAIN).addRecord(f"@ NS ns1.{SECONDARY_DOMAIN}")

    ldns = DomainNameCachingService(autoRoot=False)
    ldns.install("recursive-resolver").setNameServerOnNodesByAsns([58])

    emu.addLayer(base)
    emu.addLayer(routing)
    emu.addLayer(ebgp)
    emu.addLayer(ibgp)
    emu.addLayer(ospf)
    emu.addLayer(dns)
    emu.addLayer(ldns)

    emu.addBinding(Binding("dyn-auth", filter=Filter(asn=56, nodeName="router", allowBound=True), action=Action.FIRST))
    emu.addBinding(Binding("secondary-auth", filter=Filter(asn=57, nodeName="router", allowBound=True), action=Action.FIRST))
    emu.addBinding(Binding("recursive-resolver", filter=Filter(asn=58, nodeName="router", allowBound=True), action=Action.FIRST))
    return emu, [dyn_router, secondary_router, resolver_router]


def _router_dns_image(platform: Platform) -> DockerImage:
    if platform == Platform.ARM64:
        return DockerImage(ROUTER_IMAGE_ARM, ["bind9", "nginx-light", "iptables"], local=True, dirName=os.path.relpath(CASE_DIR / "router-dns-image-arm", OUTPUT_DIR), subset=ROUTER_IMAGE_ARM64)
    return DockerImage(ROUTER_IMAGE_AMD, ["bind9", "nginx-light", "iptables"], local=True, dirName=os.path.relpath(CASE_DIR / "router-dns-image-amd", OUTPUT_DIR), subset=ROUTER_IMAGE)


def run():
    platform, tier = _parse_args()
    emu, service_routers = build_case(tier)
    emu.render()
    docker = Docker(
        platform=platform,
        namingScheme=f"{CONTAINER_PREFIX}as{{asn}}{{role}}-{{displayName}}-{{primaryIp}}",
        internetMapEnabled=False,
    )
    router_dns_image = _router_dns_image(platform)
    docker.addImage(router_dns_image, priority=0)
    for router in service_routers:
        docker.setImageOverride(router, router_dns_image.getName())
    emu.compile(docker, str(OUTPUT_DIR), override=True)


if __name__ == "__main__":
    run()
