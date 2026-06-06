#!/usr/bin/env python3

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List


def read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def generated_file(output: Path, service: str, destination: str) -> Path:
    service_dir = output / service
    dockerfile = read(service_dir / "Dockerfile")
    for line in dockerfile.splitlines():
        parts = line.strip().split()
        if len(parts) >= 3 and parts[0] == "COPY" and parts[-1] == destination:
            return service_dir / parts[1]
    return service_dir / "__missing__"


def read_container_file(output: Path, service: str, destination: str) -> str:
    return read(generated_file(output, service, destination))


def record(name: str, passed: bool, message: str) -> Dict[str, object]:
    return {"name": name, "status": "passed" if passed else "failed", "message": message}


def main() -> int:
    example_dir = Path(os.environ.get("EXAMPLE_RUNNER_EXAMPLE_DIR", Path(__file__).parent)).resolve()
    artifact_dir = os.environ.get("EXAMPLE_RUNNER_ARTIFACT_DIR")
    output = example_dir / "output"
    compose = output / "docker-compose.yml"

    compose_text = read(compose) if compose.exists() else ""
    exabgp_conf = read_container_file(output, "hnode_180_exabgp", "/etc/exabgp/exabgp.conf")
    router_conf = read_container_file(output, "brdnode_2_router0", "/etc/bird/bird.conf")
    live_control = read_container_file(output, "hnode_180_exabgp", "/opt/exabgp/live_control.py")

    checks: List[Dict[str, object]] = [
        record("compose exists", compose.exists(), str(compose)),
        record("compose enables IPv6", "enable_ipv6: true" in compose_text, "IPv6 is explicit for A16"),
        record("compose assigns ExaBGP IPv6", "2000:8:0:64::b4" in compose_text, "ExaBGP host has explicit IPv6"),
        record("ExaBGP config uses IPv6 family", "ipv6 unicast" in exabgp_conf, "ExaBGP family is IPv6"),
        record("ExaBGP announces IPv6 prefix", "2000:b400:100::/64" in exabgp_conf, "static IPv6 announcement exists"),
        record("ExaBGP live control process is configured", "exabgp_live_control" in exabgp_conf, "ExaBGP starts live control as a process"),
        record("ExaBGP live FIFO is installed", "/run/exabgp/live.in" in live_control, "live control FIFO is configured"),
        record("router has IPv6 BGP table", "t_bgp6" in router_conf, "router peer renders IPv6 BGP"),
    ]

    summary = {
        "example": "A16",
        "compose_file": str(compose),
        "results": checks,
        "failures": [item["name"] for item in checks if item["status"] == "failed"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))

    if artifact_dir:
        path = Path(artifact_dir) / "a16-generated-config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return 1 if summary["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
