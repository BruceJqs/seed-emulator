#!/usr/bin/env python
"""
Routing trust component-family blueprint.

This file is intentionally a direct-component sketch for the second project
lane. It reuses SEED-native services and routing layers instead of inheriting a
whole teaching example layout.
"""

from __future__ import annotations

import os
import sys

from seedemu.compiler import Docker, Platform
from seedemu.core import Binding, Emulator, Filter, Hook
from seedemu.layers import Base, Ebgp, Ibgp, Ospf, PeerRelationship, Routing
from seedemu.services import BgpLookingGlassService, ExaBgpService, WebService


# Keep the first blueprint inside the simple auto-addressing range so the
# earliest compile check exercises component composition instead of advanced
# prefix allocation concerns.
ATTACKER_ASN = 30
SERVICE_ASN = 31
CLIENT_ASN = 32
OBSERVER_ASN = 33
TRANSIT_ASN = 34
# Keep IX ids within the simple built-in range so the first direct-component
# compile does not depend on extra route-server address wiring.
# Keep this lane off the already-active strict-v2 IX ranges to avoid pool
# overlap when multiple Foundry runtimes are up at the same time.
IX_ATTACK = 240
IX_SERVICE = 241
IX_CLIENT = 242
SERVICE_PREFIX = "198.51.100.0/24"
EVENT_PORT = int(os.environ.get("ROUTING_TRUST_EVENT_PORT", "5701"))
LOOKING_GLASS_PORT = int(os.environ.get("ROUTING_TRUST_LG_PORT", "5702"))
ATTACK_PREFIX = os.environ.get("ROUTING_TRUST_ATTACK_PREFIX", "").strip()

HIJACK_STATIC_TEMPLATE = """\
    ipv4 {{
        table t_hijack;
    }};
{routes}
"""


class RoutingTrustHijackHook(Hook):
    def __init__(self, attacker_router, attack_prefix: str):
        self._attacker_router = attacker_router
        self._attack_prefix = attack_prefix

    def getName(self) -> str:
        return "RoutingTrustHijackInjector"

    def getTargetLayer(self) -> str:
        return "Ebgp"

    def postrender(self, emulator: Emulator):
        router = self._attacker_router
        router.addTable("t_hijack")
        router.addTablePipe(
            "t_hijack",
            "t_bgp",
            exportFilter="filter { bgp_large_community.add(LOCAL_COMM); bgp_local_pref = 40; accept; }",
        )
        router.addProtocol(
            "static",
            "hijacks",
            HIJACK_STATIC_TEMPLATE.format(routes=f"    route {self._attack_prefix} blackhole;\n"),
        )


def resolve_platform() -> Platform:
    if len(sys.argv) == 1:
        return Platform.AMD64
    if len(sys.argv) == 2:
        flag = sys.argv[1].lower()
        if flag == "amd":
            return Platform.AMD64
        if flag == "arm":
            return Platform.ARM64
    raise SystemExit(f"Usage: {os.path.basename(__file__)} [amd|arm]")


def create_topology(base: Base) -> dict[str, object]:
    base.createInternetExchange(IX_ATTACK).getPeeringLan().setDisplayName("routing-trust-attack-ix")
    base.createInternetExchange(IX_SERVICE).getPeeringLan().setDisplayName("routing-trust-service-ix")
    base.createInternetExchange(IX_CLIENT).getPeeringLan().setDisplayName("routing-trust-client-ix")

    transit = base.createAutonomousSystem(TRANSIT_ASN)
    transit.createNetwork("core_net")
    transit_router = transit.createRouter("r-core")
    transit_router.joinNetwork("core_net")
    transit_router.joinNetwork(f"ix{IX_ATTACK}")
    transit_router.joinNetwork(f"ix{IX_SERVICE}")
    transit_router.joinNetwork(f"ix{IX_CLIENT}")

    attacker = base.createAutonomousSystem(ATTACKER_ASN)
    attacker.createNetwork("net0")
    attacker_router = attacker.createRouter("r-attacker")
    attacker_router.joinNetwork("net0")
    attacker_router.joinNetwork(f"ix{IX_ATTACK}")
    attacker_host = attacker.createHost("event-viewer")
    attacker_host.joinNetwork("net0")
    attacker_host.addPortForwarding(EVENT_PORT, 5000)

    service = base.createAutonomousSystem(SERVICE_ASN)
    service.createNetwork("net0")
    service_router = service.createRouter("r-service")
    service_router.joinNetwork("net0")
    service_router.joinNetwork(f"ix{IX_SERVICE}")
    service_host = service.createHost("service-app")
    service_host.joinNetwork("net0")

    client = base.createAutonomousSystem(CLIENT_ASN)
    client.createNetwork("net0")
    client_router = client.createRouter("r-client")
    client_router.joinNetwork("net0")
    client_router.joinNetwork(f"ix{IX_CLIENT}")
    client_host = client.createHost("client-probe")
    client_host.joinNetwork("net0")

    observer = base.createAutonomousSystem(OBSERVER_ASN)
    observer.createNetwork("net0")
    observer_router = observer.createRouter("r-observer")
    observer_router.joinNetwork("net0")
    observer_router.joinNetwork(f"ix{IX_ATTACK}")
    observer_host = observer.createHost("looking-glass")
    observer_host.joinNetwork("net0")
    observer_host.addPortForwarding(LOOKING_GLASS_PORT, 5000)

    return {
        "transit_router": transit_router,
        "attacker_router": attacker_router,
        "attacker_host": attacker_host,
        "service_router": service_router,
        "service_host": service_host,
        "client_router": client_router,
        "client_host": client_host,
        "observer_router": observer_router,
        "observer_host": observer_host,
    }


