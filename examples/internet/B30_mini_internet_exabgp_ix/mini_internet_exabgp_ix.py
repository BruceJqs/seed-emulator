#!/usr/bin/env python3

import argparse
import os
from pathlib import Path
import sys
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from seedemu.compiler import Docker, Platform
from seedemu.core import Emulator
from seedemu.layers import Ebgp, PeerRelationship
from examples.internet.B00_mini_internet import mini_internet


EXABGP_ASN = 180
EXABGP_ROUTER = "exabgp"
EXABGP_IX = 100
EXABGP_IX_ADDRESS = "10.100.0.180"
EXABGP_ANNOUNCEMENT = "203.0.113.0/24"
EXABGP_EXTRA_ANNOUNCEMENT = "203.0.114.0/24"
EXABGP_CONTAINER_PORT = 5000
EXABGP_HOST_PORT_ENV = "SEED_B30_EXABGP_PORT"
EXABGP_DEFAULT_HOST_PORT = 5106


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build mini_internet with an AS180 ExaBGP IX control-plane router"
    )
    parser.add_argument("platform", nargs="?", default="amd", choices=["amd", "arm"])
    return parser.parse_args()


def resolve_platform(name: str) -> Platform:
    return Platform.AMD64 if name == "amd" else Platform.ARM64


def get_dashboard_host_port() -> int:
    value = os.environ.get(EXABGP_HOST_PORT_ENV, str(EXABGP_DEFAULT_HOST_PORT))
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{EXABGP_HOST_PORT_ENV} must be an integer, got {value!r}") from exc


def add_exabgp_ix_router(emu: Emulator):
    base = emu.getLayer("Base")

    as180 = base.createAutonomousSystem(EXABGP_ASN)
    router = as180.createRouter(EXABGP_ROUTER, routingBackend="exabgp")
    router.joinNetwork(f"ix{EXABGP_IX}", address=EXABGP_IX_ADDRESS)
    router.addPort(get_dashboard_host_port(), EXABGP_CONTAINER_PORT, "tcp")
    router.setDisplayName("AS180 ExaBGP IX Control Plane")
    router.addBgpAnnouncement(EXABGP_ANNOUNCEMENT)
    router.addBgpAnnouncement(EXABGP_EXTRA_ANNOUNCEMENT)
    return router


def build_emulator() -> Emulator:
    base_bin = SCRIPT_DIR / "base_internet.bin"
    mini_internet.run(dumpfile=str(base_bin), hosts_per_as=0)

    emu = Emulator()
    emu.load(str(base_bin))

    add_exabgp_ix_router(emu)
    ebgp = emu.getLayer("Ebgp")
    assert isinstance(ebgp, Ebgp)
    ebgp.addPrivatePeering(EXABGP_IX, 2, EXABGP_ASN, abRelationship=PeerRelationship.Provider)
    ebgp.addPrivatePeering(EXABGP_IX, 3, EXABGP_ASN, abRelationship=PeerRelationship.Provider)

    return emu


def run(dumpfile: Optional[str] = None) -> None:
    emu = build_emulator()

    if dumpfile is not None:
        emu.dump(dumpfile)
        return

    args = parse_args()
    output_dir = SCRIPT_DIR / "output"

    emu.render()
    emu.compile(
        Docker(platform=resolve_platform(args.platform)),
        str(output_dir),
        override=True,
    )

    print(f"Generated Docker output in: {output_dir}")
    print(
        "ExaBGP dashboard will be published on host port "
        f"{get_dashboard_host_port()} when the compose project is started."
    )


if __name__ == "__main__":
    run()
