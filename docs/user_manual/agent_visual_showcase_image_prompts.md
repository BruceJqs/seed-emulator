# SEED 智能体实验可视化图片生成提示词

用途：这份文档是给 RightCodes `gpt-image-2` 的高质量生图 brief。每个“完整提示词”都必须可以单独复制使用，不能假设模型读过本文前文。

原则：

- 只使用 RightCodes `gpt-image-2` 生图。
- 不用 HTML、SVG、Mermaid、Graphviz、Markdown 图、前端页面、PPT 形状或脚本绘图替代。
- 图要服务展示：让老师和合作方快速看懂我们围绕智能体做了什么、实验规模有多大、关键节点在哪里、如何运行、如何验证。
- 每张图都要有足够信息量，但不要把 README 压成小字海报。图上放短标签、关键数字、核心节点和证据面；详细命令放正文。
- 生图模型没有上下文，所以每个完整提示词都重新说明项目、系列统一性、本图目标、事实约束和禁区。
- 允许 image-2 自由选择构图、配色、箭头、图形语言和视觉隐喻。我们约束事实和重点，不把它限制成死板模板。
- 严禁编造未给出的 ASN、IP、端口、前缀、节点名、任务结果或测试结论。

推荐生成尺寸：16:9。若接口支持尺寸参数，优先 `1536x864` 或同等 16:9 高清尺寸。

## 系列统一性要求

每张图都属于同一个系列：`SEED Emulator + SeedAgent 智能体网络实验平台`。

系列视觉目标：

- 专业科研汇报插图，不是产品 UI、聊天 UI、网页 dashboard 或命令行截图。
- 有真实网络系统感：AS、IX、router、service、BGP speaker、runtime evidence、policy gate、artifact。
- 有智能体工程感：`seed-codex`、`SeedAgent`、`SeedOps MCP`、skills、task loop、policy/HITL、evidence archive。
- 图中文字中文为主，保留必要英文术语：SeedAgent、SeedOps、MCP、Codex skills、BIRD、FRR、ExaBGP、Looking Glass。
- 同系列图可共享视觉语言，但不要每张图长得完全一样。总览图偏架构，例子图偏网络拓扑，审计图偏闭环，控制面图偏协议与证据。

生图时有效突出重点的方法：

- 明确主角：每张图只设一个主叙事，例如“运行时接管”“Z30 ExaBGP IX 工具”“B29 邮件/DNS 运维”。
- 用视觉分区承载复杂性：左侧实验网络，中间运行时/控制面，右侧证据或 dashboard。
- 把规模数字做成显眼 badge：例如 `38 services`、`35 nodes`、`24 ASNs`。
- 把关键节点做成重点标注：例如 `AS180 exabgp 10.100.0.180`。
- 把证据面单独成组：routes、logs、pages、artifacts、job steps。
- 不要画过细线缆拓扑。复杂拓扑用聚类/层级表达，精确事实用短标签。

## 图片清单

| 序号 | 图 | 文件 |
|---|---|---|
| 01 | 总体成果三条线 | `overview_three_workstreams.png` |
| 02 | seed-codex 激活链与 harness | `agent_harness_activation_stack.png` |
| 03 | Agent / MCP / runtime 分层架构 | `agent_mcp_runtime_layers.png` |
| 04 | Codex skills 与行为约束 | `agent_skills_behavior_contract.png` |
| 05 | Mission task 状态机 | `agent_mission_state_machine.png` |
| 06 | 审计报告与证据 anatomy | `agent_audit_report_anatomy.png` |
| 07 | BGP 控制面 core 能力 | `bgp_control_plane_core.png` |
| 08 | 控制面验证矩阵 | `bgp_validation_matrix.png` |
| 09 | Z00 / B00 mini Internet | `z00_b00_mini_internet.png` |
| 10 | Z01 / Y01 prefix hijack | `z01_y01_prefix_hijack.png` |
| 11 | Z02 / A02 MPLS | `z02_a02_mpls.png` |
| 12 | Z12 / A12 BIRD-FRR mixed backend | `z12_a12_mixed_frr_bird.png` |
| 13 | Z13 / A13 ExaBGP control-plane tool | `z13_a13_exabgp.png` |
| 14 | Z30 / B30 ExaBGP IX tool | `z30_b30_exabgp_ix.png` |
| 15 | Z14 / A14 BGP Looking Glass | `z14_a14_bgp_lg.png` |
| 16 | Z28 / B28 traffic generator | `z28_b28_traffic.png` |
| 17 | Z29 / B29 mail DNS ops | `z29_b29_mail_dns.png` |
| 18 | Kubernetes scale-out 方向 | `k8s_direction.png` |

## 01 总体成果三条线

目标文件：`docs/user_manual/images/agent_visual_showcase/overview_three_workstreams.png`

这张图要说明：

- 我们围绕智能体做了三条主线。
- 第一条是运行时底座：智能体接管已经启动的 SEED 实验。
- 第二条是可审计闭环：观察、判断、动作、验证、总结、证据归档。
- 第三条是控制面扩展：BGP、FRR、ExaBGP、Looking Glass。
- 图要让人明白这些不是孤立功能，而是共同组成“智能体网络实验平台”。

完整提示词：

