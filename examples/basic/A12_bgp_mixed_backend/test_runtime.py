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
    frr_conf = read_container_file(output, "brdnode_2_r2", "/etc/frr/frr.conf")
    frr_edge = read_container_file(output, "brdnode_151_router0", "/etc/frr/frr.conf")
    bird_conf = read_container_file(output, "brdnode_152_router0", "/etc/bird/bird.conf")
    bird_transit = read_container_file(output, "brdnode_2_r1", "/etc/bird/bird.conf")

    checks: List[Dict[str, object]] = [
        record("compose exists", compose.exists(), str(compose)),
        record("IPv4 default compose has no enable_ipv6", "enable_ipv6" not in compose_text, "A12 is IPv4-only by default"),
        record("FRR transit config exists", "router bgp 2" in frr_conf, "AS2 r2 uses FRR"),
        record("FRR edge config exists", "router bgp 151" in frr_edge, "AS151 edge uses FRR"),
        record("BIRD edge config exists", "protocol bgp" in bird_conf, "AS152 edge uses BIRD"),
        record("BIRD transit config exists", "protocol bgp" in bird_transit, "AS2 r1 uses BIRD"),
        record("FRR has OSPF", "router ospf" in frr_conf, "FRR renders OSPF"),
        record("BIRD has OSPF", "protocol ospf" in bird_transit, "BIRD renders OSPF"),
    ]

    summary = {
        "example": "A12",
        "compose_file": str(compose),
        "results": checks,
        "failures": [item["name"] for item in checks if item["status"] == "failed"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))

    if artifact_dir:
        path = Path(artifact_dir) / "a12-generated-config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return 1 if summary["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
