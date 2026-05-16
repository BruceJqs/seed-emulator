# Clean VM Handoff Package

## Goal

This package is for moving the current SEED agent and BGP control-plane work to a clean VM and running the demos without relying on local WSL state.

Prioritize the control-plane demos first:

| Priority | Feature | Example | Branch |
|---|---|---|---|
| 1 | FRR backend | `examples/basic/A12_bgp_mixed_backend` | `feat/bgp-control-plane-core` |
| 2 | ExaBGP tool node | `examples/basic/A13_exabgp_control_plane` | `feat/bgp-control-plane-core` |
| 3 | ExaBGP IX router | `examples/internet/B30_mini_internet_exabgp_ix` | `feat/bgp-control-plane-core` |
| 4 | Classic LG + event view | `examples/basic/A14_bgp_event_looking_glass` | `feat/bgp-control-plane-core` |
| 5 | Agent attached runtime | `examples/agent-specific/Z30_b30_mini_internet_exabgp_ix` and related packs | `feat/seed-codex-harness` |

## Branch Roles

| Branch | Purpose | Merge order |
|---|---|---|
| `feat/bgp-control-plane-core` | FRR, ExaBGP, Looking Glass core examples and runtime tests | Merge first |
| `feat/seed-codex-harness` | `seed-codex`, SeedAgent/SeedOps integration, skills, mission packs, demo bundles | Merge second |
| `feat/mcp-server` | Integration/reference branch with combined history and presentation material | Keep as reference unless intentionally integrating |
| `subrepos/seed-agent:feat/codex-integration` | SeedAgent subrepo branch used by the harness branch | Checkout through submodule |

Do not merge `feat/mcp-server` into `master` as the clean path. Use the two split branches above for review and integration.

## Clean VM Requirements

Use an SSD/NVMe-backed Linux VM if possible. Avoid placing Docker root or the repository on a slow Windows-mounted path.

Required tools:

```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-venv python3-pip curl jq make docker.io docker-compose-plugin
sudo usermod -aG docker "$USER"
newgrp docker
```

Recommended kernel/network precheck:

```bash
docker version
docker compose version
df -hT / /home /var/lib/docker 2>/dev/null || true
cat /proc/sys/net/bridge/bridge-nf-call-iptables 2>/dev/null || true
cat /proc/sys/net/bridge/bridge-nf-call-ip6tables 2>/dev/null || true
```

If `bridge-nf-call-iptables` or `bridge-nf-call-ip6tables` is `1`, record it as an environment risk for runtime network tests. It does not explain Docker build slowness, but it can affect container forwarding behavior.

## Checkout

```bash
git clone <repo-url> seed-emulator-harness
cd seed-emulator-harness
git fetch origin
git checkout feat/bgp-control-plane-core
```

For the harness branch:

```bash
git checkout feat/seed-codex-harness
git submodule update --init --recursive
git -C subrepos/seed-agent checkout feat/codex-integration
```

## Python Build Environment