```text
请生成一张 16:9 专业科研汇报插图。项目背景：SEED Emulator 原本用于构建可运行的网络仿真实验；我们把它扩展为可被智能体接管、观测、受控操作、验证和复盘的网络实验平台。图属于一组“SEED Emulator + SeedAgent 智能体网络实验平台”系列图，风格应专业、现代、可信，有网络系统论文/科研项目汇报的质感，不要画成网页、聊天界面、命令行截图、代码截图或玩具流程图。

本图目标：总览我们围绕智能体完成的三条主线。请让画面有三个清晰主区，每个主区有短标签和典型元素。

主线 1：运行时底座。短标签包括：Running SEED Runtime、seed-codex ui、SeedAgent、SeedOps MCP、nodes / services / routes / logs / pages、one active baseline、read-only first。表达智能体接入已经启动的实验网络，从运行态事实工作，而不是读取构建期拓扑答案。

主线 2：可审计闭环。短标签包括：Observe、Judge、Act、Verify、Summarize、Policy Gate、HITL、Rollback、Evidence Artifacts。表达智能体行为有任务流程、范围控制、风险确认、复验和证据归档。

主线 3：控制面扩展。短标签包括：BIRD、FRR、ExaBGP、Classic Looking Glass、Event Dashboard、BGP observability、route injection / withdraw。表达我们扩展了 BGP 控制面基础设施，使仿真器能承载更真实的网络运维和研究场景。

必须体现最终可见成果：interactive operation、mission task packs、agent-specific bundles、runtime evidence、BGP control-plane showcases。不要编造具体性能指标。
```

## 02 seed-codex 激活链与 harness

目标文件：`docs/user_manual/images/agent_visual_showcase/agent_harness_activation_stack.png`

这张图要说明：

- `seed-codex` 为什么不是普通 Codex。
- harness 的真实激活链：repo launcher -> subrepo launcher -> render config -> sync skills -> CODEX_HOME -> Codex profile。
- 图里要画出最终用户能看到和能用的东西。

关键事实：

- repo-root launcher: `scripts/seed-codex`
- subrepo launcher: `subrepos/seed-agent/scripts/seed-codex`
- config source: `subrepos/seed-agent/scripts/render_codex_seed_config.py`
- assets sync: `subrepos/seed-agent/scripts/seed_codex_assets.py sync`
- CODEX_HOME: `subrepos/seed-agent/.codex-seed-agent`
- active profile: `seed_codex_ops`
- config: `.codex-seed-agent/config.toml`
- project Codex skills: `.codex-seed-agent/skills/*`
- enabled MCP: SeedAgent MCP + SeedOps MCP
- current project plugin: none / empty slot，不要画成核心能力

完整提示词：

```text
请生成一张 16:9 专业科研汇报插图。项目背景：我们为 SEED Emulator 做了一个 agent harness，使普通 Codex 通过项目专用 CODEX_HOME、系统提示词、Codex skills 和 MCP 工具白名单，变成面向 SEED runtime 的智能体操作入口。图属于“SEED Emulator + SeedAgent 智能体网络实验平台”系列图，风格要专业、清晰、现代，不要画成网页 UI、聊天窗口、命令行截图或代码截图。

本图目标：解释 seed-codex harness 的真实激活链，让观众明白它不是普通 Codex 加几句 prompt。

必须画出从左到右或从上到下的激活链：
1. 用户运行 repo-root launcher：scripts/seed-codex ui
2. 转到 subrepo launcher：subrepos/seed-agent/scripts/seed-codex
3. render_codex_seed_config.py 生成项目 config
4. seed_codex_assets.py sync 同步项目 Codex skills
5. 专用 CODEX_HOME：subrepos/seed-agent/.codex-seed-agent
6. active profile：seed_codex_ops
7. config.toml 中包含 developer instructions、SeedAgent MCP 白名单、SeedOps MCP 白名单
8. CODEX_HOME/skills 中包含项目 Codex skills
9. 最终进入 Codex UI，用户通过自然语言操作当前 SEED runtime

必须单独标注：project-local plugin 当前为空位，不是核心能力；marketplace cache plugins 不等于 SEED 项目逻辑。不要把 plugin 画成已经实现的主路径。

画面中应显示最终用户可见入口：scripts/seed-codex inspect、scripts/seed-codex ui、scripts/seed-codex status。也要显示最终连接目标：SeedAgent MCP、SeedOps MCP、running SEED runtime。
```

## 03 Agent / MCP / Runtime 分层架构

目标文件：`docs/user_manual/images/agent_visual_showcase/agent_mcp_runtime_layers.png`

这张图要说明：

- 从用户交互到真实网络的分层链路。
- 高层 SeedAgent 负责任务、规划、策略、报告；SeedOps 负责运行时观测与动作；底层是 Docker/Compose 中的 SEED 网络。
- 智能体不是直接乱用 shell，而是通过工具面和策略面操作。

关键事实：

- User / Teacher / Operator
- `seed-codex ui`
- SeedAgent MCP: `seed_agent_run`, `seed_agent_plan`, `seed_agent_policy_check`, `seed_agent_task_*`
- Task Engine: catalog, begin, reply, execute, status
- Policy / HITL / reporter
- SeedOps MCP: `workspace_*`, `inventory_list_nodes`, `routing_*`, `ops_logs`, `ops_exec`, `job_*`, `artifact_*`
- Running SEED runtime: Docker containers, AS/IX/routers/services/pages/logs/routes
- Evidence: job steps, artifacts, logs, route snapshots, page probes

完整提示词：

