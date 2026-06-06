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

    checks: List[Dict[str, object]] = []
    compose_text = read(compose) if compose.exists() else ""

    checks.append(record("compose exists", compose.exists(), str(compose)))
    checks.append(record("compose enables IPv6", "enable_ipv6: true" in compose_text, "IPv6 is explicit for A15"))
    checks.append(record("compose has IPv6 IPAM", "subnet: 2000:" in compose_text, "IPv6 subnets are generated"))
    checks.append(record("compose assigns IPv6 addresses", "ipv6_address:" in compose_text, "IPv6 node addresses are generated"))

    frr_conf = read_container_file(output, "brdnode_151_router0", "/etc/frr/frr.conf")
    bird_conf = read_container_file(output, "brdnode_152_router0", "/etc/bird/bird.conf")
    as2_bird = read_container_file(output, "brdnode_2_r1", "/etc/bird/bird.conf")
    as2_frr = read_container_file(output, "brdnode_2_r2", "/etc/frr/frr.conf")

    checks.append(record("FRR has IPv6 BGP", "address-family ipv6 unicast" in frr_conf, "FRR renders IPv6 BGP"))
    checks.append(record("FRR has OSPFv3", "router ospf6" in frr_conf, "FRR renders OSPFv3"))
    checks.append(record("BIRD has IPv6 BGP table", "ipv6 table t_bgp6" in bird_conf, "BIRD renders IPv6 BGP"))
    checks.append(record("BIRD has OSPFv3 table", "ipv6 table t_ospf6" in bird_conf or "protocol ospf ospf6" in bird_conf, "BIRD renders IPv6 OSPF"))
    checks.append(record("AS2 BIRD side has IPv6", "ipv6 table" in as2_bird, "BIRD transit side is dual stack"))
    checks.append(record("AS2 FRR side has IPv6", "address-family ipv6 unicast" in as2_frr, "FRR transit side is dual stack"))

    summary = {
        "example": "A15",
        "compose_file": str(compose),
        "results": checks,
        "failures": [item["name"] for item in checks if item["status"] == "failed"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))

    if artifact_dir:
        path = Path(artifact_dir) / "a15-generated-config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return 1 if summary["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
