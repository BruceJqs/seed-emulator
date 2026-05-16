#!/usr/bin/env python
"""
Strict same-scenario V2 blueprint for routing-service-trust-baseline.

This project-local file is intentionally a blueprint rather than a finished lab.
It captures the minimum same-topology role graph that we want to materialize on
the remote SEED harness once strict-v2 is approved for the first real prepare.
"""

from __future__ import annotations

import os
import sys

from seedemu.compiler import Docker, Platform
from seedemu.core import Binding, Emulator, Filter, Hook
from seedemu.layers import Base, Ebgp, Ibgp, Ospf, PeerRelationship, Routing
from seedemu.services import BgpLookingGlassService, ExaBgpService, WebService


SERVICE_PREFIX = "203.0.113.0/24"
EXABGP_DASHBOARD_PORT = int(os.environ.get("STRICT_V2_EXABGP_PORT", "5601"))
LOOKING_GLASS_PORT = int(os.environ.get("STRICT_V2_LOOKING_GLASS_PORT", "5602"))
STRICT_V2_IX_IDS = (210, 211, 212)
ATTACKER_ASN = 220
SERVICE_ASN = 221
CLIENT_ASN = 222
OBSERVER_ASN = 223
TRANSIT_ASN = 224

HIJACK_STATIC_TEMPLATE = """\
    ipv4 {{
        table t_hijack;
    }};
{routes}
"""


class StrictV2HijackHook(Hook):
    def __init__(self, attacker_router):
        self._attacker_router = attacker_router

    def getName(self) -> str:
        return "StrictV2HijackInjector"

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
            HIJACK_STATIC_TEMPLATE.format(routes=f"    route {SERVICE_PREFIX} blackhole;\n"),
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


def create_role_topology(base: Base) -> dict[str, object]:
    ix_core, ix_service, ix_client = STRICT_V2_IX_IDS
    base.createInternetExchange(ix_core).getPeeringLan().setDisplayName("strict-v2-core-ix")
    base.createInternetExchange(ix_service).getPeeringLan().setDisplayName("strict-v2-service-ix")
    base.createInternetExchange(ix_client).getPeeringLan().setDisplayName("strict-v2-client-ix")

    transit = base.createAutonomousSystem(TRANSIT_ASN)
    transit.createNetwork("core_net")
    transit_router = transit.createRouter("r-core")
    transit_router.joinNetwork("core_net")
    transit_router.joinNetwork(f"ix{ix_core}")
    transit_router.joinNetwork(f"ix{ix_service}")
    transit_router.joinNetwork(f"ix{ix_client}")

    attacker = base.createAutonomousSystem(ATTACKER_ASN)
    attacker.createNetwork("net0")
    attacker_router = attacker.createRouter("r-attacker")
    attacker_router.joinNetwork("net0")
    attacker_router.joinNetwork(f"ix{ix_core}")
    attacker_host = attacker.createHost("event-viewer")
    attacker_host.joinNetwork("net0")
    attacker_host.addPortForwarding(EXABGP_DASHBOARD_PORT, 5000)

    service = base.createAutonomousSystem(SERVICE_ASN)
    service.createNetwork("net0")
    service_router = service.createRouter("r-service")
    service_router.joinNetwork("net0")
    service_router.joinNetwork(f"ix{ix_service}")
    service_host = service.createHost("service-app")
    service_host.joinNetwork("net0")

    client = base.createAutonomousSystem(CLIENT_ASN)
    client.createNetwork("net0")
    client_router = client.createRouter("r-client")
    client_router.joinNetwork("net0")
    client_router.joinNetwork(f"ix{ix_client}")
    client_host = client.createHost("client-probe")
    client_host.joinNetwork("net0")

    observer = base.createAutonomousSystem(OBSERVER_ASN)
    observer.createNetwork("net0")
    observer_router = observer.createRouter("r-observer")
    observer_router.joinNetwork("net0")
    observer_router.joinNetwork(f"ix{ix_core}")
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
    ix_core, ix_service, ix_client = STRICT_V2_IX_IDS
    ebgp.addPrivatePeering(ix_core, TRANSIT_ASN, ATTACKER_ASN, abRelationship=PeerRelationship.Provider)
    ebgp.addPrivatePeering(ix_service, TRANSIT_ASN, SERVICE_ASN, abRelationship=PeerRelationship.Provider)
    ebgp.addPrivatePeering(ix_client, TRANSIT_ASN, CLIENT_ASN, abRelationship=PeerRelationship.Provider)
    ebgp.addPrivatePeering(ix_core, TRANSIT_ASN, OBSERVER_ASN, abRelationship=PeerRelationship.Provider)


def install_observability(emu: Emulator, role_nodes: dict[str, object]) -> None:
    exabgp = ExaBgpService()
    looking_glass = BgpLookingGlassService()

    attacker_router = role_nodes["attacker_router"]
    observer_host = role_nodes["observer_host"]

    exabgp.install("strict_v2_bgp_events") \
        .attachToRouter("r-attacker") \
        .setLocalAsn(65199) \
        .addAnnouncement(SERVICE_PREFIX) \
        .enableDashboard(EXABGP_DASHBOARD_PORT)
    emu.addBinding(Binding("strict_v2_bgp_events", filter=Filter(nodeName="event-viewer", asn=ATTACKER_ASN)))

    looking_glass.install("strict_v2_lg") \
        .attach("r-observer") \
        .setFrontendPort(5000) \
        .setProxyPort(8000)
    emu.addBinding(Binding("strict_v2_lg", filter=Filter(nodeName=observer_host.getName(), asn=OBSERVER_ASN)))

    emu.addHook(StrictV2HijackHook(attacker_router))
    emu.addLayer(exabgp)
    emu.addLayer(looking_glass)


def install_service_surface(emu: Emulator) -> None:
    web = WebService()
    web_server = web.install("strict_v2_service_web")
    web_server.setServerNames(["strict-v2.service.local"])
    web_server.setIndexContent(
        "<h1>strict-v2 service surface</h1>"
        "<p>Same-topology routing trust validation service.</p>"
    )
    emu.addBinding(Binding("strict_v2_service_web", filter=Filter(nodeName="service-app", asn=SERVICE_ASN)))
    emu.addLayer(web)


def build_emulator() -> Emulator:
    emu = Emulator()
    base = Base()
    routing = Routing()
    ebgp = Ebgp()

    role_nodes = create_role_topology(base)
    configure_peerings(ebgp)

    emu.addLayer(base)
    emu.addLayer(routing)
    emu.addLayer(ebgp)
    emu.addLayer(Ibgp())
    emu.addLayer(Ospf())

    install_observability(emu, role_nodes)
    install_service_surface(emu)
    return emu


def main() -> None:
    platform = resolve_platform()
    output_dir = os.path.join(os.path.dirname(__file__), "strict_v2_output")
    emu = build_emulator()
    emu.render()
    emu.compile(Docker(platform=platform), output_dir, override=True)


if __name__ == "__main__":
    main()
