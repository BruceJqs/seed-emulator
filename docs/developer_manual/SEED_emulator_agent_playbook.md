# SEED Emulator 智能体接管 Playbook

## 0. 约定
- 主仓：`seed-labs/seed-emulator`
- 线路 1 分支：`feat/bgp-control-plane-core`
- 线路 2 分支：`feat/seed-codex-harness`
- 子仓：`subrepos/seed-agent`
- 子仓分支：`feat/codex-integration`
- 这份 playbook 默认用 `docker-compose`
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

如果本机还没有这些别名，先把常用命令记成短名：
```bash
alias dcbuild='DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 docker-compose build'
alias dcup='docker-compose up -d'
alias dcdown='docker-compose down --remove-orphans'
alias dockps='docker ps --format "{{.ID}}  {{.Names}}"'
alias docksh='docker exec -it'
```

## 2. 阶段一: 先证实控制面能力

原则:
- 每个例子都从源码重新生成 `output`
- 每次只跑一个例子
- 每次都用唯一 `COMPOSE_PROJECT_NAME`
- 先看配置，再看容器，再看协议和路由，再看页面和日志
- 最后再回到源码说明“这能力怎么接入 SEED”
- 每次换例子前先 `docker-compose down --remove-orphans`
- 每次只用一个 `COMPOSE_PROJECT_NAME`
- WSL 里用 `localhost` 看页面，不走 GUI

### A12: FRR / BIRD mixed backend

实现位置:
- `seedemu/layers/FrrBgp.py`
- `seedemu/layers/_bgp_metadata.py`
- `seedemu/layers/Routing.py`
- `seedemu/layers/Ebgp.py`
- `seedemu/layers/Ibgp.py`
- `seedemu/layers/Ospf.py`
- `examples/basic/A12_bgp_mixed_backend`

拓扑:
- AS2: 两台路由器 `r1` / `r2`
- AS151: 一台 BIRD 路由器 `router0` + 一台主机 `web`
- AS152: 一台 BIRD 路由器 `router0` + 一台主机 `web`
- IX100 / IX101: 两个交换点

看谁:
- `as2brd-r1` / `as2brd-r2`: 对比 BIRD 和 FRR 混合 backend
- `as151brd-router0` / `as152brd-router0`: 看 BIRD 端协议和前缀学习
- `as151h-web` / `as152h-web`: 只做接入验证，不是主讲对象

测什么:
- AS2 里 `r2` 是 FRR backend，`r1` 是 BIRD backend
- AS151/AS152 通过 IX 学前缀
- FRR 节点和 BIRD 节点的 route policy、local-pref、community 是否一致

先跑:
```bash
seedcore
. .venv/bin/activate
PYTHONPATH=. python examples/basic/A12_bgp_mixed_backend/bgp_mixed_backend.py
cd examples/basic/A12_bgp_mixed_backend/output
DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 COMPOSE_PROJECT_NAME=a12 docker-compose build
COMPOSE_PROJECT_NAME=a12 docker-compose up -d
```

再验:
- `COMPOSE_PROJECT_NAME=a12 docker-compose ps`
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

拓扑:
- AS2: BIRD 路由器 `router0`
- AS151: BIRD 路由器 `router0` + ExaBGP 工具节点 `control-plane-tool`
- IX100: 单交换点

看谁:
- `as151h-ExaBGP_Control_Plane_Tool`: 这是主角，里面跑 ExaBGP
- `as2brd-router0` / `as151brd-router0`: 看邻居和路由学习

测什么:
- ExaBGP 节点是否安装并运行 `exabgp`
- `exabgp.conf` 是否正确声明 local ASN / peer ASN / neighbor / announce prefix
- peer router 是否学到工具节点宣布的前缀
- dashboard 是否显示事件流

先跑:
```bash
seedcore
. .venv/bin/activate
PYTHONPATH=. python examples/basic/A13_exabgp_control_plane/exabgp_control_plane.py
cd examples/basic/A13_exabgp_control_plane/output
DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 COMPOSE_PROJECT_NAME=a13 docker-compose build
COMPOSE_PROJECT_NAME=a13 docker-compose up -d
```

