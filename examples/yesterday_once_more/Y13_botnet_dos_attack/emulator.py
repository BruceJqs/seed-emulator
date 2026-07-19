#!/usr/bin/env python3
# encoding: utf-8

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
B00_DIR = REPO_ROOT / "examples" / "internet" / "B00_mini_internet"
TRAFFIC_VISUALIZER_SOURCE_DIR = REPO_ROOT / "tools" / "TrafficVisualizer"

for path in [REPO_ROOT, B00_DIR]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from mini_internet import build_emulator
from seedemu.compiler import Docker, Platform
from seedemu.core import Action, Binding, Emulator, Filter, Node
from seedemu.services import BotnetClientService, BotnetService


BOT_CONTROLLER_IP = "10.150.0.66"
BOT_CANDIDATE_ASNS = [152, 154, 160, 161, 162, 163, 164, 170, 171]
AUTOMATIC_HOST_SLOTS_PER_AS = 29
VICTIM_HOST = (151, "host_0")
VICTIM_IP = "10.151.0.71"
VICTIM_ROUTER = (151, "router0")
LEGITIMATE_CLIENT_HOST = (153, "host_0")
DEMO_DIR = "/opt/botnet-dos"
TRAFFIC_VISUALIZER_DIR = f"{DEMO_DIR}/traffic_visualizer"
TRAFFIC_VISUALIZER_HOST_PORT = 8081
TRAFFIC_VISUALIZER_CONTAINER_PORT = 8080
HEALTH_PROBE_HOST_PORT = 8082
HEALTH_PROBE_CONTAINER_PORT = 8080
VICTIM_SERVICE_PORT = 8000
ATTACK_PORT = 9000
DEFAULT_BOT_PPS = 200
DEFAULT_UDP_PAYLOAD_BYTES = 1200


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Y13 botnet DoS example.")
    parser.add_argument("legacy_platform", nargs="?", choices=["amd", "arm"])
    parser.add_argument("--platform", choices=["amd", "arm"])
    parser.add_argument("--output", default=str(SCRIPT_DIR / "output"))
    parser.add_argument("--dumpfile")
    parser.add_argument("--hosts-per-as", type=int, default=2)
    parser.add_argument("--bot-count", type=int, default=8)
    parser.add_argument("--override", dest="override", action="store_true", default=True)
    parser.add_argument("--no-override", dest="override", action="store_false")
    parser.add_argument("--skip-render", dest="render", action="store_false", default=True)
    args = parser.parse_args()
    args.platform = args.platform or args.legacy_platform or "amd"
    if args.hosts_per_as < 1 or args.hosts_per_as >= AUTOMATIC_HOST_SLOTS_PER_AS:
        parser.error(f"--hosts-per-as must be between 1 and {AUTOMATIC_HOST_SLOTS_PER_AS - 1}")
    if args.bot_count < 1:
        parser.error("--bot-count must be at least 1")
    maximum_bots = len(BOT_CANDIDATE_ASNS) * (
        AUTOMATIC_HOST_SLOTS_PER_AS - args.hosts_per_as
    )
    if args.bot_count > maximum_bots:
        parser.error(
            f"--bot-count cannot exceed {maximum_bots} with "
            f"--hosts-per-as {args.hosts_per_as}"
        )
    return args


def resolve_platform(name: str) -> Platform:
    return Platform.AMD64 if name == "amd" else Platform.ARM64


def get_base(emu: Emulator):
    return emu.getLayer("Base")


def get_host(emu: Emulator, asn: int, name: str) -> Node:
    return get_base(emu).getAutonomousSystem(asn).getHost(name)


def get_router(emu: Emulator, asn: int, name: str) -> Node:
    return get_base(emu).getAutonomousSystem(asn).getRouter(name)


def read_example_file(name: str) -> str:
    return (SCRIPT_DIR / name).read_text(encoding="utf-8")


def install_example_file(node: Node, local_name: str, remote_name: str | None = None) -> None:
    node.setFile(f"{DEMO_DIR}/{remote_name or local_name}", read_example_file(local_name))


def install_traffic_visualizer_file(node: Node, name: str) -> None:
    content = (TRAFFIC_VISUALIZER_SOURCE_DIR / name).read_text(encoding="utf-8")
    node.setFile(f"{TRAFFIC_VISUALIZER_DIR}/{name}", content)


