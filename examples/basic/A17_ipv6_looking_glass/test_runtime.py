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
    frr_conf = read_container_file(output, "brdnode_2_router0", "/etc/frr/frr.conf")
    bird_conf = read_container_file(output, "brdnode_151_router0", "/etc/bird/bird.conf")
    lg_start = read_container_file(output, "hnode_2_looking-glass", "/start.sh")
    frontend = read_container_file(output, "hnode_2_looking-glass", "/opt/seed-lg/frontend.py")
    router_start = read_container_file(output, "brdnode_2_router0", "/start.sh")

    checks: List[Dict[str, object]] = [
        record("compose exists", compose.exists(), str(compose)),
        record("compose enables IPv6", "enable_ipv6: true" in compose_text, "IPv6 is explicit for A17"),
        record("FRR exposes IPv6 route commands", "address-family ipv6 unicast" in frr_conf, "FRR renders IPv6 BGP"),
        record("BIRD exposes IPv6 route table", "t_bgp6" in bird_conf, "BIRD renders IPv6 route state"),
        record("Looking Glass uses route-state API", "/api/state" in frontend, "frontend exposes route-state API"),
        record("Looking Glass uses proxy URL mapping", "SEED_LG_PROXY_URLS" in lg_start, "frontend uses formatted proxy URLs"),
        record("Looking Glass is not ExaBGP event stream", "EXABGP_EVENT_LOG" not in lg_start, "route state and event stream stay separate"),
        record("router proxy includes IPv6 families", "SEED_LG_FAMILIES" in router_start and "ipv6" in router_start, "router proxy asks for IPv6 route state"),
    ]

    summary = {
        "example": "A17",
        "compose_file": str(compose),
        "results": checks,
        "failures": [item["name"] for item in checks if item["status"] == "failed"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))

    if artifact_dir:
        path = Path(artifact_dir) / "a17-generated-config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return 1 if summary["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