若 `5001` 已被占用:
- 先看 `docker ps | grep 5001`
- 再把 generated `docker-compose.yml` 里的 `5001:5000` 改成 `5101:5000`
- 然后重新 `COMPOSE_PROJECT_NAME=a13 docker-compose up -d`

再验:
- `COMPOSE_PROJECT_NAME=a13 docker-compose ps`
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

拓扑:
- AS180: ExaBGP IX tool router，挂在 IX100 上
- AS2 / AS3 / AS4 / AS11 / AS12: 上游/邻接自治域
- AS150~AS171: 大量边缘 AS，主要用来验证规模化传播
- IX100~IX105: 多个交换点

看谁:
- `as180brd-ExaBGP_Control_Plane_Tool`: 主角，验证 IX 直连 speaker
- `as2brd-r100` / `as3brd-r100`: 观察 `203.0.113.0/24`
- `seedemu_internet_map`: 观察拓扑展示

测什么:
- AS180 不是普通 host demo，而是 IX 上的 BGP speaker
- AS2/AS3 是否学到 `203.0.113.0/24`
- 是否可以不改配置文件，在线 announce / withdraw 新前缀
- event sink 是否记录 ExaBGP 事件
- dashboard 是否能解释 BGP 事件流

先跑:
```bash
seedcore
. .venv/bin/activate
PYTHONPATH=. python examples/internet/B30_mini_internet_exabgp_ix/mini_internet_exabgp_ix.py amd
cd examples/internet/B30_mini_internet_exabgp_ix/output
DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 COMPOSE_PROJECT_NAME=b30 docker-compose build
COMPOSE_PROJECT_NAME=b30 docker-compose up -d
```

再验:
- `COMPOSE_PROJECT_NAME=b30 docker-compose ps`
- `docker exec as180brd-ExaBGP_Control_Plane_Tool-10.100.0.180 sh -lc 'ps aux | grep -E "exabgp|python|dashboard" | grep -v grep'`
- `docker exec as180brd-ExaBGP_Control_Plane_Tool-10.100.0.180 sh -lc 'sed -n "1,220p" /etc/exabgp/exabgp.conf'`
- `docker exec as180brd-ExaBGP_Control_Plane_Tool-10.100.0.180 sh -lc 'tail -n 40 /var/log/exabgp/events.jsonl; tail -n 40 /var/log/exabgp/exabgp.log'`
- `docker exec as2brd-r100-10.100.0.2 birdc show protocols`
- `docker exec as3brd-r100-10.100.0.3 birdc show protocols`
- `docker exec as2brd-r100-10.100.0.2 birdc show route 203.0.113.0/24 all`
- `docker exec as3brd-r100-10.100.0.3 birdc show route 203.0.113.0/24 all`
- `curl http://localhost:8080/pro/home`
- `curl http://localhost:5106/`

在线改:
- `docker exec as180brd-ExaBGP_Control_Plane_Tool-10.100.0.180 sh -lc "printf '%s\n' 'announce route 203.2.3.0/24 next-hop self' > /run/exabgp/live.in"`
- `docker exec as2brd-r100-10.100.0.2 birdc show route for 203.2.3.1 all`
- `docker exec as3brd-r100-10.100.0.3 birdc show route for 203.2.3.1 all`
- `docker exec as180brd-ExaBGP_Control_Plane_Tool-10.100.0.180 tail -n 20 /var/log/exabgp/live-control.log`
- `docker exec as180brd-ExaBGP_Control_Plane_Tool-10.100.0.180 sh -lc "printf '%s\n' 'withdraw route 203.2.3.0/24 next-hop self' > /run/exabgp/live.in"`
- `docker exec as2brd-r100-10.100.0.2 birdc show route for 203.2.3.1 all`

讲法:
- AS180 不是普通 host demo
- 它是 IX 直连 BGP speaker
- `ExaBgpService` 把 speaker 接入 SEED 的 routing metadata
- `/run/exabgp/live.in` 是 SEED 生成的 ExaBGP process API 入口，现场可以实时发 `announce` / `withdraw`

