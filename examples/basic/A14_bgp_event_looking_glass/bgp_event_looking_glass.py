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

from seedemu.compiler import Docker, Platform
from seedemu.core import Binding, Emulator, Filter
from seedemu.layers import Base, Ebgp, PeerRelationship, Routing
from seedemu.services import BgpLookingGlassService, ExaBgpService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build separate BGP route-state and event-dashboard observers.")
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
    emu = Emulator()

    base = Base()
    routing = Routing()
    ebgp = Ebgp()
    exabgp = ExaBgpService()
    looking_glass = BgpLookingGlassService()

    base.createInternetExchange(100)

    looking_glass_port = int(os.environ.get("SEED_A14_LG_PORT", "5002"))
    event_dashboard_port = int(os.environ.get("SEED_A14_EVENT_PORT", "5003"))

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    as2.createRouter("router0").joinNetwork("net0").joinNetwork("ix100")
    as2.createHost("looking-glass").joinNetwork("net0").addPortForwarding(looking_glass_port, 5000)

    as151 = base.createAutonomousSystem(151)
    as151.createNetwork("net0")
    as151.createRouter("router0").joinNetwork("net0").joinNetwork("ix100")
    as151.createHost("event-viewer").joinNetwork("net0").addPortForwarding(event_dashboard_port, 5000)

    ebgp.addPrivatePeering(100, 2, 151, abRelationship=PeerRelationship.Provider)

    looking_glass.install("bgp_lg").addRouter(2, "router0").setFrontendPort(5000).setProxyPort(8000)
    emu.addBinding(Binding("bgp_lg", filter=Filter(nodeName="looking-glass", asn=2)))

    exabgp.install("bgp_events") \
        .attachToRouter("router0") \
        .setLocalAsn(65020) \
        .enableDashboard(5000)
    emu.addBinding(Binding("bgp_events", filter=Filter(nodeName="event-viewer", asn=151)))

    emu.addLayer(base)
    emu.addLayer(routing)
    emu.addLayer(ebgp)
    emu.addLayer(exabgp)
    emu.addLayer(looking_glass)
    return emu


def main() -> int:
    args = parse_args()
    emu = build_emulator()

    if args.dumpfile:
        emu.dump(args.dumpfile)
        print("Saved A14 emulator to {}".format(args.dumpfile))
        return 0

    if args.render:
        emu.render()

    output_dir = Path(args.output).resolve()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    emu.compile(Docker(platform=resolve_platform(args.platform)), str(output_dir), override=args.override)
    print("Generated A14 Docker output in {}".format(output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
