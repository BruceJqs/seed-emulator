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
    lg_frontend = read_container_file(output, "hnode_2_looking-glass", "/opt/seed-lg/frontend.py")
    lg_start = read_container_file(output, "hnode_2_looking-glass", "/start.sh")
    event_frontend = read_container_file(output, "hnode_151_event-viewer", "/opt/exabgp/dashboard.py")
    event_config = read_container_file(output, "hnode_151_event-viewer", "/etc/exabgp/exabgp.conf")
    event_start = read_container_file(output, "hnode_151_event-viewer", "/start.sh")

    checks: List[Dict[str, object]] = [
        record("compose exists", compose.exists(), str(compose)),
        record("IPv4 default compose has no enable_ipv6", "enable_ipv6" not in compose_text, "A14 is IPv4-only by default"),
        record("Looking Glass has route-state API", "/api/state" in lg_frontend, "route-state observer API exists"),
        record("Looking Glass targets router", "SEED_LG_ROUTERS" in lg_start and "router0" in lg_start, "observed router is declared"),
        record("ExaBGP dashboard exists", "Flask" in event_frontend or "event" in event_frontend, "event dashboard is generated"),
        record("ExaBGP speaker config exists", "neighbor" in event_config, "ExaBGP config is generated"),
        record("ExaBGP event stream separate", "/run/exabgp/events.log" in event_start or "event_sink.py" in event_start, "event stream stays on ExaBGP speaker"),
        record("Looking Glass does not read events", "/run/exabgp/events.log" not in lg_frontend, "route-state observer is separate"),
    ]

    summary = {
        "example": "A14",
        "compose_file": str(compose),
        "results": checks,
        "failures": [item["name"] for item in checks if item["status"] == "failed"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))

    if artifact_dir:
        path = Path(artifact_dir) / "a14-generated-config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return 1 if summary["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
