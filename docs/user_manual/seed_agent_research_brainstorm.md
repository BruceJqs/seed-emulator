# SEED Agent Research Brainstorm

## 最新趋势

- Agentic NetOps/AIOps 的核心不是“让 LLM 自由操作网络”, 而是受控工作流: 先收集证据, 再给计划, 通过权限/策略/检查/回滚门后才执行。最新 NetOps/AIOps survey 明确把 autonomy 看成 constrained operational control problem, 评价也要看 trace quality、bounded tool use、sandbox replay、rollback-aware scoring: https://arxiv.org/abs/2605.12729
- AIOpsLab 代表了很适合对齐 SEED 的方向: 动态环境、故障注入、工作负载、telemetry、agent-cloud interface, 任务覆盖 detection/localization/RCA/mitigation。它说明静态 QA benchmark 不够, 需要可交互环境和 oracle: https://proceedings.mlsys.org/paper_files/paper/2025/file/d1f9e4a9f109b6e8b75ed362736f22ec-Paper-Conference.pdf
- NIKA 是最直接的网络故障 benchmark 参照: 真实运行场景、统一 agent-network interface、几百个网络 incident、54 类问题。关键结论是模型能更容易发现有问题, 但 fault localization 和 root cause 仍弱: https://arxiv.org/abs/2512.16381
- SADE 说明“网络 agent 的方法论”本身就是研究点: 它把 Cisco 式逐层排障编码成 phase-gated policy, 把证据收集和假设提交分开, 在 NIKA held-out incident 上明显优于自由 ReAct: https://arxiv.org/abs/2605.04530
- NetAgentBench 把 network configuration agent 评价变成状态机问题, 强调 determinism、bounded execution、多轮稳定性。它观察到 expert-level 配置会出现 exploration meltdown 和 coherence collapse: https://arxiv.org/abs/2604.09678
- MCP-Diag 的重点和我们今天修的点一致: 不让 agent 直接理解杂乱 stdout, 先用确定性工具把 ping/traceroute/dig 等结果转成 schema, 再给 LLM。它同时强调 HITL authorization: https://arxiv.org/abs/2601.22633
- OpenRCA failure analysis 对我们也有警示: RCA 失败常来自 agent framework, 不是单纯模型不强。典型问题是 hallucinated interpretation 和 incomplete exploration, prompt tuning 不够, 要靠结构化通信和运行时检查: https://arxiv.org/abs/2602.09937
- Agent benchmark 正在从“单次成功率”转向可靠性曲面: repeated execution、语义扰动、tool/API 故障注入。ReliabilityBench 给了 pass^k、perturbation、fault injection 这类指标: https://arxiv.org/abs/2601.06112
- 安全评价开始看长轨迹, 不是单轮 prompt。ATBench 把风险按来源、失败模式、真实伤害分类, 做多步 trajectory audit: https://arxiv.org/abs/2604.02022
- Cyber agent 评价也在转向综合能力。CAIBench 覆盖 CTF、attack-defense、cyber range、knowledge、privacy, 结论是知识强不等于多步攻防能力强: https://arxiv.org/abs/2510.24317
- Verifiability-first agent 方向值得跟: 运行时 attestation、audit agent、challenge-response。适合我们把 SeedOps job/artifact/event 变成可审计证据链: https://arxiv.org/abs/2512.17259

## SEED Agent 最有价值的问题

1. 运行态理解是否可靠
   任务: 不看源码拓扑, 只用 inventory/routing/log/page probe 识别当前网络能力。
   价值: 这是 SEED 相比静态 benchmark 的优势, 网络是真跑的。

2. 控制面语义是否能被 agent 正确区分
   任务: 区分 BIRD/FRR/ExaBGP/Looking Glass route-state/event-stream。
   现状: 已修 SeedOps ExaBGP 后端识别, 现在 AS180 会显示 `routing_backend=exabgp` 和 `backend_counts={"exabgp":1}`。

3. 故障定位能否跨层闭环
   任务: route missing -> peer/session/config/log/page 逐层定位。
   指标: 首个错误断点是否正确、证据是否足够、是否误用 shell、耗时和工具调用数。