```text
请生成一张 16:9 专业科研汇报插图。项目背景：SEED Emulator 现在不仅能构建网络实验，还能让 SeedAgent 通过 MCP 分层接管已经运行的实验网络。图属于“SEED Emulator + SeedAgent 智能体网络实验平台”系列图，要求像系统架构图但不要像代码框图或网页 UI。

本图目标：展示从用户交互到真实运行网络的分层架构。

必须画出这些层次：
顶部：User / Teacher / Operator 通过 scripts/seed-codex ui 进入交互。
智能体层：SeedAgent MCP，包含 seed_agent_run、seed_agent_plan、seed_agent_policy_check、seed_agent_task_*。
任务层：Task Engine，包含 catalog、begin、reply、execute、status。
约束层：Policy Gate、HITL Confirmation、Reporter、Fallback。
运行时工具层：SeedOps MCP，包含 workspace_*、inventory_list_nodes、routing_*、ops_logs、ops_exec、job_*、artifact_*。
底层：running SEED runtime，包含 Docker containers、AS/IX、routers、services、pages、logs、routes。
输出层：job steps、artifacts、route snapshots、logs、page probes、summary report。

视觉重点：高层工具优先，低层 shell 只作为 bounded evidence collection。默认 read-only first，高风险动作必须经过 policy/HITL。不要画成智能体直接跳进所有容器随便执行命令。
```

## 04 Codex Skills 与行为约束

目标文件：`docs/user_manual/images/agent_visual_showcase/agent_skills_behavior_contract.png`

这张图要说明：

- 项目自带 Codex skills 是 harness 的关键部分。
- 每个 skill 不是“一个名字”，而是约束智能体行为和工具选择。
- 当前主路径的 project Codex skills 与旧 BUILD-path YAML skills 要区分。

关键事实：

- Project Codex skills:
- `seed-runtime-operator`: 当前运行时接管、匿名 runtime operator、不要索要 workspace、先做运行态证据
- `seed-task-runtime-loop`: task begin/reply/execute/status、missing inputs、approval、rollback、report
- `seed-behavior-verification`: inspect、probe-context、verify、fallback/evidence quality
- `seed-bgp-control-plane`: BIRD/FRR/ExaBGP、routing evidence、backend-aware diagnosis
- `seed-exabgp-tool`: ExaBGP tool node、peer/config/event/dashboard
- `seed-bgp-looking-glass`: route-state vs event-stream、continuous checks
- Legacy YAML skills: build-oriented, not attached-runtime main path

完整提示词：

```text
请生成一张 16:9 专业科研汇报插图。项目背景：SEED 的 seed-codex harness 不只是工具白名单，还把项目自带 Codex skills 同步到专用 CODEX_HOME，用来约束智能体身份、任务闭环、验证方式和 BGP 专项行为。图属于同一套 SEED Agent 展示图，风格专业，不要画成插件市场或聊天机器人界面。

本图目标：解释 Codex skills 如何把智能体行为从“泛用助手”收紧成“SEED runtime operator”。

必须画出 Project Codex skills 这一组：
1. seed-runtime-operator：当前运行时接管、anonymous runtime operator、runtime facts first、不要无意义索要 workspace。
2. seed-task-runtime-loop：task begin / reply / execute / status、missing inputs、approval、rollback、report。
3. seed-behavior-verification：inspect、probe-context、verify、fallback detection、evidence quality。
4. seed-bgp-control-plane：BIRD / FRR / ExaBGP、routing summary、looking glass、backend-aware diagnosis。
5. seed-exabgp-tool：ExaBGP tool node、peer、config、event log、dashboard。
6. seed-bgp-looking-glass：route-state view vs event-stream view、continuous checks。

必须单独画出 Legacy internal YAML skills：BUILD-path / topology construction / not attached-runtime main path。表达它仍存在但不是 seed-codex ui 主证明。

视觉重点：skills 影响身份、工具顺序、风险边界、报告质量。不要把 skill 画成简单文件列表；要画成行为 contract。
```

## 05 Mission Task 状态机

目标文件：`docs/user_manual/images/agent_visual_showcase/agent_mission_state_machine.png`

这张图要说明：

- mission 是结构化任务路径，不是主交互入口，但它证明任务化、回放、审计和演示稳定性。
- 状态机：catalog -> begin -> needs_input / awaiting_confirmation -> execute -> status/report。

关键事实：

- APIs: `seed_agent_task_catalog`, `seed_agent_task_begin`, `seed_agent_task_reply`, `seed_agent_task_execute`, `seed_agent_task_status`
- Session lifecycle: begin, ready, needs_input, awaiting_confirmation, executing, done/error
- Policy by stage: observe/analyze/verify default read_only; net_ops/danger need confirmation
- rollback_required
- evidence_requirements
- report_summary
- fallback playbooks

完整提示词：

```text
请生成一张 16:9 专业科研汇报插图。项目背景：SEED Agent 支持结构化 mission task，用来把运行时操作变成可复用、可审计、可回放的任务流程。图属于 SEED Agent 系列图，要求专业清晰，不要画成普通项目管理看板或聊天界面。

本图目标：展示 mission task 状态机和它解决的问题：输入收集、风险确认、执行、回滚、证据和报告。

必须画出 API 流程：seed_agent_task_catalog -> seed_agent_task_begin -> seed_agent_task_reply -> seed_agent_task_execute -> seed_agent_task_status。

必须画出 session 状态：begin / ready / needs_input / awaiting_confirmation / executing / done / error。

必须画出任务文件中的关键 contract：objective、required_inputs、policy_by_stage、rollback_required、evidence_requirements、fallback_playbooks、acceptance_checks、report_summary。

必须表达：普通演示主入口是 seed-codex ui；mission 是结构化验证和回归路径。高风险 task 需要 HITL confirmation，rollback-required task 必须有 rollback evidence。
```

## 06 审计报告与证据 Anatomy

目标文件：`docs/user_manual/images/agent_visual_showcase/agent_audit_report_anatomy.png`

这张图要说明：

