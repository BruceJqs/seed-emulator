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
    start_script = read_container_file(output, "hnode_180_exabgp", "/start.sh")
    router_conf = read_container_file(output, "brdnode_2_router0", "/etc/bird/bird.conf")

    checks: List[Dict[str, object]] = [
        record("compose exists", compose.exists(), str(compose)),
        record("IPv4 default compose has no enable_ipv6", "enable_ipv6" not in compose_text, "A13 is IPv4-only by default"),
        record("ExaBGP config exists", "neighbor 10.100.0." in exabgp_conf, "ExaBGP peers with router on IX"),
        record("ExaBGP announces static route", "198.51.100.0/24" in exabgp_conf, "static announcement rendered"),
        record("ExaBGP runtime paths exist", "/run/exabgp/live.in" in start_script, "live control FIFO is prepared"),
        record("Router remains BIRD backend", "protocol bgp" in router_conf, "router backend remains routing daemon"),
    ]

    summary = {
        "example": "A13",
        "compose_file": str(compose),
        "results": checks,
        "failures": [item["name"] for item in checks if item["status"] == "failed"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))

    if artifact_dir:
        path = Path(artifact_dir) / "a13-generated-config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return 1 if summary["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