Use a local venv for source compilation:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install geopy requests docker PyYAML pytest
```

## Demo Build Rule

Do fresh source builds before the demo, not during the live demo. Docker image export can be slow on WSL or slow disks.

Always use a unique Compose project name. Many SEED outputs live in directories named `output`; default Compose project names can collide and reuse stale images or networks.

Pattern:

```bash
COMPOSE_PROJECT_NAME=a12 docker compose up -d
COMPOSE_PROJECT_NAME=a12 docker compose down --remove-orphans
```

## A12 FRR Mixed Backend

Purpose: prove FRR is a real routing backend interoperating with BIRD.

Build:

```bash
git checkout feat/bgp-control-plane-core
. .venv/bin/activate
PYTHONPATH=. python examples/basic/A12_bgp_mixed_backend/bgp_mixed_backend.py amd
cd examples/basic/A12_bgp_mixed_backend/output
COMPOSE_PROJECT_NAME=a12 docker compose build
```

Run:

```bash
COMPOSE_PROJECT_NAME=a12 docker compose up -d
```

Open:

```text
http://<vm-ip>:8080/pro/home
```

Verify:

```bash
curl --noproxy '*' -I http://127.0.0.1:8080/pro/home
docker exec as151brd-router0-10.151.0.254 vtysh -c 'show ip bgp summary'
docker exec as2brd-r2-10.2.0.253 vtysh -c 'show ip bgp summary'
docker exec as152brd-router0-10.152.0.254 birdc show protocols
docker exec as152brd-router0-10.152.0.254 birdc show route 10.151.0.0/24 all
```

Expected control-plane evidence:

| Check | Expected |
|---|---|
| `AS151/router0` | FRR present, `vtysh` works, eBGP to `10.100.0.2` established |
| `AS2/r2` | FRR present, iBGP to `10.0.0.1` established, eBGP to AS152 established |
| `AS152/router0` | BIRD present, BGP to AS2 established |
| Route evidence | AS152 sees `10.151.0.0/24` with AS path through AS2/AS151 |

Stop:

```bash
COMPOSE_PROJECT_NAME=a12 docker compose down --remove-orphans
```

## A13 ExaBGP Control-Plane Tool

Purpose: show ExaBGP as a BGP control-plane tool node with config, process, event log and dashboard.

Build:

```bash
cd <repo-root>
git checkout feat/bgp-control-plane-core
. .venv/bin/activate
PYTHONPATH=. python examples/basic/A13_exabgp_control_plane/exabgp_control_plane.py amd
cd examples/basic/A13_exabgp_control_plane/output
COMPOSE_PROJECT_NAME=a13 docker compose build
```

Run:

```bash
COMPOSE_PROJECT_NAME=a13 docker compose up -d
```

Open:

```text
Map:       http://<vm-ip>:8080/pro/home
Dashboard: http://<vm-ip>:5001/
```

Verify:

```bash
curl --noproxy '*' -I http://127.0.0.1:5001/
docker ps --format '{{.Names}}'
docker exec as151h-control-plane-tool-10.151.0.200 exabgp --version
docker exec as151h-control-plane-tool-10.151.0.200 sed -n '1,220p' /etc/exabgp/exabgp.conf
docker exec as2brd-router0-10.2.0.254 birdc show route 198.51.100.0/24 all || true
```

Stop:

```bash
COMPOSE_PROJECT_NAME=a13 docker compose down --remove-orphans
```

## B30 Mini Internet ExaBGP IX Tool

Purpose: show ExaBGP as a real IX-attached BGP speaker in mini Internet.

Build:

```bash
cd <repo-root>
git checkout feat/bgp-control-plane-core
. .venv/bin/activate
PYTHONPATH=. python examples/internet/B30_mini_internet_exabgp_ix/mini_internet_exabgp_ix.py amd
cd examples/internet/B30_mini_internet_exabgp_ix/output
COMPOSE_PROJECT_NAME=b30 docker compose build
```

Run:

```bash
COMPOSE_PROJECT_NAME=b30 docker compose up -d
```

Open:

```text
Map:       http://<vm-ip>:8080/pro/home
Dashboard: http://<vm-ip>:5130/
```

Verify:

```bash
curl --noproxy '*' -I http://127.0.0.1:5130/
docker exec as180brd-ExaBGP_Control_Plane_Tool-10.100.0.180 exabgp --version
docker exec as180brd-ExaBGP_Control_Plane_Tool-10.100.0.180 sed -n '1,260p' /etc/exabgp/exabgp.conf
docker exec as2brd-r100-10.100.0.2 birdc show route 203.0.113.0/24 all || true
docker exec as3brd-r100-10.100.0.3 birdc show route 203.0.113.0/24 all || true
```

Expected:

| Check | Expected |
|---|---|
| AS180 tool router | ExaBGP process and config present |
| Peers | AS2/r100 and AS3/r100 configured as neighbors |
| Announcement | `203.0.113.0/24` visible on AS2 and AS3 |
| Dashboard | `5130` returns HTTP 200 |

Stop:

```bash
COMPOSE_PROJECT_NAME=b30 docker compose down --remove-orphans
```

## A14 Looking Glass + Event View

Purpose: show route-state and event-stream observation as separate views.

Build:

```bash
cd <repo-root>
git checkout feat/bgp-control-plane-core
. .venv/bin/activate
PYTHONPATH=. python examples/basic/A14_bgp_event_looking_glass/bgp_event_looking_glass.py amd
cd examples/basic/A14_bgp_event_looking_glass/output
COMPOSE_PROJECT_NAME=a14 docker compose build
```

Run:

```bash
COMPOSE_PROJECT_NAME=a14 docker compose up -d
```

Open:

```text
Map:             http://<vm-ip>:8080/pro/home
Classic LG:      http://<vm-ip>:5002/
Event dashboard: http://<vm-ip>:5003/
```

Verify:

```bash
curl --noproxy '*' -I http://127.0.0.1:5002/
curl --noproxy '*' -I http://127.0.0.1:5003/
docker ps --format '{{.Names}}'
```

Stop:

```bash
COMPOSE_PROJECT_NAME=a14 docker compose down --remove-orphans
```

## Harness / Agent Runtime Demo

Use this after the control-plane features are proven.

```bash
git checkout feat/seed-codex-harness
git submodule update --init --recursive
git -C subrepos/seed-agent checkout feat/codex-integration
scripts/seed-codex status
scripts/seed-codex inspect
scripts/seed-codex ui -m gpt-5.4 -c 'model_reasoning_effort="low"'
```

Recommended first prompt:

```text
接管当前唯一在线的 SEED 网络。先不要修改配置，只通过运行态证据说明这个网络里有哪些关键节点、服务、路由状态和可视化入口。
```

For B30:

```text
接管当前 B30。不要修改配置，找到 AS180 ExaBGP IX 工具 router，说明它和 AS2/r100、AS3/r100 的 BGP 对等关系，并给出 route、event、dashboard、process、config 和日志证据。
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Build spends minutes at `writing image sha256` | Slow disk, WSL VHDX on HDD, Docker overlay export | Build once before demo; use SSD/NVMe VM |
| Containers start but wrong daemon appears | Stale image from another `output` project | Use unique `COMPOSE_PROJECT_NAME`; rebuild target output |
| Network creation says pool overlaps | Old SEED Docker networks remain | Stop active experiment, remove only relevant old compose project/networks |
| Browser cannot open page | Port conflict or VM firewall | Check `docker ps`, use `curl --noproxy '*'`, open VM firewall |
| Runtime forwarding behaves oddly | Bridge netfilter enabled | Record environment risk; disable only if allowed by VM policy |

## Demo Order

1. A12: FRR/BIRD mixed backend control-plane evidence.
2. A13: ExaBGP single-peer tool node and dashboard.
3. B30: ExaBGP IX-attached multi-peer speaker in mini Internet.
4. A14: Classic route-state LG plus ExaBGP event dashboard.
5. Z30 or B29 with `seed-codex ui`: agent attached-runtime evidence and audit behavior.