通过点:
- AS180 ExaBGP 节点安装完成
- `/etc/exabgp/exabgp.conf` 正确
- AS2 / AS3 学到 `203.0.113.0/24`
- 在线 announce 后 AS2 / AS3 学到 `203.2.3.0/24`
- 在线 withdraw 后 AS2 / AS3 查不到 `203.2.3.0/24`
- event sink / dashboard 可达
- dashboard 和 route-state 不混淆
- 不改配置文件也能在线改 BGP announcement

失败点:
- event log 空
- peer router 没学到 prefix
- dashboard 200 但没有事件
- `/run/exabgp/live.in` 不存在或 `live_control.py` 进程不在

### A14: Classic Looking Glass + event dashboard

实现位置:
- `seedemu/services/BgpLookingGlassService.py`
- `seedemu/services/ExaBgpService.py`
- `examples/basic/A14_bgp_event_looking_glass`

拓扑:
- AS2: Classic Looking Glass 所在 AS
- AS151: Event Viewer + ExaBGP event source
- IX100: 单交换点

看谁:
- `as2h-looking-glass`: 这是 Classic LG 的 frontend/proxy
- `as151h-event-viewer`: 这是 ExaBGP event dashboard
- `as2brd-router0` / `as151brd-router0`: 这是 LG 读取的真实 BIRD router

测什么:
- `5002` 是 route-state 页面
- `5003` 是 event-stream 页面
- `proxy` / `frontend` / `exabgp` 进程是否都在
- LG 页面是不是直接读 BIRD route-state
- event dashboard 是不是只展示 ExaBGP JSON 事件

先跑:
```bash
seedcore
. .venv/bin/activate
PYTHONPATH=. python examples/basic/A14_bgp_event_looking_glass/bgp_event_looking_glass.py
cd examples/basic/A14_bgp_event_looking_glass/output
DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 COMPOSE_PROJECT_NAME=a14 docker-compose build
COMPOSE_PROJECT_NAME=a14 docker-compose up -d
```

再验:
- `COMPOSE_PROJECT_NAME=a14 docker-compose ps`
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
- AS2 的 `looking-glass` 是浏览器入口，不是 BIRD router
- AS151 的 `event-viewer` 是 ExaBGP event sink + dashboard

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
scripts/seed-codex status
scripts/seed-codex inspect
scripts/seed-codex ui -m gpt-5.4 -c 'model_reasoning_effort="low"'
```

讲法:
- 高层判断走 SeedAgent
- 底层证据走 SeedOps
- shell 只补充证据

如果是 B30 场景，第一句直接换成:
```text
接管当前 B30。不要修改配置，先找到 AS180 ExaBGP IX 工具 router，
说明它和 AS2/r100、AS3/r100 的 BGP 对等关系，并给出 route、
event、dashboard、process、config 和日志证据。
```

## 4. 切换和清场

每次换例子只做这几步:
```bash
cd <example>/output
COMPOSE_PROJECT_NAME=<name> docker-compose down --remove-orphans
DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 COMPOSE_PROJECT_NAME=<name> docker-compose build
COMPOSE_PROJECT_NAME=<name> docker-compose up -d
```

如果要换到下一个展示任务:
```bash
COMPOSE_PROJECT_NAME=<name> docker-compose down --remove-orphans
```

## 5. 端口速记
- A12: `8080`
- A13: `8080` + tool dashboard `5001`，若冲突可临时改到 `5101`
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

## 7. 你现场最顺手的讲法
- 先打开 `http://localhost:8080/pro/home`
- 再点到目标例子的 map 节点，看拓扑和端口
- 再进容器看 `ps`、`birdc`、`vtysh`、`cat /etc/...`
- 最后回源码看 service/layer 怎么把能力挂进来的
- A12 用 `FRR vs BIRD`
- A13 用 `tool node + event sink + peer route`
- B30 用 `IX 直连 speaker + 大规模传播`
- A14 用 `route-state` 和 `event-stream` 分开讲
