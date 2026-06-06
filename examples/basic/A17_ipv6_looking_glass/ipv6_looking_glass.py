#!/usr/bin/env python3
# encoding: utf-8

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from seedemu.layers import Base, Routing, Ebgp, PeerRelationship, Ospf
from seedemu.services import BgpLookingGlassService
from seedemu.core import Emulator, Binding, Filter
from seedemu.compiler import Docker, Platform


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the A17 IPv6 Looking Glass example.")
    parser.add_argument("legacy_platform", nargs="?", choices=["amd", "arm"])
    parser.add_argument("--platform", choices=["amd", "arm"])
    parser.add_argument("--output", default=str(SCRIPT_DIR / "output"))
    parser.add_argument("--dumpfile")
    parser.add_argument("--override", dest="override", action="store_true", default=True)
    parser.add_argument("--no-override", dest="override", action="store_false")
    parser.add_argument("--skip-render", dest="render", action="store_false", default=True)
    args = parser.parse_args()
    args.platform = args.platform or args.legacy_platform or "amd"
    return args


def resolve_platform(name: str) -> Platform:
    return Platform.AMD64 if name == "amd" else Platform.ARM64


def build_emulator() -> Emulator:
    looking_glass_host_port = int(os.environ.get("SEED_A17_LG_PORT", "5017"))

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
    as2.createHost("looking-glass").joinNetwork("net0").addPortForwarding(
        looking_glass_host_port, 5000
    )

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
    return emu


def run(
    dumpfile=None,
    output=None,
    platform=Platform.AMD64,
    override=True,
    render=True,
):
    emu = build_emulator()
    if dumpfile is not None:
        emu.dump(dumpfile)
        return

    if render:
        emu.render()

    output_dir = Path(output or SCRIPT_DIR / "output").resolve()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    emu.compile(Docker(platform=platform), str(output_dir), override=override)


def main() -> int:
    args = parse_args()
    run(
        dumpfile=args.dumpfile,
        output=str(Path(args.output).resolve()),
        platform=resolve_platform(args.platform),
        override=args.override,
        render=args.render,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
