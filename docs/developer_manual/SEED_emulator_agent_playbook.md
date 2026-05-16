# SEED Emulator 智能体接管 Playbook

## 0. 约定
- 主仓：`seed-labs/seed-emulator`
- 线路 1 分支：`feat/bgp-control-plane-core`
- 线路 2 分支：`feat/seed-codex-harness`
- 子仓：`subrepos/seed-agent`
- 子仓分支：`feat/codex-integration`
- WSL 访问浏览器优先用 `http://localhost:<port>/`

## 1. 快速别名
```bash
source ~/.bashrc
seedcore
seedcodex
seeda12
seeda13
seeda14
seedb30
```

```bash
dcbuild
dcup
dcdown
dockps
docksh <id>
```

## 2. 阶段一: 先证实控制面能力

原则:
- 每个例子都从源码重新生成 `output`
- 每次只跑一个例子
- 每次都用唯一 `COMPOSE_PROJECT_NAME`
- 先看配置，再看容器，再看协议和路由，再看页面和日志
- 最后再回到源码说明“这能力怎么接入 SEED”

### A12: FRR / BIRD mixed backend

实现位置:
- `seedemu/layers/FrrBgp.py`
- `seedemu/layers/_bgp_metadata.py`
- `seedemu/layers/Routing.py`
- `seedemu/layers/Ebgp.py`
- `seedemu/layers/Ibgp.py`
- `seedemu/layers/Ospf.py`
- `examples/basic/A12_bgp_mixed_backend`

先跑:
```bash
seedcore
. .venv/bin/activate
PYTHONPATH=. python examples/basic/A12_bgp_mixed_backend/bgp_mixed_backend.py
cd examples/basic/A12_bgp_mixed_backend/output
COMPOSE_PROJECT_NAME=a12 docker compose build
COMPOSE_PROJECT_NAME=a12 docker compose up -d
```

再验:
- `docker compose -p a12 ps`
- `docker exec <frr-router> sh -lc 'test -f /etc/frr/frr.conf && sed -n "1,220p" /etc/frr/frr.conf'`
- `docker exec <frr-router> vtysh -c 'show bgp summary'`
- `docker exec <bird-router> birdc show protocols`
- `docker exec <bird-router> birdc show route`
- `curl http://localhost:8080/pro/home`

讲法:
- FRR 是 SEED 的控制面 backend，不是运行时手补
- `FrrBgp.py` 负责把 router 标成 `frr`
- `_bgp_metadata.py` 负责记录 backend、session、export policy
- `Routing/Ebgp/Ibgp/Ospf` 根据 backend 生成不同配置

通过点:
- output 里 FRR 节点 Dockerfile 安装 `frr`
- FRR 节点没有启动 BIRD
- `/etc/frr/frr.conf` 存在且有 BGP/OSPF
- `vtysh` 能看到 `bgpd/ospfd`
- BIRD 节点 `birdc` 正常
- mixed backend 能学到前缀

失败点:
- FRR 容器里还有 BIRD 进程
- `frr.conf` 缺 BGP/OSPF
- BIRD/FRR 路由互学失败

### A13: ExaBGP 控制面工具节点

实现位置:
- `seedemu/services/ExaBgpService.py`
- `examples/basic/A13_exabgp_control_plane`

先跑:
```bash
seedcore
. .venv/bin/activate
PYTHONPATH=. python examples/basic/A13_exabgp_control_plane/exabgp_control_plane.py
cd examples/basic/A13_exabgp_control_plane/output
COMPOSE_PROJECT_NAME=a13 docker compose build
COMPOSE_PROJECT_NAME=a13 docker compose up -d
```

若 `5001` 已被 WSL/宿主占用:
- 临时把 generated `docker-compose.yml` 里的 `5001:5000` 改成 `5011:5000`
- 再 `COMPOSE_PROJECT_NAME=a13 docker compose up -d`

再验:
- `docker compose -p a13 ps`
- `docker exec <exabgp-node> sh -lc 'ps aux | grep -E "exabgp|python" | grep -v grep'`
- `docker exec <exabgp-node> sh -lc 'sed -n "1,160p" /etc/exabgp/exabgp.conf'`
- `docker exec <exabgp-node> sh -lc 'tail -n 40 /var/log/exabgp/exabgp.log'`
- `docker exec <peer-router> birdc show protocols`
- `docker exec <peer-router> birdc show route`
- `curl http://localhost:8080/pro/home`
- `curl http://localhost:5011/`  或 `5001`

讲法:
- `ExaBgpService.py` 把 ExaBGP 作为 SEED 的外部 speaker 接入
- `neighbor / local-as / peer-as / announcement` 都是代码生成，不是手改
- event sink 和 dashboard 是同一能力的两种观测面

通过点:
- `exabgp` 安装完成
- `exabgp.conf` 正确
- event sink / dashboard 可达
- peer router 学到 announcement prefix

失败点:
- 端口被占用
- `exabgp.conf` 不含正确 AS/neighbor/prefix
- peer router 没学到前缀

### B30: mini Internet + AS180 ExaBGP IX tool router

实现位置:
- `seedemu/services/ExaBgpService.py`
- `examples/internet/B30_mini_internet_exabgp_ix`

先跑:
```bash
seedcore
. .venv/bin/activate
PYTHONPATH=. python examples/internet/B30_mini_internet_exabgp_ix/mini_internet_exabgp_ix.py amd
cd examples/internet/B30_mini_internet_exabgp_ix/output
COMPOSE_PROJECT_NAME=b30 docker compose build
COMPOSE_PROJECT_NAME=b30 docker compose up -d
```

