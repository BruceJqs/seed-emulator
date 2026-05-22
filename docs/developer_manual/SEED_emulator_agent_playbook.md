# SEED 控制面与智能体展示 Playbook

## 0. 现场约定
- 线路 1: `seed-labs/seed-emulator` / `feat/bgp-control-plane-core`
- 线路 2: `seed-labs/seed-emulator` / `feat/seed-codex-harness`, 子仓 `subrepos/seed-agent` / `feat/codex-integration`
- WSL 无 GUI: 页面都用 Windows 浏览器打开 `http://localhost:<port>/`
- Compose 用 `docker-compose`, 本机没有 `docker compose`
- 每次只跑一个例子, 每次都指定 `COMPOSE_PROJECT_NAME`

常用别名:
```bash
source ~/.bashrc
seedcore
seeda12; seeda13; seeda14; seedb30
dcbuild; dcup; dcdown
dockps
docksh <container-id-or-prefix>
```

如果别名不可用:
```bash
alias dcbuild='DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 docker-compose build'
alias dcup='docker-compose up -d'
alias dcdown='docker-compose down --remove-orphans'
alias dockps='docker ps --format "{{.ID}}  {{.Names}}"'
docksh() { docker exec -it "$1" /bin/bash; }
```

通用清场:
```bash
cd <example>/output
COMPOSE_PROJECT_NAME=<name> docker-compose down --remove-orphans
```

找容器:
```bash
dockps | grep -E 'as2|as151|as180|router|exabgp|looking'
docker ps --format '{{.Names}}' | grep 'as180.*exabgp'
```

## 1. 阶段一: 人工/Codex 先验控制面能力

讲法:
- Router 有 `routingBackend`: 默认 `bird`, 可选 `frr` / `exabgp`
- `Ebgp/Ibgp/Ospf` 只记录协议 intent
- `Routing` 按 Router backend 生成 BIRD/FRR/ExaBGP 配置
- Looking Glass 是 Service, 通过 Binding 安装到 host, 再声明观察哪些 router

### A12: FRR / BIRD mixed backend

拓扑:
- AS2: `r1` 是 BIRD, `r2` 是 FRR, 两者在 `net0` 内部互联
- AS151: `router0` 是 FRR, `web` 是主机, 通过 IX100 接 AS2/r1
- AS152: `router0` 是 BIRD, `web` 是主机, 通过 IX101 接 AS2/r2

源码位置:
- `seedemu/core/AutonomousSystem.py`: `createRouter(..., routingBackend=...)`
- `seedemu/core/Node.py`: `Router.get/setRoutingBackend`
- `seedemu/layers/Routing.py`: BIRD/FRR 后端渲染
- `seedemu/layers/_bgp_metadata.py`: BGP session / policy intent
- `seedemu/layers/Ebgp.py`, `Ibgp.py`, `Ospf.py`: 记录协议 intent
- `seedemu/layers/FrrBgp.py`: 旧 API 兼容 shim
- `examples/basic/A12_bgp_mixed_backend`

启动:
```bash
seedcore
. .venv/bin/activate
PYTHONPATH=. python examples/basic/A12_bgp_mixed_backend/bgp_mixed_backend.py
cd examples/basic/A12_bgp_mixed_backend/output
DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 COMPOSE_PROJECT_NAME=a12 docker-compose build
COMPOSE_PROJECT_NAME=a12 docker-compose up -d
```

验配置:
```bash
grep -R "apt-get install.*frr\\|/etc/frr/frr.conf\\|bird -d" -n brdnode_* Dockerfile docker-compose.yml 2>/dev/null
FRR_AS2=$(docker ps --format '{{.Names}}' | grep 'as2.*r2')
FRR_AS151=$(docker ps --format '{{.Names}}' | grep 'as151.*router0')
BIRD_AS2=$(docker ps --format '{{.Names}}' | grep 'as2.*r1')
BIRD_AS152=$(docker ps --format '{{.Names}}' | grep 'as152.*router0')
docker exec "$FRR_AS2" sh -lc 'test -f /etc/frr/frr.conf && ! pgrep bird && sed -n "1,220p" /etc/frr/frr.conf'
docker exec "$BIRD_AS2" sh -lc 'test -f /etc/bird/bird.conf && sed -n "1,220p" /etc/bird/bird.conf'
```

