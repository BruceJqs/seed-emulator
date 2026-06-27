#!/usr/bin/env python3
# encoding: utf-8

from __future__ import annotations

import argparse
from pathlib import Path
import sys
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
B00_DIR = REPO_ROOT / "examples" / "internet" / "B00_mini_internet"

for path in [REPO_ROOT, B00_DIR]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from mini_internet import build_emulator
from seedemu.compiler import Docker, Platform
from seedemu.core import Emulator, Node


AMPLIFIER_HOSTS = [(152, "host_0"), (160, "host_0"), (171, "host_0")]
ATTACKER_HOST = (150, "host_0")
VICTIM_HOST = (151, "host_0")
NTP_LIKE_DIR = "/opt/ntp-like"
VICTIM_LOG = "/var/log/ntp-like-victim.log"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Y10 NTP-like amplification example.")
    parser.add_argument("legacy_platform", nargs="?", choices=["amd", "arm"])
    parser.add_argument("--platform", choices=["amd", "arm"])
    parser.add_argument("--output", default=str(SCRIPT_DIR / "output"))
    parser.add_argument("--dumpfile")
    parser.add_argument("--hosts-per-as", type=int, default=2)
    parser.add_argument("--response-size", type=int, default=1200)
    parser.add_argument("--override", dest="override", action="store_true", default=True)
    parser.add_argument("--no-override", dest="override", action="store_false")
    parser.add_argument("--skip-render", dest="render", action="store_false", default=True)
    args = parser.parse_args()
    args.platform = args.platform or args.legacy_platform or "amd"
    return args


def resolve_platform(name: str) -> Platform:
    return Platform.AMD64 if name == "amd" else Platform.ARM64


def get_host(emu: Emulator, asn: int, name: str) -> Node:
    base = emu.getLayer("Base")
    return base.getAutonomousSystem(asn).getHost(name)


def install_file(node: Node, local_name: str, remote_name: str) -> None:
    content = (SCRIPT_DIR / local_name).read_text(encoding="utf-8")
    node.setFile(f"{NTP_LIKE_DIR}/{remote_name}", content)


def prepare_ntp_like_dir(node: Node) -> None:
    node.addBuildCommand(f"mkdir -p {NTP_LIKE_DIR}")
    node.appendStartCommand(f"mkdir -p {NTP_LIKE_DIR}")


def install_amplifier(node: Node, response_size: int) -> None:
    node.addSoftware("python3")
    prepare_ntp_like_dir(node)
    install_file(node, "ntp_like_daemon.py", "ntp_like_daemon.py")
    node.appendStartCommand(
        "python3 {}/ntp_like_daemon.py "
        "--port 123 "
        "--response-size {} "
        "--allowed-prefix 10. "
        "--reflect-token seedemu-lab "
        "--reflect-target-prefix 10. "
        ">> /var/log/ntp-like-daemon.log 2>&1".format(NTP_LIKE_DIR, response_size),
        fork=True,
    )
    node.appendClassName("NtpLikeAmplifier")


def install_attacker(node: Node) -> None:
    node.addSoftware("python3")
    prepare_ntp_like_dir(node)
    install_file(node, "trigger_attack.py", "trigger_attack.py")
    install_file(node, "trigger_attack.sh", "trigger_attack.sh")
    node.appendStartCommand(f"chmod +x {NTP_LIKE_DIR}/trigger_attack.py {NTP_LIKE_DIR}/trigger_attack.sh")
    node.appendClassName("NtpLikeAttacker")


def install_victim(node: Node) -> None:
    node.addSoftware("python3")
    prepare_ntp_like_dir(node)
    install_file(node, "udp_sink.py", "udp_sink.py")
    node.appendStartCommand(f": > {VICTIM_LOG}")
    node.appendStartCommand(
        f"python3 {NTP_LIKE_DIR}/udp_sink.py --port 9000 --log {VICTIM_LOG} "
        ">> /var/log/ntp-like-victim-sink.log 2>&1",
        fork=True,
    )
    node.appendClassName("NtpLikeVictim")


def customize_b00_for_ntp_amplification(emu: Emulator, response_size: int) -> None:
    for asn, host in AMPLIFIER_HOSTS:
        install_amplifier(get_host(emu, asn, host), response_size)

    install_attacker(get_host(emu, *ATTACKER_HOST))
    install_victim(get_host(emu, *VICTIM_HOST))


def build_y10_emulator(hosts_per_as: int, response_size: int) -> Emulator:
    emu = build_emulator(hosts_per_as=hosts_per_as)
    customize_b00_for_ntp_amplification(emu, response_size=response_size)
    return emu


def run(
    dumpfile=None,
    hosts_per_as=2,
    response_size=1200,
    output=None,
    platform=Platform.AMD64,
    override=True,
    render=True,
) -> None:
    emu = build_y10_emulator(hosts_per_as=hosts_per_as, response_size=response_size)
    if dumpfile is not None:
        emu.dump(dumpfile)
        return

    if render:
        emu.render()

    docker = Docker(platform=platform)
    emu.compile(docker, output or "./output", override=override)


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output).resolve()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    run(
        dumpfile=args.dumpfile,
        hosts_per_as=args.hosts_per_as,
        response_size=args.response_size,
        output=str(output_dir),
        platform=resolve_platform(args.platform),
        override=args.override,
        render=args.render,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