- 我们关心的不只是最终回答，而是 agent 做了什么、用了什么工具、是否越界、证据在哪里。
- 报告字段是可审计闭环的一部分。

关键事实：

- visibility_mode
- attach_type
- allowed_selector
- redacted_fields
- planner_mode / fallback_used
- tool_usage_summary
- ops_exec_count
- high_level_action_count
- routing_action_count
- risky_action_count
- mutating_action_count
- changed_state.mutated_runtime
- dashboard_reachability
- artifact_count
- rollback_status
- action_timeline
- unresolved_issues

完整提示词：

```text
请生成一张 16:9 专业科研汇报插图。项目背景：SEED Agent 的结果不是只看最后一句话，而是要审计它从运行态接管、工具选择、策略边界、动作执行到证据归档的全过程。图属于 SEED Agent 系列图，风格应像科研系统的 evidence report anatomy，不要画成 JSON 截图或命令行输出。

本图目标：解释一次 agent 任务报告中哪些内容证明它做得可信。

必须画出 report anatomy 的模块：
Runtime context：visibility_mode、attach_type、allowed_selector、redacted_fields。
Planning：planner_mode、fallback_used。
Tool use：tool_usage_summary、high_level_action_count、routing_action_count、ops_exec_count。
Risk and mutation：risky_action_count、mutating_action_count、changed_state.mutated_runtime。
Verification：dashboard_reachability、rollback_status、verification_status。
Evidence：artifact_count、artifact names、job steps、logs、routes、pages。
Review：action_timeline、unresolved_issues。

必须突出一个细节：read-only ops_exec can be risky surface but not runtime mutation。也就是说只读 shell 探测会被记录，但不会自动等同于改变网络。

不要画成密密麻麻字段表；用报告剖面图或证据盒子表达。
```

## 07 BGP 控制面 Core 能力

目标文件：`docs/user_manual/images/agent_visual_showcase/bgp_control_plane_core.png`

这张图要说明：

- FRR、ExaBGP、Classic LG 是 core/control-plane 能力，不只是例子 patch。
- BIRD 与 FRR 是 backend；ExaBGP 是工具 speaker；LG 是观测面。

关键事实：

- BIRD remains reference backend
- FRR as first-class backend target
- backend-neutral routing intent
- eBGP / iBGP / route-server peering
- import/export policy
- connected/direct export
- next-hop-self
- OSPF / router-id / loopback
- ExaBGP service declares tool speaker + peers + announcements
- Classic LG is Bird-only in this round

完整提示词：

```text
请生成一张 16:9 专业科研汇报插图。项目背景：我们为 SEED 扩展 BGP 控制面 core 能力，使仿真器不只生成 BIRD 网络，也能向 FRR、一等 ExaBGP 工具节点和 Looking Glass 观测体系演进。图属于 SEED Agent / BGP control-plane 系列图，风格专业，像网络系统架构图，不要画成代码模块 UML。

本图目标：解释 BGP 控制面增强的核心设计，而不是某个单一 demo。

必须画出 shared routing intent 位于中心，向不同 renderer/service 输出：
1. BIRD backend：reference semantics。
2. FRR backend：first-class backend target。
3. ExaBGP service：tool speaker、peers、announcements、event sink、dashboard。
4. Classic Looking Glass：Bird-only route-state view in this round。

必须标出 intent 内容：eBGP, iBGP, route-server peering, import/export policy, connected/direct export, next-hop-self, OSPF, router-id, loopback。

必须表达：FRR 目标是从源码构建后真实收敛和转发，不是运行时补丁；ExaBGP 不应偷偷绑定 BIRD，而应由 backend-neutral intent 接入；Classic LG 当前先稳 Bird-only。
```

## 08 BGP 控制面验证矩阵

目标文件：`docs/user_manual/images/agent_visual_showcase/bgp_validation_matrix.png`

这张图要说明：

- 控制面验收不是“容器起来了”。
- 验收维度包括构建、协议、连通、策略、页面、日志、agent 证据。

关键事实：

- Fresh build from source
- Docker runtime up
- OSPF Full
- iBGP Established
- eBGP Established
- route entries
- next-hop resolved
- host-to-host
- router-to-router
- AS path / community / local-pref
- ExaBGP process/config/event/dashboard
- Classic LG page 200
- artifacts and report summary

完整提示词：

```text
请生成一张 16:9 专业科研汇报插图。项目背景：SEED 的 BGP/FRR/ExaBGP/Looking Glass 能力必须通过核心矩阵验证，不能只看容器是否启动或命令是否存在。图属于 SEED control-plane 验证系列，风格应像科研验收矩阵或工程质量雷达图，但不要画成普通 Excel 表。

本图目标：展示控制面实验怎样从源码构建到运行证据闭环。

必须包含验证阶段：
1. Fresh build from source。
2. Docker runtime up。
3. Protocol convergence：OSPF Full、iBGP Established、eBGP Established。
4. Routing correctness：route entries、next-hop resolved、AS path、community、local-pref。
5. Data-plane checks：host-to-host、router-to-router。
6. Tool observability：ExaBGP process/config/event/dashboard、Classic LG page 200。
7. Agent audit：artifacts、job steps、report summary、rollback_status。

必须表达：A12/A13/A14/B30 是验证样例；真正目标是 reusable control-plane capability。
```

## 09 Z00 / B00 Mini Internet

目标文件：`docs/user_manual/images/agent_visual_showcase/z00_b00_mini_internet.png`

关键拓扑事实：

