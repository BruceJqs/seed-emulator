# Strict Runtime Plan V2

## Goal

为 strict-v2 lane 提供一份真正可接到 `prepare/build` 的运行前置方案。

## Runtime Split

### Design Stage

- 先产出 same-topology scenario definition
- 再产出 control / treatment runtime profiles
- 最后才进入真正的 build

### Build Stage

control / treatment 必须共享：

- 相同 scenario root
- 相同 artifact root 结构
- 相同 cleanup ownership 规则

## Namespace Plan

- control:
  - `COMPOSE_PROJECT_NAME=foundry-routing-v2-control`
- treatment:
  - `COMPOSE_PROJECT_NAME=foundry-routing-v2-treatment`

约束：

- 只允许 namespace 不同
- 不允许 topology / service layout / observables contract 不同

## Port / Lease Plan

- 所有 host port override 必须登记在 strict-v2 runtime profile
- 若 control / treatment 需要串行运行，则 cleanup ownership 必须显式
- 若 lease 不清楚，则不得进入 build

## Prepare Checklist

1. strict-v2 scenario unit 已存在
2. component reuse mapping 已冻结
3. observables contract 已冻结
4. runtime profile 已定义
5. cleanup ownership 已写清

## Build Entry Decision

当上面五条满足时，下一步不是直接 `accepted`，而是：

- 先执行 strict-v2 `prepare`
- 验证 runtime profile / lease / artifact contract
- 再进入第一轮 strict-v2 `build`
