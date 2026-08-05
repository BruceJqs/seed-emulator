#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from seedemu.compiler import Docker, Platform
from seedemu.core import Emulator, ImageRef
from seedemu.layers import Base


AMD_IMAGE = ImageRef("ubuntu", tag="22.04", platform="amd64")
ARM_IMAGE = ImageRef("ubuntu", tag="24.04", platform="arm64")
BASE_IMAGES = (AMD_IMAGE, ARM_IMAGE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the A14 base-image example.")
    parser.add_argument("legacy_platform", nargs="?", choices=["amd", "arm"])
    parser.add_argument("--platform", choices=["amd", "arm"])
    parser.add_argument("--output", default=str(SCRIPT_DIR / "output"))
    parser.add_argument("--override", dest="override", action="store_true", default=True)
    parser.add_argument("--no-override", dest="override", action="store_false")
    args = parser.parse_args()
    args.platform = args.platform or args.legacy_platform or "amd"
    return args


def resolve_platform(name: str) -> Platform:
    return Platform.AMD64 if name == "amd" else Platform.ARM64


def build_emulator(image_refs: Iterable[ImageRef] = BASE_IMAGES) -> Emulator:
    emu = Emulator()
    base = Base()

    autonomous_system = base.createAutonomousSystem(150)
    autonomous_system.createNetwork("net0")
    host = autonomous_system.createHost("host").joinNetwork("net0")
    host.getSoftware().clear()
    for image_ref in image_refs:
        host.setBaseImage(image_ref)

    emu.addLayer(base)
    return emu


def compile_emulator(
    output: Path,
    platform: Platform,
    image_refs: Iterable[ImageRef] = BASE_IMAGES,
    override: bool = True,
) -> None:
    emu = build_emulator(image_refs)
    emu.render()
    emu.compile(
        Docker(platform=platform, internetMapEnabled=False),
        str(output),
        override=override,
    )


def main() -> int:
    args = parse_args()
    compile_emulator(
        Path(args.output).resolve(),
        resolve_platform(args.platform),
        override=args.override,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