- 来源：`examples/internet/B00_mini_internet/output`
- 6 Internet Exchanges
- 5 transit AS
- 12 stub AS
- 约 61 compose services
- Internet Map 一般使用 `18080`
- Agent 包：`Z00_b00_attached_runtime`
- 任务：BGP flap root cause、convergence comparison、prefix hijack live drill

完整提示词：

```text
请生成一张 16:9 专业科研汇报插图。项目背景：SEED Emulator 可以构建 mini Internet，SeedAgent 可以通过 seed-codex ui 接管已运行网络并从运行态证据理解路径、BGP 状态和服务状态。图属于 SEED Agent 实验展示系列，专业、清晰、信息量高，不要画成网页 UI、命令行截图或简单玩具拓扑。

本图目标：展示 Z00 / B00 mini Internet 作为智能体 attached-runtime 基础场景。

必须准确呈现这些事实：来源实验 B00_mini_internet；Agent 包 Z00_b00_attached_runtime；6 个 Internet Exchanges；5 个 transit AS；12 个 stub AS；约 61 compose services；Internet Map 通常为 host port 18080。

拓扑表达要求：画出 6 个 IX 作为互联网骨架，5 个 transit AS 连接多个 IX，12 个 stub AS 挂在边缘。不要画成只有三四个节点的小玩具。可以聚类表达，不必画满所有 61 个 service，但规模 badge 必须醒目。

Agent 运行逻辑：从 current runtime 接管，不偷看拓扑源码；先 workspace_refresh / inventory_list_nodes，再 routing_protocol_summary / routing_looking_glass / traceroute / logs；最后给出 path reasoning、BGP health、evidence artifacts。

必须突出用途：BGP flap root cause、convergence comparison、prefix hijack drill with rollback。不要暗示默认可以无确认执行高风险劫持；高风险演练需要 policy/HITL/rollback。
```

## 10 Z01 / Y01 Prefix Hijack Drill

目标文件：`docs/user_manual/images/agent_visual_showcase/z01_y01_prefix_hijack.png`

关键拓扑事实：

- 来源：`examples/yesterday_once_more/Y01_bgp_prefix_hijacking/demo/output`
- 约 125 compose services
- 类型：BGP prefix hijacking security drill candidate
- 状态：Conditional Go
- 关键概念：victim prefix、attacker AS、observation routers、normal route、hijacked route、rollback verification

完整提示词：

```text
请生成一张 16:9 专业科研汇报插图。项目背景：SEED Agent 可以在运行态网络中分析 BGP 安全演练，重点不是提前知道拓扑，而是从路由表、AS path、next-hop 和事件前后对比中理解 prefix hijack。图属于 SEED Agent 实验展示系列，风格专业、可信，不能像网络攻击漫画或玩具图。

本图目标：展示 Z01 / Y01 prefix hijack drill 作为 routing security 候选场景。

必须准确呈现这些事实：来源实验 Y01_bgp_prefix_hijacking demo；Agent 包 Z01_y01_prefix_hijack_drill；约 125 compose services；状态 Conditional Go；用于 BGP prefix hijacking 演练候选。

拓扑表达要求：画出 victim AS / victim prefix、attacker AS、多个 observation routers、normal route 与 hijacked route 两条路径。用 before / during / after 时间线表达路由变化和 rollback verification。不要编造具体受害前缀数值，因为没有提供。

Agent 运行逻辑：先只读预分析，识别受害前缀候选、攻击侧 AS、关键观察点；如果进入 live drill，必须展示 policy gate、HITL confirmation、route injection、withdraw rollback、post-rollback route evidence。

必须突出证据：AS path evidence、next-hop evidence、route-table before/during/after、job artifacts。不要把它画成默认稳定主秀；它是 Conditional Go。
```

## 11 Z02 / A02 MPLS Control Plane

目标文件：`docs/user_manual/images/agent_visual_showcase/z02_a02_mpls.png`

关键拓扑事实：

- 来源：`examples/basic/A02_transit_as_mpls/output`
- 约 13 compose services
- `AS150` MPLS backbone
- edge routers: `r1`, `r4`
- core routers: `r2`, `r3`
- customer sides: `AS151`, `AS152`
- 需要 Linux MPLS kernel support

完整提示词：

```text
请生成一张 16:9 专业科研汇报插图。项目背景：SEED Agent 不只做服务排障，也要能理解控制面和转发面的运行态证据。A02 是 MPLS 控制面场景，用于检查 edge/core router 角色、label switched path 和 FRR/MPLS 证据。图属于 SEED Agent 实验展示系列，专业、清晰，不要画成普通 IP ping 拓扑。

本图目标：展示 Z02 / A02 MPLS control plane。

必须准确呈现这些事实：来源实验 A02_transit_as_mpls；Agent 包 Z02_a02_mpls_control_plane；约 13 compose services；AS150 是 MPLS backbone；edge routers 是 r1 和 r4；core routers 是 r2 和 r3；两端连接 AS151 与 AS152；运行依赖 Linux MPLS kernel support。

拓扑表达要求：画 AS151 -- AS150/r1 -- AS150/r2 -- AS150/r3 -- AS150/r4 -- AS152 的 backbone 结构。r1/r4 标成 edge routers，r2/r3 标成 core routers。用 label-switched path 表达 MPLS，不要画成所有 router 都承载完整 BGP 表。

Agent 运行逻辑：接管 runtime 后，用 inventory、routing summary、traceroute、targeted FRR/MPLS evidence 和 tcpdump MPLS evidence 判断。突出 traceroute 中间跳可能不可见，这是 MPLS 行为证据之一。

必须突出验证：MPLS label evidence、edge/core role evidence、FRR/MPLS inspection、kernel support precheck。
```

## 12 Z12 / A12 BIRD-FRR Mixed Backend

