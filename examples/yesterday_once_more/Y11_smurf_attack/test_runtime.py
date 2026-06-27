#!/usr/bin/env python3

from __future__ import annotations

from seedemu.testing import ComposeRuntimeTest


MONITOR_OUTPUT = "/tmp/smurf-monitor.json"
MONITOR_LOG = "/tmp/smurf-monitor.log"


def main() -> int:
    test = ComposeRuntimeTest(__file__)

    attacker = test.require_service(150, "host_0", "AS150 attacker host is generated")
    victim = test.require_service(151, "host_0", "AS151 victim host is generated")
    amplifier0 = test.require_service(152, "host_0", "AS152 amplifier host_0 is generated")
    amplifier11 = test.require_service(152, "host_11", "AS152 amplifier host_11 is generated")
    target_router = test.require_service(152, "router0", "AS152 directed-broadcast router is generated")

    if target_router:
        test.exec_check(
            "AS152 router enables directed broadcast forwarding",
            target_router,
            "test -e /proc/sys/net/ipv4/conf/all/bc_forwarding "
            "&& test \"$(cat /proc/sys/net/ipv4/conf/all/bc_forwarding)\" = 1",
            retries=30,
            interval=3,
        )

    for service in [amplifier0, amplifier11]:
        if service:
            test.exec_check(
                "{} responds to broadcast ICMP echo".format(service.name),
                service,
                "test \"$(cat /proc/sys/net/ipv4/icmp_echo_ignore_broadcasts)\" = 0",
                retries=30,
                interval=3,
            )

    if victim and attacker:
        test.exec_check(
            "victim starts ICMP reply monitor",
            victim,
            "rm -f {out} {log}; "
            "(python3 /opt/smurf-lab/smurf_monitor.py --duration 8 --output {out} > {log} 2>&1 &) ; "
            "sleep 1".format(out=MONITOR_OUTPUT, log=MONITOR_LOG),
            retries=1,
            interval=1,
        )
        test.exec_check(
            "attacker sends spoofed ICMP requests to AS152 directed broadcast",
            attacker,
            "/opt/smurf-lab/trigger_attack.sh --count 3 --interval 0.2",
            retries=10,
            interval=2,
        )
        test.exec_check(
            "victim receives multiple reflected ICMP echo replies",
            victim,
            "for i in $(seq 1 12); do [ -s {out} ] && break; sleep 1; done; "
            "python3 -c \"import json; d=json.load(open('{out}')); "
            "assert d['reply_count'] >= 6, d; "
            "assert len(d['unique_reply_sources']) >= 2, d\"".format(out=MONITOR_OUTPUT),
            retries=1,
            interval=1,
        )

    test.write_summary("y11-smurf-attack-runtime-test.json")
    return test.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())
