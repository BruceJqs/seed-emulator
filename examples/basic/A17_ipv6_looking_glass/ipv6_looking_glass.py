#!/usr/bin/env python3
# encoding: utf-8

from seedemu.layers import Base, Routing, Ebgp, PeerRelationship, Ospf
from seedemu.services import BgpLookingGlassService
from seedemu.core import Emulator, Binding, Filter
from seedemu.compiler import Docker, Platform
import sys, os


script_name = os.path.basename(__file__)
output_dir = os.path.join(os.path.dirname(__file__), "output")
looking_glass_host_port = int(os.environ.get("SEED_A17_LG_PORT", "5017"))

if len(sys.argv) == 1:
    platform = Platform.AMD64
elif len(sys.argv) == 2:
    if sys.argv[1].lower() == 'amd':
        platform = Platform.AMD64
    elif sys.argv[1].lower() == 'arm':
        platform = Platform.ARM64
    else:
        print(f"Usage:  {script_name} amd|arm")
        sys.exit(1)
else:
    print(f"Usage:  {script_name} amd|arm")
    sys.exit(1)

emu = Emulator()

base = Base(enableIpv6=True, ipv6RootPrefix="2000::/12")
routing = Routing()
ospf = Ospf()
ebgp = Ebgp()
looking_glass = BgpLookingGlassService()

base.createInternetExchange(100)

as2 = base.createAutonomousSystem(2)
as2.createNetwork("net0")
as2.createRouter("router0", routingBackend="frr") \
    .joinNetwork("net0") \
    .joinNetwork("ix100")
as2.createHost("looking-glass").joinNetwork("net0").addPortForwarding(looking_glass_host_port, 5000)

as151 = base.createAutonomousSystem(151)
as151.createNetwork("net0")
as151.createRouter("router0").joinNetwork("net0").joinNetwork("ix100")

ebgp.addPrivatePeering(100, 2, 151, abRelationship=PeerRelationship.Provider)

looking_glass.install("bgp_lg") \
    .addRouter(2, "router0") \
    .addRouter(151, "router0") \
    .useManagementNetwork() \
    .setFrontendPort(5000) \
    .setProxyPort(8000)
emu.addBinding(Binding("bgp_lg", filter=Filter(nodeName="looking-glass", asn=2)))

emu.addLayer(base)
emu.addLayer(routing)
emu.addLayer(ospf)
emu.addLayer(ebgp)
emu.addLayer(looking_glass)

emu.render()
emu.compile(Docker(platform=platform), output_dir, override=True)