目标文件：`docs/user_manual/images/agent_visual_showcase/z12_a12_mixed_frr_bird.png`

关键拓扑事实：

- 来源：`examples/basic/A12_bgp_mixed_backend/output`
- 约 11 compose services
- IX: `ix100`, `ix101`
- `AS2` transit，routers: `r1`, `r2`
- `AS151/router0` + host `web`
- `AS152/router0` + host `web`
- private peering: IX100 between AS2 and AS151; IX101 between AS2 and AS152
- FRR enabled on `AS2/r2` and `AS151/router0`
- `AS2/r1` and `AS152/router0` stay BIRD

完整提示词：

```text
请生成一张 16:9 专业科研汇报插图。项目背景：SEED 的 BGP 控制面正在从单一 BIRD backend 扩展到 BIRD/FRR mixed backend。A12 是验证 FRR 一等 backend 和 BIRD-FRR 互操作的关键样例。图属于 SEED Agent / BGP control-plane 展示系列，专业、信息密度高，不要画成只有“FRR logo + BIRD logo”的空泛图。

本图目标：展示 Z12 / A12 mixed BIRD-FRR backend 的真实拓扑和验证重点。

必须准确呈现这些事实：来源实验 A12_bgp_mixed_backend；Agent 包 Z12_a12_bgp_mixed_backend；约 11 compose services；有 ix100 和 ix101；AS2 是 transit，包含 r1 和 r2；AS151 有 router0 和 web host；AS152 有 router0 和 web host；AS2 与 AS151 在 ix100 peering；AS2 与 AS152 在 ix101 peering；FRR enabled on AS2/r2 and AS151/router0；AS2/r1 and AS152/router0 stay on BIRD。

拓扑表达要求：画出 AS2/r1 连接 ix100 与 AS151/router0，AS2/r2 连接 ix101 与 AS152/router0，同时 AS2 内部 r1-r2 互联。明确用标签区分 BIRD nodes 与 FRR nodes。AS151 web 和 AS152 web 要作为 host-to-host 验证端点出现。

Agent 运行逻辑：先 routing_protocol_summary 区分 backend，再用 birdc/vtysh 作为 targeted evidence；如果做 route injection live drill，必须有 announce、withdraw、post-withdraw verification。

必须突出验证标准：OSPF/iBGP/eBGP 状态、route propagation、next-hop resolved、host-to-host、router-to-router、BIRD/FRR interoperability、rollback verified。不要把“vtysh 存在”画成成功标准。
```

## 13 Z13 / A13 ExaBGP Control-Plane Tool

目标文件：`docs/user_manual/images/agent_visual_showcase/z13_a13_exabgp.png`

关键拓扑事实：

- 来源：`examples/basic/A13_exabgp_control_plane/output`
- 约 7 compose services
- IX: `ix100`
- `AS2/router0` connects `net0` and `ix100`
- `AS151/router0` connects `net0` and `ix100`
- `AS151/control-plane-tool` joins `net0`
- ExaBGP is installed on `control-plane-tool`
- ExaBGP `attachToRouter("router0")`
- local ASN `65010`
- announcement `198.51.100.0/24`
- dashboard host `5001` -> container `5000`
- map host `8080`

完整提示词：

```text
请生成一张 16:9 专业科研汇报插图。项目背景：ExaBGP 被称为 BGP Swiss Army Knife，我们把它作为 SEED 内部可复用控制面工具节点，用来产生、观察和记录 BGP 事件。A13 是单 peer ExaBGP 工具节点样例。图属于 SEED Agent / BGP control-plane 展示系列，专业清晰，不要把 ExaBGP 画成普通 Web 服务。

本图目标：展示 Z13 / A13 ExaBGP control-plane tooling 的真实结构和证据面。

必须准确呈现这些事实：来源实验 A13_exabgp_control_plane；Agent 包 Z13_a13_exabgp_control_plane；约 7 compose services；有 ix100；AS2/router0 连接 net0 和 ix100；AS151/router0 连接 net0 和 ix100；AS151/control-plane-tool 连接 net0 并运行 ExaBGP；ExaBGP attachToRouter router0；local ASN 65010；announcement 198.51.100.0/24；dashboard host 5001 -> container 5000；map host 8080。

拓扑表达要求：画 AS2/router0 与 AS151/router0 通过 ix100 peering；AS151/control-plane-tool 在 AS151 内网侧，作为 ExaBGP tool node 与 AS151/router0 建立控制面关系。突出它是工具节点，不是生产 router。

Agent 运行逻辑：接管 runtime 后定位 ExaBGP node，确认 peer router、local ASN、announcement、config evidence、event log、dashboard reachability。工具顺序：inventory、routing summary、ops_logs、targeted read-only ops_exec。

必须突出证据面：/etc/exabgp config、/var/log/exabgp/events.jsonl、process state、dashboard 5001、peer route evidence。
```

## 14 Z30 / B30 Mini Internet ExaBGP IX Tool

目标文件：`docs/user_manual/images/agent_visual_showcase/z30_b30_exabgp_ix.png`

关键拓扑事实：

- 来源：`examples/internet/B30_mini_internet_exabgp_ix/output`
- 基于 B00 mini Internet，但 `hosts_per_as=0`
- 新增 `AS180`
- router name: `exabgp`
- IX: `ix100`
- IX address: `10.100.0.180`
- local ASN: `180`
- announcement: `203.0.113.0/24`
- peers: `AS2/r100`, `AS3/r100`
- 38 compose services
- 35 parsed runtime nodes
- 24 ASNs
- dashboard host `5130` -> container `5000`
- map host `8080`
- 已验证 AS2/r100 与 AS3/r100 看到 `203.0.113.0/24`