验协议/路由:
```bash
docker exec "$FRR_AS2" vtysh -c 'show bgp summary' -c 'show ip ospf neighbor' -c 'show bgp ipv4 unicast'
docker exec "$FRR_AS151" vtysh -c 'show bgp summary' -c 'show ip route bgp'
docker exec "$BIRD_AS2" birdc show protocols
docker exec "$BIRD_AS2" birdc show route all
docker exec "$BIRD_AS152" birdc show protocols
docker exec "$BIRD_AS152" birdc show route all
curl --noproxy '*' http://127.0.0.1:8080/pro/home
```

通过点:
- FRR 节点 Dockerfile 安装 `frr`
- FRR 节点没有 BIRD 进程
- `/etc/frr/frr.conf` 有 BGP/OSPF、route-map、large-community、local-pref
- BIRD 节点 `birdc show protocols` 正常
- FRR/BIRD 都能看到学到的对端前缀

清场:
```bash
COMPOSE_PROJECT_NAME=a12 docker-compose down --remove-orphans
```

### A13: ExaBGP IX router

拓扑:
- AS2: `router0` 是 BIRD provider edge
- AS180: `exabgp` 是 `routingBackend="exabgp"` 的 Router
- IX100: AS180 直接以 `10.100.0.180` 上 IX, 和 AS2 建 eBGP

源码位置:
- `seedemu/core/Node.py`: `Router.addBgpAnnouncement`
- `seedemu/layers/Routing.py`: ExaBGP backend、event sink、dashboard、live FIFO
- `seedemu/layers/Ebgp.py`: AS2/AS180 eBGP intent
- `examples/basic/A13_exabgp_control_plane`

启动:
```bash
seedcore
. .venv/bin/activate
PYTHONPATH=. python examples/basic/A13_exabgp_control_plane/exabgp_control_plane.py
cd examples/basic/A13_exabgp_control_plane/output
DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 COMPOSE_PROJECT_NAME=a13 docker-compose build
COMPOSE_PROJECT_NAME=a13 docker-compose up -d
```

验配置:
```bash
EXA=$(docker ps --format '{{.Names}}' | grep 'as180.*exabgp')
R2=$(docker ps --format '{{.Names}}' | grep 'as2.*router0')
docker exec "$EXA" sh -lc 'test -f /etc/exabgp/exabgp.conf && sed -n "1,180p" /etc/exabgp/exabgp.conf'
docker exec "$EXA" sh -lc 'test -p /run/exabgp/live.in && ps aux | grep -E "exabgp|dashboard|live_control" | grep -v grep'
docker exec "$EXA" sh -lc 'tail -n 50 /var/log/exabgp/exabgp.log; tail -n 20 /var/log/exabgp/events.jsonl'
```

验路由和在线 announce:
```bash
docker exec "$R2" birdc show protocols
docker exec "$R2" birdc show route for 198.51.100.1 all
docker exec "$EXA" sh -lc "printf '%s\n' 'announce route 203.2.3.0/24 next-hop self' > /run/exabgp/live.in"
sleep 3
docker exec "$R2" birdc show route for 203.2.3.1 all
docker exec "$EXA" tail -n 20 /var/log/exabgp/live-control.log
docker exec "$EXA" sh -lc "printf '%s\n' 'withdraw route 203.2.3.0/24 next-hop self' > /run/exabgp/live.in"
sleep 3
docker exec "$R2" birdc show route for 203.2.3.1 all
curl --noproxy '*' http://127.0.0.1:5001/
curl --noproxy '*' http://127.0.0.1:8080/pro/home
```