def configure_peerings(ebgp: Ebgp) -> None:
    ebgp.addPrivatePeering(IX_ATTACK, TRANSIT_ASN, ATTACKER_ASN, abRelationship=PeerRelationship.Provider)
    ebgp.addPrivatePeering(IX_ATTACK, TRANSIT_ASN, OBSERVER_ASN, abRelationship=PeerRelationship.Provider)
    ebgp.addPrivatePeering(IX_SERVICE, TRANSIT_ASN, SERVICE_ASN, abRelationship=PeerRelationship.Provider)
    ebgp.addPrivatePeering(IX_CLIENT, TRANSIT_ASN, CLIENT_ASN, abRelationship=PeerRelationship.Provider)


def install_control_plane(emu: Emulator) -> None:
    exabgp = ExaBgpService()
    viewer = exabgp.install("routing_trust_bgp_events")
    viewer.attachToRouter("r-attacker")
    viewer.setLocalAsn(65199)
    # Keep the dashboard on the service's default container port and use host
    # port forwarding for the external access point.
    viewer.enableDashboard(5000)
    emu.addBinding(Binding("routing_trust_bgp_events", filter=Filter(nodeName="event-viewer", asn=ATTACKER_ASN)))
    emu.addLayer(exabgp)


def install_observability(emu: Emulator) -> None:
    looking_glass = BgpLookingGlassService()
    lg = looking_glass.install("routing_trust_lg")
    lg.attach("r-observer")
    lg.setFrontendPort(5000)
    lg.setProxyPort(8000)
    emu.addBinding(Binding("routing_trust_lg", filter=Filter(nodeName="looking-glass", asn=OBSERVER_ASN)))
    emu.addLayer(looking_glass)


def install_service_surface(emu: Emulator) -> None:
    web = WebService()
    server = web.install("routing_trust_service_web")
    server.setServerNames(["routing-trust.service.local"])
    server.setIndexContent(
        "<h1>routing trust component blueprint</h1>"
        "<p>Direct-component service surface for the second Foundry lane.</p>"
    )
    emu.addBinding(Binding("routing_trust_service_web", filter=Filter(nodeName="service-app", asn=SERVICE_ASN)))
    emu.addLayer(web)


def build_emulator() -> Emulator:
    emu = Emulator()
    base = Base()
    routing = Routing()
    ebgp = Ebgp()
    role_nodes = create_topology(base)
    configure_peerings(ebgp)

    emu.addLayer(base)
    emu.addLayer(routing)
    emu.addLayer(ebgp)
    emu.addLayer(Ibgp())
    emu.addLayer(Ospf())

    install_control_plane(emu)
    install_observability(emu)
    install_service_surface(emu)
    if ATTACK_PREFIX:
        emu.addHook(RoutingTrustHijackHook(role_nodes["attacker_router"], ATTACK_PREFIX))
    return emu


def main() -> None:
    platform = resolve_platform()
    output_dir_name = os.environ.get("ROUTING_TRUST_OUTPUT_DIR", "component_blueprint_output").strip() or "component_blueprint_output"
    output_dir = os.path.join(os.path.dirname(__file__), output_dir_name)
    emu = build_emulator()
    emu.render()
    emu.compile(Docker(platform=platform, internetMapEnabled=False), output_dir, override=True)


if __name__ == "__main__":
    main()
