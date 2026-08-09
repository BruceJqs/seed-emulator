#!/usr/bin/env python3
# encoding: utf-8

from argparse import ArgumentParser
from pathlib import Path

from seedemu import *
from examples.basic.A01_transit_as import transit_as


def parse_args():
    parser = ArgumentParser(description="Customize a SeedEmu node.")
    parser.add_argument("--platform", choices=("amd", "arm"), default="amd")
    parser.add_argument("--output", default="output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    platform = Platform.AMD64 if args.platform == "amd" else Platform.ARM64
    output = Path(args.output)

    # Load the pre-built component from example A01_transit_as.
    transit_as.run(dumpfile="./base_component.bin")

    emu = Emulator()
    emu.load("./base_component.bin")

    base = emu.getLayer("Base")
    as152 = base.getAutonomousSystem(152)
    node = as152.getHost("host0")

    # Select the runtime system required by this node. Docker maps this exact
    # profile to ubuntu:24.04. More specialized profiles can declare this
    # profile as their subset.
    node.setBaseSystem(BaseSystem.UBUNTU_24_04)

    assert BaseSystem.doesAContainB(
        BaseSystem.SEEDEMU_BASE, BaseSystem.UBUNTU_24_04
    )
    assert BaseSystem.doesAContainB(
        BaseSystem.SEEDEMU_ROUTER, BaseSystem.SEEDEMU_BASE
    )

    # Dockerfile: RUN apt-get update && apt-get install -y
    #                     --no-install-recommends python3
    node.addSoftware("python3")

    # Dockerfile: RUN curl http://example.com
    node.addBuildCommand("curl http://example.com")

    # Dockerfile: COPY <generated-name> /myprog.py
    node.importFile(
        hostpath=str(Path.cwd() / "myprog.py"),
        containerpath="/myprog.py",
    )

    # Dockerfile: COPY <generated-name> /file.txt
    node.setFile(path="/file.txt", content="hello world")

    # Add a finite ping check to start.sh.
    node.insertStartCommand(0, "ping -c 1 1.2.3.4 >/dev/null || true")

    # Add "python3 /myprog.py &" to start.sh.
    node.appendStartCommand("python3 /myprog.py", fork=True)

    emu.render()
    emu.compile(Docker(platform=platform), str(output), override=True)

    dockerfiles = [
        path.read_text()
        for path in (output / "dummies").glob("*")
    ]
    assert any(
        content.startswith("FROM ubuntu:24.04\n") for content in dockerfiles
    ), "setBaseSystem did not select the ubuntu:24.04 image"


if __name__ == "__main__":
    main()
