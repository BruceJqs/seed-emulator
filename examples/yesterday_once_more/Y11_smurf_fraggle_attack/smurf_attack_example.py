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


ATTACKER_HOST = (150, "host_0")
VICTIM_HOST = (151, "host_0")
TARGET_ASN = 152
TARGET_ROUTER = "router0"
TARGET_NETWORK = "net0"
SMURF_DIR = "/opt/smurf-lab"
FRAGGLE_PORT = 19


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Y11 Smurf attack example.")
    parser.add_argument("legacy_platform", nargs="?", choices=["amd", "arm"])
    parser.add_argument("--platform", choices=["amd", "arm"])
    parser.add_argument("--output", default=str(SCRIPT_DIR / "output"))
    parser.add_argument("--dumpfile")
    parser.add_argument("--hosts-per-as", type=int, default=2)
    parser.add_argument(
        "--target-hosts",
        type=int,
        default=12,
        help="number of hosts on the vulnerable AS152 broadcast LAN",
    )
    parser.add_argument("--override", dest="override", action="store_true", default=True)
    parser.add_argument("--no-override", dest="override", action="store_false")
    parser.add_argument("--skip-render", dest="render", action="store_false", default=True)
    args = parser.parse_args()
    args.platform = args.platform or args.legacy_platform or "amd"
    return args


def resolve_platform(name: str) -> Platform:
    return Platform.AMD64 if name == "amd" else Platform.ARM64


def get_base(emu: Emulator):
    return emu.getLayer("Base")


def get_host(emu: Emulator, asn: int, name: str) -> Node:
    return get_base(emu).getAutonomousSystem(asn).getHost(name)


def get_router(emu: Emulator, asn: int, name: str) -> Node:
    return get_base(emu).getAutonomousSystem(asn).getRouter(name)


def install_file(node: Node, local_name: str, remote_name: str) -> None:
    content = (SCRIPT_DIR / local_name).read_text(encoding="utf-8")
    node.setFile(f"{SMURF_DIR}/{remote_name}", content)


def prepare_smurf_dir(node: Node) -> None:
    node.addBuildCommand(f"mkdir -p {SMURF_DIR}")
    node.appendStartCommand(f"mkdir -p {SMURF_DIR}")


def add_target_hosts(emu: Emulator, target_hosts: int, hosts_per_as: int) -> None:
    target_as = get_base(emu).getAutonomousSystem(TARGET_ASN)
    existing = max(hosts_per_as, 0)
    for index in range(existing, target_hosts):
        target_as.createHost(f"host_{index}").joinNetwork(TARGET_NETWORK)


def configure_directed_broadcast_router(router: Node) -> None:
    router.appendStartCommand("sysctl -w net.ipv4.ip_forward=1")
    router.appendStartCommand("sysctl -w net.ipv4.conf.all.bc_forwarding=1 || true")
    router.appendStartCommand("sysctl -w net.ipv4.conf.default.bc_forwarding=1 || true")
    router.appendStartCommand(
        "for f in /proc/sys/net/ipv4/conf/*/bc_forwarding; do [ -e \"$f\" ] && echo 1 > \"$f\"; done"
    )
    router.appendStartCommand("sysctl -w net.ipv4.conf.all.rp_filter=0")
    router.appendStartCommand("sysctl -w net.ipv4.conf.default.rp_filter=0")
    router.appendClassName("SmurfDirectedBroadcastRouter")


def configure_target_host(host: Node) -> None:
    host.addSoftware("python3")
    prepare_smurf_dir(host)
    install_file(host, "fraggle_amplifier.py", "fraggle_amplifier.py")
    host.appendStartCommand("sysctl -w net.ipv4.icmp_echo_ignore_broadcasts=0")
    host.appendStartCommand("sysctl -w net.ipv4.conf.all.rp_filter=0")
    host.appendStartCommand("sysctl -w net.ipv4.conf.default.rp_filter=0")
    host.appendStartCommand(f"chmod +x {SMURF_DIR}/fraggle_amplifier.py")
    host.appendStartCommand(
        "python3 {}/fraggle_amplifier.py --port {} --mode chargen --response-size 512 "
        ">> /var/log/fraggle-amplifier-supervisor.log 2>&1".format(SMURF_DIR, FRAGGLE_PORT),
        fork=True,
    )
    host.appendClassName("SmurfAmplifierHost")
    host.appendClassName("FraggleAmplifierHost")


def configure_attacker(host: Node) -> None:
    host.addSoftware("python3")
    prepare_smurf_dir(host)
    install_file(host, "smurf_attack.py", "smurf_attack.py")
    install_file(host, "fraggle_attack.py", "fraggle_attack.py")
    install_file(host, "trigger_attack.sh", "trigger_attack.sh")
    host.appendStartCommand(
        f"chmod +x {SMURF_DIR}/smurf_attack.py {SMURF_DIR}/fraggle_attack.py {SMURF_DIR}/trigger_attack.sh"
    )
    host.appendClassName("SmurfAttacker")
    host.appendClassName("FraggleAttacker")


def configure_victim(host: Node) -> None:
    host.addSoftware("python3")
    prepare_smurf_dir(host)
    install_file(host, "smurf_monitor.py", "smurf_monitor.py")
    install_file(host, "fraggle_monitor.py", "fraggle_monitor.py")
    install_file(host, "visualize_attack.py", "visualize_attack.py")
    host.appendStartCommand(
        f"chmod +x {SMURF_DIR}/smurf_monitor.py {SMURF_DIR}/fraggle_monitor.py {SMURF_DIR}/visualize_attack.py"
    )
    host.appendClassName("SmurfVictim")
    host.appendClassName("FraggleVictim")


def customize_b00_for_smurf(emu: Emulator, target_hosts: int, hosts_per_as: int) -> None:
    if target_hosts < hosts_per_as:
        raise ValueError("--target-hosts must be greater than or equal to --hosts-per-as")

    add_target_hosts(emu, target_hosts=target_hosts, hosts_per_as=hosts_per_as)
    configure_directed_broadcast_router(get_router(emu, TARGET_ASN, TARGET_ROUTER))
    configure_attacker(get_host(emu, *ATTACKER_HOST))
    configure_victim(get_host(emu, *VICTIM_HOST))

    target_as = get_base(emu).getAutonomousSystem(TARGET_ASN)
    for index in range(target_hosts):
        configure_target_host(target_as.getHost(f"host_{index}"))


def build_y11_emulator(hosts_per_as: int, target_hosts: int) -> Emulator:
    emu = build_emulator(hosts_per_as=hosts_per_as)
    customize_b00_for_smurf(emu, target_hosts=target_hosts, hosts_per_as=hosts_per_as)
    return emu


def run(
    dumpfile=None,
    hosts_per_as=2,
    target_hosts=12,
    output=None,
    platform=Platform.AMD64,
    override=True,
    render=True,
) -> None:
    emu = build_y11_emulator(hosts_per_as=hosts_per_as, target_hosts=target_hosts)
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
        target_hosts=args.target_hosts,
        output=str(output_dir),
        platform=resolve_platform(args.platform),
        override=args.override,
        render=args.render,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