def prepare_demo_dir(node: Node) -> None:
    node.addBuildCommand(f"mkdir -p {DEMO_DIR} {TRAFFIC_VISUALIZER_DIR}")
    node.appendStartCommand(f"mkdir -p {DEMO_DIR} {TRAFFIC_VISUALIZER_DIR}")


def configure_bot_node(node: Node, index: int) -> None:
    node.addSoftware("python3")
    prepare_demo_dir(node)
    install_example_file(node, "bot_attack.py")
    node.appendStartCommand(f"chmod +x {DEMO_DIR}/bot_attack.py")
    node.setDisplayName(f"Bot-{index:03d}")
    node.appendClassName("BotnetDosBot")


def configure_controller(emu: Emulator, botnet: BotnetService) -> None:
    botnet.install("bot-controller")
    node = emu.getVirtualNode("bot-controller")
    node.setDisplayName("Bot-Controller")
    node.setFile("/bin/show-attack-command", read_example_file("show_attack_command.sh"))
    node.appendStartCommand("chmod +x /bin/show-attack-command")
    node.appendClassName("BotnetDosController")
    emu.addBinding(
        Binding(
            "bot-controller",
            filter=Filter(ip=BOT_CONTROLLER_IP, nodeName="bot-controller"),
            action=Action.NEW,
        )
    )


def configure_bots(emu: Emulator, clients: BotnetClientService, bot_count: int) -> None:
    for index in range(bot_count):
        vnode = f"bot-node-{index:03d}"
        asn = BOT_CANDIDATE_ASNS[index % len(BOT_CANDIDATE_ASNS)]
        clients.install(vnode).setServer("bot-controller")
        configure_bot_node(emu.getVirtualNode(vnode), index)
        emu.addBinding(
            Binding(
                vnode,
                filter=Filter(asn=asn, nodeName=vnode),
                action=Action.NEW,
            )
        )


def configure_victim_router(router: Node) -> None:
    router.addSoftware("python3")
    router.addSoftware("iproute2")
    prepare_demo_dir(router)
    install_traffic_visualizer_file(router, "network_control.py")
    router.appendStartCommand(f"chmod +x {TRAFFIC_VISUALIZER_DIR}/network_control.py")
    router.appendClassName("VictimAccessLinkController")
    router.setDisplayName("Victim-Access-Router")


def visualizer_config(bot_count: int) -> str:
    config = json.loads(read_example_file("traffic_visualizer_config.json"))
    options = config["frontend"]["options"]
    options["bot_count"] = bot_count
    options["bot_pps"] = DEFAULT_BOT_PPS
    options["udp_payload_bytes"] = DEFAULT_UDP_PAYLOAD_BYTES
    options["offered_load_mbps"] = round(
        bot_count * DEFAULT_BOT_PPS * (DEFAULT_UDP_PAYLOAD_BYTES + 28) * 8 / 1_000_000,
        2,
    )
    return json.dumps(config, indent=2) + "\n"


def configure_victim(host: Node, bot_count: int) -> None:
    host.addSoftware("python3")
    host.addSoftware("tcpdump")
    prepare_demo_dir(host)
    install_example_file(host, "udp_sink.py")
    install_traffic_visualizer_file(host, "victim_http_service.py")
    install_traffic_visualizer_file(host, "traffic_visualizer.py")
    install_traffic_visualizer_file(host, "dashboard.html")
    host.setFile(f"{TRAFFIC_VISUALIZER_DIR}/config.json", visualizer_config(bot_count))
    install_example_file(
        host,
        "traffic_visualizer_extension.js",
        "traffic_visualizer/traffic_visualizer_extension.js",
    )
    install_example_file(
        host,
        "traffic_visualizer_extension.css",
        "traffic_visualizer/traffic_visualizer_extension.css",
    )
    host.addPortForwarding(TRAFFIC_VISUALIZER_HOST_PORT, TRAFFIC_VISUALIZER_CONTAINER_PORT)
    host.appendStartCommand(
        f"chmod +x {DEMO_DIR}/udp_sink.py {TRAFFIC_VISUALIZER_DIR}/victim_http_service.py "
        f"{TRAFFIC_VISUALIZER_DIR}/traffic_visualizer.py"
    )
    host.appendStartCommand(
        f"python3 {DEMO_DIR}/udp_sink.py --port {ATTACK_PORT} "
        ">> /var/log/y13-udp-sink.log 2>&1",
        fork=True,
    )
    host.appendStartCommand(
        f"python3 {TRAFFIC_VISUALIZER_DIR}/victim_http_service.py --port {VICTIM_SERVICE_PORT} "
        ">> /var/log/y13-victim-http.log 2>&1",
        fork=True,
    )
    host.appendStartCommand(
        f"python3 {TRAFFIC_VISUALIZER_DIR}/traffic_visualizer.py "
        f"--config {TRAFFIC_VISUALIZER_DIR}/config.json "
        f"--dashboard {TRAFFIC_VISUALIZER_DIR}/dashboard.html "
        ">> /var/log/y13-traffic-visualizer.log 2>&1",
        fork=True,
    )
    host.appendClassName("BotnetDosVictim")
    host.appendClassName("TrafficVisualizer")
    host.appendClassName("VictimHttpService")
    host.setDisplayName("Victim")


