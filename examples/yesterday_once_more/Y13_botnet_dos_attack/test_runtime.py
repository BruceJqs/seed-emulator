#!/usr/bin/env python3
"""Validate Y13 infrastructure without launching a denial-of-service load."""

from __future__ import annotations

from typing import List

from seedemu.testing import ComposeRuntimeTest, ComposeService
from seedemu.testing.runtime import ADDRESS_LABEL, NODE_LABEL


BOT_CONTROLLER_IP = "10.150.0.66"
EXPECTED_BOT_COUNT = 8


def discover_bots(test: ComposeRuntimeTest) -> List[ComposeService]:
    bots: List[ComposeService] = []
    for name, service in test.compose.get("services", {}).items():
        labels = dict(service.get("labels", {}))
        node_name = str(labels.get(NODE_LABEL, ""))
        if node_name.startswith("bot-node-"):
            address = str(labels.get(ADDRESS_LABEL, "")).split("/", 1)[0]
            bots.append(ComposeService(name=str(name), address=address, labels=labels))
    bots.sort(key=lambda service: str(service.labels.get(NODE_LABEL, service.name)))
    return bots


def main() -> int:
    test = ComposeRuntimeTest(__file__)
    controller = test.require_service(150, "bot-controller", "AS150 BYOB controller is generated")
    victim = test.require_service(151, "host_0", "AS151 victim is generated")
    victim_router = test.require_service(151, "router0", "AS151 victim access router is generated")
    legitimate_client = test.require_service(153, "host_0", "AS153 legitimate client is generated")
    bots = discover_bots(test)

    test.structural_check(
        "Y13 creates eight distributed bot clients",
        len(bots) == EXPECTED_BOT_COUNT,
        f"found {len(bots)} bot clients",
    )

    if controller:
        test.structural_check(
            "bot controller uses the expected address",
            controller.address == BOT_CONTROLLER_IP,
            f"controller address={controller.address}",
        )
        test.exec_check(
            "controller has BYOB and classroom helpers",
            controller,
            "test -f /tmp/byob/byob/server.py && test -x /bin/start-byob-shell "
            "&& test -x /bin/show-attack-command",
            retries=30,
            interval=3,
        )
        test.exec_check(
            "controller exposes the BYOB dropper endpoint",
            controller,
            "curl -fsS http://127.0.0.1:446/clients/droppers/client.py >/dev/null",
            retries=60,
            interval=5,
            timeout=45,
        )

    for bot in bots:
        label = bot.labels.get(NODE_LABEL, bot.name)
        test.exec_check(
            f"{label} has BYOB and the bounded attack agent",
            bot,
            "test -x /tmp/byob_client_dropper_runner && test -x /opt/botnet-dos/bot_attack.py "
            "&& python3 /opt/botnet-dos/bot_attack.py --dry-run --json >/dev/null",
            retries=30,
            interval=3,
        )

    if victim:
        test.exec_check(
            "victim UDP sink and HTTP service are running",
            victim,
            "ps -ef | grep -F '/opt/botnet-dos/udp_sink.py' | grep -v grep >/dev/null "
            "&& python3 -c \"import json,urllib.request; "
            "d=json.load(urllib.request.urlopen('http://127.0.0.1:8000/health')); "
            "assert d['status'] == 'ok', d\"",
            retries=30,
            interval=2,
        )
        test.exec_check(
            "traffic visualizer serves Y13 configuration",
            victim,
            "python3 -c \"import json,urllib.request; "
            "d=json.load(urllib.request.urlopen('http://127.0.0.1:8080/api/config')); "
            "assert d['frontend']['options']['bot_count'] == 8, d\"",
            retries=30,
            interval=2,
        )

    if victim_router:
        test.exec_check(
            "victim access router includes the runtime link controller",
            victim_router,
            "test -x /opt/botnet-dos/traffic_visualizer/network_control.py",
            retries=1,
            interval=1,
        )

    if legitimate_client:
        test.exec_check(
            "health probe API serves latency and goodput samples with CORS",
            legitimate_client,
            "python3 -c \"import json,urllib.request; "
            "r=urllib.request.urlopen('http://127.0.0.1:8080/api/health'); "
            "assert r.headers['Access-Control-Allow-Origin'] == '*', r.headers; "
            "d=json.load(r); assert d['sample_count'] >= 2, d; "
            "assert d['bandwidth_sample_count'] >= 1, d\"",
            retries=30,
            interval=2,
        )

    if bots and victim:
        test.exec_check(
            "one bot can send a tiny smoke stream to the fixed victim",
            bots[0],
            "python3 /opt/botnet-dos/bot_attack.py --duration 0.2 --pps 5 "
            "--packet-size 64 --json >/dev/null",
            retries=10,
            interval=2,
        )
        test.exec_check(
            "victim visualizer observes the smoke stream",
            victim,
            "python3 -c \"import json,urllib.request; "
            "d=json.load(urllib.request.urlopen('http://127.0.0.1:8080/api/stats')); "
            "assert d['total_packets'] >= 1, d\"",
            retries=10,
            interval=1,
        )

    test.write_summary("y13-botnet-dos-runtime-test.json")
    return test.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())