再验:
- `docker compose -p b30 ps`
- `docker exec as180brd-ExaBGP_Control_Plane_Tool-10.100.0.180 sh -lc 'ps aux | grep -E "exabgp|python|dashboard" | grep -v grep'`
- `docker exec as180brd-ExaBGP_Control_Plane_Tool-10.100.0.180 sh -lc 'sed -n "1,220p" /etc/exabgp/exabgp.conf'`
- `docker exec as180brd-ExaBGP_Control_Plane_Tool-10.100.0.180 sh -lc 'tail -n 40 /var/log/exabgp/events.jsonl; tail -n 40 /var/log/exabgp/exabgp.log'`
- `docker exec as2brd-r100-10.100.0.2 birdc show protocols`
- `docker exec as3brd-r100-10.100.0.3 birdc show protocols`
- `docker exec as2brd-r100-10.100.0.2 birdc show route 203.0.113.0/24 all`
- `docker exec as3brd-r100-10.100.0.3 birdc show route 203.0.113.0/24 all`
- `curl http://localhost:8080/pro/home`
- `curl http://localhost:5106/`

讲法:
- AS180 不是普通 host demo
- 它是 IX 直连 BGP speaker
- `ExaBgpService` 把 speaker 接入 SEED 的 routing metadata

通过点:
- AS180 ExaBGP 节点安装完成
- `/etc/exabgp/exabgp.conf` 正确
- AS2 / AS3 学到 `203.0.113.0/24`
- event sink / dashboard 可达
- dashboard 和 route-state 不混淆

失败点:
- event log 空
- peer router 没学到 prefix
- dashboard 200 但没有事件

### A14: Classic Looking Glass + event dashboard

实现位置:
- `seedemu/services/BgpLookingGlassService.py`
- `seedemu/services/ExaBgpService.py`
- `examples/basic/A14_bgp_event_looking_glass`

先跑:
```bash
seedcore
. .venv/bin/activate
PYTHONPATH=. python examples/basic/A14_bgp_event_looking_glass/bgp_event_looking_glass.py
cd examples/basic/A14_bgp_event_looking_glass/output
COMPOSE_PROJECT_NAME=a14 docker compose build
COMPOSE_PROJECT_NAME=a14 docker compose up -d
```

再验:
- `docker compose -p a14 ps`
- `docker exec as2h-looking-glass-10.2.0.71 sh -lc 'ps aux | grep -E "frontend|proxy|bird-lg" | grep -v grep'`
- `docker exec as151h-ExaBGP_Control_Plane_Tool-10.151.0.71 sh -lc 'ps aux | grep -E "exabgp|python" | grep -v grep'`
- `docker exec as151h-ExaBGP_Control_Plane_Tool-10.151.0.71 sh -lc 'sed -n "1,160p" /etc/exabgp/exabgp.conf'`
- `docker exec as151h-ExaBGP_Control_Plane_Tool-10.151.0.71 sh -lc 'tail -n 40 /var/log/exabgp/exabgp.log'`
- `curl http://localhost:5002/`
- `curl http://localhost:5003/`
- `curl http://localhost:8080/pro/home`

讲法:
- Classic LG 是 route-state view
- event dashboard 是 event-stream view
- 两者都由 SEED service 接入，但语义不同
- `BgpLookingGlassService.py` 负责 router 侧 proxy + frontend
- `ExaBgpService.py` 负责 event stream

通过点:
- Classic LG 页面可达
- event dashboard 可达
- proxy/frontend/exabgp 进程正常
- 绑定的是 Bird router
- event log 存在

失败点:
- 页面 200 但无数据
- frontend 起了，proxy 没起
- route-state 和 event-stream 混淆

## 3. 阶段二: 再让 seed-codex 接管同一运行态

前提:
- 第一阶段四个例子的能力已经人工/Codex 验证成立
- 只接管一个当前在线 runtime
- 不改配置，不看源码拓扑

推荐提示词:
```text
接管当前唯一在线 runtime。不要看源码拓扑，不要修改配置。
请从运行态证据识别当前网络里的 FRR/ExaBGP/Looking Glass 能力，
说明它们各自在哪些节点上、状态是否正常、证据来自哪些路由表/配置/日志/页面。
```

可执行命令:
```bash
seedcodex
bash scripts/seed-codex status
bash scripts/seed-codex inspect
bash scripts/seed-codex ui -m gpt-5.4 -c 'model_reasoning_effort="low"'
```

讲法:
- 高层判断走 SeedAgent
- 底层证据走 SeedOps
- shell 只补充证据

## 4. 切换和清场

每次换例子只做这几步:
```bash
cd <example>/output
COMPOSE_PROJECT_NAME=<name> docker compose down --remove-orphans
COMPOSE_PROJECT_NAME=<name> docker compose build
COMPOSE_PROJECT_NAME=<name> docker compose up -d
```

如果要换到下一个展示任务:
```bash
COMPOSE_PROJECT_NAME=<name> docker compose down --remove-orphans
```

## 5. 端口速记
- A12: `8080`
- A13: `8080` + tool dashboard `5001`，若冲突可临时改到 `5011`
- A14: `8080` + LG `5002` + event dashboard `5003`
- B30: `8080` + AS180 dashboard `5106`

## 6. 代码讲解顺序

先讲接入点，再讲生成逻辑:
- FRR: `FrrBgp.py` -> `_bgp_metadata.py` -> `Routing/Ebgp/Ibgp/Ospf`
- ExaBGP: `ExaBgpService.py` -> `examples/...`
- Looking Glass: `BgpLookingGlassService.py` -> `ExaBgpService.py`

对比要点:
- BIRD 是 SEED 原生 routing backend
- FRR 是可切换 backend
- ExaBGP 是 external speaker / tool node
- Classic LG 看 route-state
- Event dashboard 看事件流