def configure_legitimate_client(host: Node) -> None:
    host.addSoftware("python3")
    prepare_demo_dir(host)
    install_traffic_visualizer_file(host, "health_probe.py")
    host.addPortForwarding(HEALTH_PROBE_HOST_PORT, HEALTH_PROBE_CONTAINER_PORT)
    host.appendStartCommand(f"chmod +x {TRAFFIC_VISUALIZER_DIR}/health_probe.py")
    host.appendStartCommand(
        f"python3 {TRAFFIC_VISUALIZER_DIR}/health_probe.py "
        f"--target http://{VICTIM_IP}:{VICTIM_SERVICE_PORT}/health "
        f"--bandwidth-url http://{VICTIM_IP}:{VICTIM_SERVICE_PORT}/bandwidth "
        "--interval 0.2 --timeout 0.5 "
        "--bandwidth-bytes 262144 --bandwidth-interval 5 --bandwidth-timeout 3 "
        f"--serve-port {HEALTH_PROBE_CONTAINER_PORT} --cors-origin '*' --max-samples 300 "
        ">> /var/log/y13-health-probe.log 2>&1",
        fork=True,
    )
    host.appendClassName("LegitimateClient")
    host.setDisplayName("Legitimate-Client")


def build_y13_emulator(hosts_per_as: int = 2, bot_count: int = 8) -> Emulator:
    available_per_as = AUTOMATIC_HOST_SLOTS_PER_AS - hosts_per_as
    maximum_bots = len(BOT_CANDIDATE_ASNS) * available_per_as
    if hosts_per_as < 1 or available_per_as < 1:
        raise ValueError(
            f"hosts_per_as must be between 1 and {AUTOMATIC_HOST_SLOTS_PER_AS - 1}"
        )
    if bot_count < 1 or bot_count > maximum_bots:
        raise ValueError(
            f"bot_count must be between 1 and {maximum_bots} for hosts_per_as={hosts_per_as}"
        )
    emu = build_emulator(hosts_per_as=hosts_per_as)
    botnet = BotnetService()
    clients = BotnetClientService()

    configure_controller(emu, botnet)
    configure_bots(emu, clients, bot_count)
    configure_victim_router(get_router(emu, *VICTIM_ROUTER))
    configure_victim(get_host(emu, *VICTIM_HOST), bot_count)
    configure_legitimate_client(get_host(emu, *LEGITIMATE_CLIENT_HOST))

    emu.addLayer(botnet)
    emu.addLayer(clients)
    return emu


def run(
    dumpfile=None,
    hosts_per_as: int = 2,
    bot_count: int = 8,
    output=None,
    platform=Platform.AMD64,
    override: bool = True,
    render: bool = True,
) -> None:
    emu = build_y13_emulator(hosts_per_as=hosts_per_as, bot_count=bot_count)
    if dumpfile is not None:
        emu.dump(dumpfile)
        return
    if render:
        emu.render()
    emu.compile(Docker(platform=platform), output or str(SCRIPT_DIR / "output"), override=override)


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output).resolve()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    run(
        dumpfile=args.dumpfile,
        hosts_per_as=args.hosts_per_as,
        bot_count=args.bot_count,
        output=str(output_dir),
        platform=resolve_platform(args.platform),
        override=args.override,
        render=args.render,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