通过点:
- ExaBGP router 安装 `exabgp`
- `local-as 180`, `peer-as 2`, `neighbor 10.100.0.2`
- `198.51.100.0/24` 被 AS2 学到
- 写 `/run/exabgp/live.in` 后新前缀出现, withdraw 后消失
- dashboard/event log 可达

清场:
```bash
COMPOSE_PROJECT_NAME=a13 docker-compose down --remove-orphans
```

### B30: mini Internet + AS180 ExaBGP IX router

拓扑:
- B00 mini Internet 原拓扑: AS2/3/4/11/12 为 transit, AS150+ 为 stub
- AS180: 新增 ExaBGP router, 挂在 IX100, 地址 `10.100.0.180`
- AS180 和 AS2/r100、AS3/r100 建 eBGP, 宣告 `203.0.113.0/24`、`203.0.114.0/24`

源码位置:
- `examples/internet/B30_mini_internet_exabgp_ix`
- `examples/internet/B00_mini_internet`
- `seedemu/layers/Routing.py`: ExaBGP backend
- `seedemu/layers/Ebgp.py`: IX peering intent

启动:
```bash
seedcore
. .venv/bin/activate
PYTHONPATH=. python examples/internet/B30_mini_internet_exabgp_ix/mini_internet_exabgp_ix.py amd
cd examples/internet/B30_mini_internet_exabgp_ix/output
DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 COMPOSE_PROJECT_NAME=b30 docker-compose build
COMPOSE_PROJECT_NAME=b30 docker-compose up -d
```

验配置:
```bash
EXA=$(docker ps --format '{{.Names}}' | grep 'as180.*exabgp')
R2=$(docker ps --format '{{.Names}}' | grep 'as2.*r100')
R3=$(docker ps --format '{{.Names}}' | grep 'as3.*r100')
docker exec "$EXA" sh -lc 'sed -n "1,240p" /etc/exabgp/exabgp.conf'
docker exec "$EXA" sh -lc 'test -p /run/exabgp/live.in && ps aux | grep -E "exabgp|dashboard|live_control" | grep -v grep'
```

验路由和在线 announce:
```bash
docker exec "$R2" birdc show protocols
docker exec "$R3" birdc show protocols
docker exec "$R2" birdc show route for 203.0.113.1 all
docker exec "$R3" birdc show route for 203.0.113.1 all
docker exec "$EXA" sh -lc "printf '%s\n' 'announce route 203.2.3.0/24 next-hop self' > /run/exabgp/live.in"
sleep 3
docker exec "$R2" birdc show route for 203.2.3.1 all
docker exec "$R3" birdc show route for 203.2.3.1 all
docker exec "$EXA" sh -lc "printf '%s\n' 'withdraw route 203.2.3.0/24 next-hop self' > /run/exabgp/live.in"
sleep 3
docker exec "$R2" birdc show route for 203.2.3.1 all
curl --noproxy '*' http://127.0.0.1:5106/
curl --noproxy '*' http://127.0.0.1:8080/pro/home
```

通过点:
- AS180 是 IX 直连 Router, 不是普通 host demo
- AS2/r100、AS3/r100 都和 AS180 有 BGP session
- 两个静态前缀可见
- live announce/withdraw 可见
- event log/dashboard 可达

清场:
```bash
COMPOSE_PROJECT_NAME=b30 docker-compose down --remove-orphans
```

### A14: Classic Looking Glass + event dashboard

拓扑:
- AS2/router0: BIRD router, Classic LG 观察对象
- AS2/looking-glass: Web host, 安装 `BgpLookingGlassService`
- AS151/router0: BIRD peer
- AS151/event-viewer: ExaBGP event-stream dashboard
- IX100: AS2 与 AS151 peering

源码位置:
- `seedemu/services/BgpLookingGlassService.py`: Service + Binding + `.addRouter(asn, router)`
- `seedemu/services/ExaBgpService.py`: event stream view
- `examples/basic/A14_bgp_event_looking_glass`