完整提示词：

```text
请生成一张 16:9 专业科研汇报插图。项目背景：我们把 ExaBGP 从普通单 peer 工具扩展为 mini Internet 中 IX 直连的 BGP tool router。B30 是最新的控制面工具例子，用来验证 ExaBGP 作为 IX-facing BGP speaker 与多个 peer 交换路由，并让 SeedAgent 做只读发现和证据总结。图属于 SEED Agent / BGP control-plane 展示系列，必须专业、有规模感，不要画成一个小 host 接路由器的玩具图。

本图目标：展示 Z30 / B30 mini Internet ExaBGP IX tool 的真实结构、规模和运行证据。

必须准确呈现这些事实：来源实验 B30_mini_internet_exabgp_ix；Agent 包 Z30_b30_mini_internet_exabgp_ix；基于 B00 mini Internet，但 hosts_per_as=0；新增 AS180；router name 是 exabgp；它直接连接 ix100；IX address 是 10.100.0.180；local ASN 是 180；announcement 是 203.0.113.0/24；eBGP peers 是 AS2/r100 和 AS3/r100；规模是 38 compose services、35 parsed runtime nodes、24 ASNs；ExaBGP dashboard host 5130 -> container 5000；map host 8080；已验证 AS2/r100 与 AS3/r100 都能看到 203.0.113.0/24。

拓扑表达要求：画出 ix100 作为中心 IX，AS180/exabgp 作为 IX 直连 BGP tool router，AS2/r100 和 AS3/r100 也是 ix100 上的 peer。可以在背景中表现 mini Internet 的其他 AS/IX 聚类，但不要抢主线。AS180/exabgp 必须画成 router speaker，不是 host-side app。

Agent 运行逻辑：read-only discovery。SeedAgent 接管 runtime，定位 AS180 ExaBGP router，识别两个 peers，读取 ExaBGP config/log/process/dashboard，使用 routing evidence 验证 AS2/AS3 看到 203.0.113.0/24。报告必须显示 mutated_runtime=false。

严禁：不要暗示 203.0.113.0/24 做了 data-plane ping；首版验收目标是 control-plane route exchange。不要编造更多 peers 或端口。
```

## 15 Z14 / A14 BGP Event Looking Glass

目标文件：`docs/user_manual/images/agent_visual_showcase/z14_a14_bgp_lg.png`

关键拓扑事实：

- 来源：`examples/basic/A14_bgp_event_looking_glass/output`
- 约 8 compose services
- IX: `ix100`
- `AS2/router0`
- `AS2/looking-glass`
- `AS151/router0`
- `AS151/event-viewer`
- private peering on ix100 between AS2 and AS151
- Classic LG installed as `bgp_lg`, attached to `AS2/router0`
- ExaBGP event service installed as `bgp_events`, attached to `AS151/router0`
- ExaBGP local ASN `65020`
- route-state LG host `5002` -> container `5000`
- event dashboard host `5003` -> container `5000`
- map host `8080`
- Classic LG 当前按 Bird route-state view 稳定，不声称 FRR LG 完整支持

完整提示词：

```text
请生成一张 16:9 专业科研汇报插图。项目背景：BGP 可观测性需要区分“当前路由状态”和“事件流”。A14 把 Classic Looking Glass 的 route-state view 与 ExaBGP event dashboard 放在同一 BGP 场景中，供人和 SeedAgent 对照观察。图属于 SEED Agent / BGP observability 展示系列，专业清晰，不要画成普通网页 dashboard 截图。

本图目标：展示 Z14 / A14 BGP event looking glass 的两类观测面。

必须准确呈现这些事实：来源实验 A14_bgp_event_looking_glass；Agent 包 Z14_a14_bgp_event_looking_glass；约 8 compose services；有 ix100；AS2/router0 与 AS151/router0 在 ix100 private peering；AS2/looking-glass 运行 Classic LG bgp_lg 并 attach 到 AS2/router0；AS151/event-viewer 运行 ExaBGP event service bgp_events 并 attach 到 AS151/router0；ExaBGP local ASN 65020；route-state LG host 5002 -> container 5000；event dashboard host 5003 -> container 5000；map host 8080。

拓扑表达要求：画成左右两个观察面。左侧 Classic Looking Glass / route-state view，连接 AS2/router0，回答 current route table / protocol state。右侧 ExaBGP Event Dashboard / event-stream view，连接 AS151/router0，回答 BGP updates / withdrawals / event flow。中间是 ix100 和 AS2-AS151 peering。

必须明确：route-state view 与 event-stream view 不是同一种证据；Classic LG 当前作为 Bird route-state view 稳定能力呈现，不要画成已完整支持 FRR LG。
```

## 16 Z28 / B28 Traffic Generator

目标文件：`docs/user_manual/images/agent_visual_showcase/z28_b28_traffic.png`

关键拓扑事实：

- 来源：`examples/internet/B28_traffic_generator/3-multi-traffic-generator/output`
- 基于 mini Internet
- 约 63 compose services
- traffic generator / traffic receivers
- 证据面：process、socket、logs、node roles
- 价值：非 BGP attached-runtime 角色识别与实验设计

完整提示词：

