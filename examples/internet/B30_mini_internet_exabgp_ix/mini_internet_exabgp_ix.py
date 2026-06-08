#!/usr/bin/env python3
# encoding: utf-8

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from typing import Optional


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from examples.internet.B00_mini_internet import mini_internet
from seedemu.compiler import Docker, Platform
from seedemu.core import Binding, Emulator, Filter
from seedemu.services import ExaBgpService


EXABGP_ASN = 180
EXABGP_NODE = "exabgp"
EXABGP_VNODE = "as180_exabgp"
EXABGP_IX = 100
EXABGP_IX_ADDRESS = "10.100.0.180"
EXABGP_ANNOUNCEMENT = "203.0.113.0/24"
EXABGP_EXTRA_ANNOUNCEMENT = "203.0.114.0/24"
EXABGP_CONTAINER_PORT = 5000
EXABGP_HOST_PORT_ENV = "SEED_B30_EXABGP_PORT"
EXABGP_DEFAULT_HOST_PORT = 5106


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build B00 with an AS180 ExaBGP IX speaker.")
    parser.add_argument("legacy_platform", nargs="?", choices=["amd", "arm"])
    parser.add_argument("--platform", choices=["amd", "arm"])
    parser.add_argument("--output", default=str(SCRIPT_DIR / "output"))
    parser.add_argument("--dumpfile")
    parser.add_argument("--hosts-per-as", type=int, default=0)
    parser.add_argument("--override", dest="override", action="store_true", default=True)
    parser.add_argument("--no-override", dest="override", action="store_false")
    parser.add_argument("--skip-render", dest="render", action="store_false", default=True)
    args = parser.parse_args()
    args.platform = args.platform or args.legacy_platform or "amd"
    return args


def resolve_platform(name: str) -> Platform:
    return Platform.AMD64 if name == "amd" else Platform.ARM64


def get_dashboard_host_port() -> int:
    value = os.environ.get(EXABGP_HOST_PORT_ENV, str(EXABGP_DEFAULT_HOST_PORT))
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError("{} must be an integer, got {!r}".format(EXABGP_HOST_PORT_ENV, value)) from exc


def add_exabgp_ix_speaker(emu: Emulator) -> None:
    base = emu.getLayer("Base")

    as180 = base.createAutonomousSystem(EXABGP_ASN)
    speaker = as180.createHost(EXABGP_NODE)
    speaker.joinNetwork("ix{}".format(EXABGP_IX), address=EXABGP_IX_ADDRESS)
    speaker.addPort(get_dashboard_host_port(), EXABGP_CONTAINER_PORT, "tcp")
    speaker.setDisplayName("AS180 ExaBGP IX Control Plane")

    exabgp = ExaBgpService()
    exabgp.install(EXABGP_VNODE) \
        .setLocalAsn(EXABGP_ASN) \
        .addPeer("r100", router_asn=2, router_relationship="customer") \
        .addPeer("r100", router_asn=3, router_relationship="customer") \
        .addAnnouncement(EXABGP_ANNOUNCEMENT) \
        .addAnnouncement(EXABGP_EXTRA_ANNOUNCEMENT)
    emu.addBinding(Binding(EXABGP_VNODE, filter=Filter(asn=EXABGP_ASN, nodeName=EXABGP_NODE)))
    emu.addLayer(exabgp)


def build_emulator(hosts_per_as: int = 0) -> Emulator:
    emu = mini_internet.build_emulator(hosts_per_as=hosts_per_as)
    add_exabgp_ix_speaker(emu)
    return emu


def run(
    dumpfile: Optional[str] = None,
    hosts_per_as: int = 0,
    output: Optional[str] = None,
    platform: Platform = Platform.AMD64,
    override: bool = True,
    render: bool = True,
) -> None:
    emu = build_emulator(hosts_per_as=hosts_per_as)

    if dumpfile is not None:
        emu.dump(dumpfile)
        return

    if render:
        emu.render()

    docker = Docker(platform=platform)
    emu.compile(docker, output or str(SCRIPT_DIR / "output"), override=override)


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output).resolve()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    run(
        dumpfile=args.dumpfile,
        hosts_per_as=args.hosts_per_as,
        output=str(output_dir),
        platform=resolve_platform(args.platform),
        override=args.override,
        render=args.render,
    )
    print("Generated B30 Docker output in {}".format(output_dir))
    print(
        "ExaBGP dashboard will be published on host port {} when the compose project is started.".format(
            get_dashboard_host_port()
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