启动:
```bash
seedcore
. .venv/bin/activate
PYTHONPATH=. python examples/basic/A14_bgp_event_looking_glass/bgp_event_looking_glass.py
cd examples/basic/A14_bgp_event_looking_glass/output
DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 COMPOSE_PROJECT_NAME=a14 docker-compose build
COMPOSE_PROJECT_NAME=a14 docker-compose up -d
```

验 route-state:
```bash
LG=$(docker ps --format '{{.Names}}' | grep 'as2.*looking-glass')
R2=$(docker ps --format '{{.Names}}' | grep 'as2.*router0')
docker exec "$LG" sh -lc 'ps aux | grep -E "seed-lg|frontend.py" | grep -v grep'
docker exec "$R2" birdc show protocols
docker exec "$R2" birdc show route all
curl --noproxy '*' http://127.0.0.1:5002/
```

验 event-stream:
```bash
EVT=$(docker ps --format '{{.Names}}' | grep 'as151.*ExaBGP')
R151=$(docker ps --format '{{.Names}}' | grep 'as151.*router0')
docker exec "$EVT" sh -lc 'ps aux | grep -E "exabgp|dashboard|live_control" | grep -v grep'
docker exec "$EVT" sh -lc 'sed -n "1,160p" /etc/exabgp/exabgp.conf'
docker exec "$EVT" sh -lc 'tail -n 50 /var/log/exabgp/events.jsonl; tail -n 50 /var/log/exabgp/exabgp.log'
docker exec "$R151" birdc show protocols
docker exec "$EVT" sh -lc "printf '%s\n' 'announce route 203.2.4.0/24 next-hop self' > /run/exabgp/live.in"
docker exec "$R151" birdc show route for 203.2.4.1 all
curl --noproxy '*' http://127.0.0.1:5003/api/events
docker exec "$EVT" sh -lc "printf '%s\n' 'withdraw route 203.2.4.0/24 next-hop self' > /run/exabgp/live.in"
curl --noproxy '*' http://127.0.0.1:5003/
curl --noproxy '*' http://127.0.0.1:8080/pro/home
```

通过点:
- `5002` 是 Classic LG route-state 页面
- `5003` 是 ExaBGP event-stream 页面
- LG frontend/proxy 正常
- LG 绑定的是 AS2/router0 BIRD router
- AS151/router0 有 `exabgp_65020 Established`
- 写 `/run/exabgp/live.in` 后 route 和 `/api/events` 都有证据

清场:
```bash
COMPOSE_PROJECT_NAME=a14 docker-compose down --remove-orphans
```

## 2. 阶段二: seed-codex 接管同一运行态

前提:
- 阶段一已经验证控制面能力成立
- 只保留一个 runtime 在线
- agent 不看源码拓扑, 不改配置

命令:
```bash
seedcodex
scripts/seed-codex status
scripts/seed-codex inspect
scripts/seed-codex ui -m gpt-5.4 -c 'model_reasoning_effort="low"'
```

通用 prompt:
```text
接管当前唯一在线 runtime。不要看源码拓扑，不要修改配置。
请从运行态证据识别当前网络里的 FRR/ExaBGP/Looking Glass 能力，
说明它们各自在哪些节点上、状态是否正常、证据来自哪些路由表/配置/日志/页面。
```

B30 prompt:
```text
接管当前 B30。不要修改配置，先找到 AS180 ExaBGP IX router，
说明它和 AS2/r100、AS3/r100 的 BGP 对等关系，并给出 route、
event、dashboard、process、config 和日志证据。
```

讲法:
- 高层判断走 SeedAgent
- 底层证据走 SeedOps
- shell 只补充证据

## 3. 端口速记
- Map: `http://localhost:8080/pro/home`
- A13 ExaBGP dashboard: `http://localhost:5001/`
- A14 Classic LG: `http://localhost:5002/`
- A14 event dashboard: `http://localhost:5003/`
- B30 AS180 dashboard: `http://localhost:5106/`
