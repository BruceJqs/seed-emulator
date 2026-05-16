# Component Reuse Mapping V2

## Goal

把 strict-v2 lane 从“整例子拼接”切成“组件级复用”。

## Reuse Rule

允许复用：

- service role layout
- route event implementation pattern
- observability component pattern

不允许直接复用：

- 整套 control 例子作为最终 control
- 整套 hijack 例子作为最终 treatment
- 彼此独立的 compose namespace / cleanup 逻辑

## Component Mapping

### Service Layout Anchor

来源：

- `examples/internet/B29_email_dns`

提取：

- service node role
- client role
- service reachability checks
- mail/web/DNS 这类“上层可观测 outcome”组织方式

不直接沿用：

- 旧 control lane 的整套目录级运行方式
- 只属于 B29 的 compose project 名称假设

### Hijack Event Anchor

来源：

- `examples/yesterday_once_more/Y01_bgp_prefix_hijacking/demo`

提取：

- forged-origin hijack 事件结构
- attacker role pattern
- route event 注入方式

不直接沿用：

- 旧 treatment lane 的整套 topology
- 只属于 Y01 的 compose/output 布局

### Control-Plane Observability

来源：

- `examples/basic/A13_exabgp_control_plane`
- `examples/basic/A14_bgp_event_looking_glass`

提取：

- ExaBGP / looking-glass 观察面
- 路由状态与事件时间线的对照方式

## V2 Minimum Output

strict-v2 最小场景必须能回答：

1. 哪些节点/角色来自 B29 思路
2. 哪些 route event 机制来自 Y01 思路
3. 哪些 observability 机制来自 A13/A14
4. 哪些内容是 Foundry 自己重新定义的 glue layer

## Foundry-Owned Glue Layer

- same-topology scenario definition
- artifact contract
- resource lease / cleanup contract
- control / treatment runtime profile split