```text
请生成一张 16:9 专业科研汇报插图。项目背景：SeedAgent 不只服务 BGP，也需要在已经运行的普通网络实验中识别应用角色和实验负载。B28 是 traffic generator/receiver 场景，用来验证 agent 能否从运行态证据识别流量发生器、接收器和实验边界。图属于 SEED Agent 实验展示系列，专业、清晰，不要画成普通网络监控 dashboard。

本图目标：展示 Z28 / B28 traffic generator lab。

必须准确呈现这些事实：来源实验 B28_traffic_generator/3-multi-traffic-generator；Agent 包 Z28_b28_traffic_lab；基于 mini Internet；约 63 compose services；包含 traffic generator 和多个 traffic receivers；证据来自 process、socket、logs、node roles。

拓扑表达要求：背景是 mini Internet 聚类，突出一个 traffic generator 向多个 receiver 发起流量。不要画成只有两个主机的 toy；要有运行态角色识别感。

Agent 运行逻辑：接管 current runtime 后，不看拓扑源码，通过 process list、listening sockets、traffic logs、inventory roles 识别 generator/receiver，再设计可验证流量实验。强调 shell 只是 read-only evidence collection。

必须突出输出：role classification、traffic evidence、experiment design、verification plan。
```

## 17 Z29 / B29 Mail DNS Runtime Ops

目标文件：`docs/user_manual/images/agent_visual_showcase/z29_b29_mail_dns.png`

关键拓扑事实：

- 来源：`examples/internet/B29_email_dns/output`
- multi-ISP, multi-IX
- DNS-first email system
- 约 85 compose services
- domains: `qq.com`, `gmail.com`, `163.com`, `outlook.com`, `company.cn`, `startup.net`
- Internet Map `18080`
- Roundcube `8082`
- 证据：DNS MX、SMTP delivery、mail logs、Roundcube、routing state
- Agent tasks: mail reachability debug、fault impact ablation、DNS/mail abuse response、social engineering triage

完整提示词：

```text
请生成一张 16:9 专业科研汇报插图。项目背景：B29 是当前最强的端到端 service ops 展示场景，SeedAgent 可以接管已经运行的邮件/DNS 网络，分析 DNS MX、SMTP 投递、日志、Roundcube 页面和路由状态，并在受控范围内做故障恢复。图属于 SEED Agent 实验展示系列，专业、有真实系统规模感，不要画成普通邮件客户端 UI。

本图目标：展示 Z29 / B29 mail DNS runtime ops。

必须准确呈现这些事实：来源实验 B29_email_dns；Agent 包 Z29_b29_mail_runtime_ops；multi-ISP、multi-IX、DNS-first email system；约 85 compose services；邮件域包括 qq.com、gmail.com、163.com、outlook.com、company.cn、startup.net；Internet Map 端口 18080；Roundcube 端口 8082。

拓扑表达要求：画出多个邮件 provider/domain 集群，通过 DNS/MX routing 和 Internet/IX 连接。Roundcube 作为用户可见入口，DNS cache / authoritative DNS、mail servers、logs 作为证据面。不要只画一个邮箱图标。

Agent 运行逻辑：接管 runtime 后，先只读理解邮件域和 MX；遇到投递失败时分层检查 DNS、route、SMTP、queue、delivery logs、Roundcube；风险动作需要 policy/HITL/rollback。

必须突出任务：mail reachability debug、fault impact ablation、DNS/mail abuse response、social engineering triage。必须突出证据：MX evidence、mail logs、cross-domain delivery、Roundcube page。
```

## 18 Kubernetes Scale-Out 方向

目标文件：`docs/user_manual/images/agent_visual_showcase/k8s_direction.png`

关键事实：

- Kubernetes 分支属于智能体辅助开发验证完善过的规模化部署方向
- 本文只读总结，不重新跑
- 目标：从单机 Docker/Compose 到 multi-worker nodes
- 关注：resource pools、network isolation、runtime observation gateway、SeedOps/SeedAgent access plane、experiment lifecycle

完整提示词：

```text
请生成一张 16:9 专业科研汇报插图。项目背景：SEED 当前主线以 Docker/Compose 运行实验，但我们也探索了 Kubernetes scale-out 方向，这部分是智能体辅助开发、验证和完善过的部署方向。本文不重新跑 Kubernetes 实验，只做只读总结。图属于 SEED Agent 平台化路线系列，专业、克制，不要编造性能指标或具体测试结果。

本图目标：展示 SEED 实验从单机 Docker/Compose 向 Kubernetes 多节点平台演进的方向。

必须准确呈现这些事实：Kubernetes / scale-out direction；multi-worker nodes；resource pools；network isolation；runtime observation gateway；SeedOps / SeedAgent access plane；experiment lifecycle；branch exploration；no new live run in this document。

拓扑表达要求：左侧画 single-node Docker/Compose runtime，右侧画 Kubernetes cluster with multiple worker nodes。中间或上方画 SeedOps/SeedAgent 通过 observation gateway 接入。突出 runtime evidence、isolation、lifecycle control，而不是云原生营销图。

必须表达：Docker/Compose 主线先把运行时接管、策略约束和证据闭环做稳；Kubernetes 方向承载后续规模化、平台化和多资源池部署。
```

## 生成命令模板

单张生成：

```bash
python ~/.codex/skills/rightcodes-imagegen/scripts/rightcodes_imagegen.py generate \
  --prompt "<粘贴某一节的完整提示词>" \
  --out docs/user_manual/images/agent_visual_showcase/<file>.png
```

建议分批：

1. 先生成 `01-08`，覆盖 agent/harness/core 总体能力。
2. 再生成 `12-15`，覆盖 BGP/FRR/ExaBGP/LG 控制面例子。
3. 再生成 `09-11`、`16-18`，覆盖基础、流量、邮件、Kubernetes。

如果 RightCodes 返回 `HTTP 502`，不要换成前端/标记语言画图，稍后重试。