4. 有限自治修复是否安全
   任务: 只允许 scope-bounded change, 例如 ExaBGP live announce/withdraw、FRR route injection, 必须有 precheck/postcheck/rollback。
   指标: rollback_status、risky_action_count、post-check route convergence。

5. Agent 的“证据链质量”
   任务: 每个结论都能指向 SeedOps artifact、route table、config、log、page probe。
   价值: 这比回答是否正确更像科研问题, 可做评分器。

6. 长轨迹稳定性
   任务: 同一 B30 runtime 连续执行 10 次 read-only 接管、3 次 live announce/withdraw, 看是否 drift。
   指标: pass^k、tool failure recovery、重复执行一致性。

7. Human-in-the-loop 策略门
   任务: read_only 自动跑, net_ops 只允许计划和确认后执行。
   指标: 危险命令阻断率、误阻断率、确认前是否无副作用。

8. 多轮配置是否会破坏已收敛状态
   任务: agent 做一组小范围 BGP/ExaBGP/FRR 配置变更, 每步都检查邻居、路由、页面和回滚点。
   指标: idempotency、coherence collapse 次数、重复执行后的路由一致性。

9. 诊断策略是否比自由推理更重要
   任务: 同一故障用自由 ReAct、layer-gated policy、skill-routed policy 三种方式跑。
   指标: root-cause F1、首个正确故障层、无效工具调用数、过早提交率。

## 下一轮推荐实验

- S1: A13/B30 ExaBGP runtime takeover
  问题: agent 能否识别 AS180 是 IX 直连 ExaBGP router, 并证明 AS2/AS3 学到前缀。

- S2: A14 双视图辨析
  问题: agent 能否明确 Classic LG 是 route-state view, ExaBGP dashboard 是 event-stream view。

- S3: A12 FRR/BIRD backend audit
  问题: agent 能否证明 FRR 是 Router backend, 不是运行时手补; 能否抓 BGP/OSPF/route attributes。

- S4: 受控故障注入
  问题: 故意 withdraw 一个 ExaBGP prefix 或停一个 BGP session, agent 先定位再恢复。

- S5: Agent benchmark 化
  问题: 把 S1-S4 固化成任务集, 每个任务输出 oracle、allowed tools、expected artifacts、scoring rubric。

- S6: NIKA-style 网络 incident 集
  问题: 基于 SEED 自动生成 path failure、BGP policy error、route leak、daemon down、dashboard stale 五类 incident。

- S7: NetAgentBench-style 状态机评估
  问题: 把任务拆成 observe -> propose -> mutate -> verify -> rollback 状态, 每个状态都有通过条件和最大步数。

- S8: SADE-style 分层诊断
  问题: 建一个 `seed-network-diagnostic-escalation` skill, 固定 L2/L3/control-plane/service/page 的升级顺序。

## 评价指标

- Correctness: 节点/服务/peer/prefix/页面入口识别是否正确。
- Evidence: 每个结论是否有 route/config/log/page/process artifact。
- Safety: read_only 是否无副作用, net_ops 是否有 confirmation 和 rollback。
- Efficiency: 工具调用数、耗时、是否跳过无关全仓扫描。
- Robustness: 同任务多次运行是否一致, 端口/容器名变化后是否仍能完成。
- Recovery: tool timeout、schema drift、页面不可达时是否降级为清晰错误。
- Stability: 多轮操作是否保持已正确状态, 是否出现循环探索或反复推翻。
- RCA Quality: 是否定位到 root cause, 而不是把 symptom 当原因。

## 近期工程缺口

- SeedOps routing 工具需要继续 backend-aware: FRR、BIRD、ExaBGP 都要有结构化 schema, 不只 raw text。
- Page probe 要纳入 SeedOps, 让 agent 能直接验证 Map/LG/dashboard, 不依赖人工 curl。
- Dashboard/event log/artifact 要带语义类型: route-state、event-stream、runtime-inventory、daemon-config。
- 任务报告要短: 判断、证据、下一步, 不输出长 JSON。
- Benchmark harness 要支持 perturbation: 端口变化、容器名变化、工具失败、日志截断、邻居 flap。
- 需要 oracle 层: 每个 SEED incident 要能用确定性脚本判断 expected route/session/page 状态。
- 需要过程评分: 记录 hallucinated interpretation、incomplete exploration、coherence collapse、risky action 等失败类型。
