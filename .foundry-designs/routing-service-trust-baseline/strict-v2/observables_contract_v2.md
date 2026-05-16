# Observables Contract V2

## Goal

让 strict-v2 lane 的 control / treatment 在观测面上完全可比。

## Required Observables

### 1. Route Snapshots

control / treatment 都必须产出：

- `route_snapshot_control.json`
- `route_snapshot_treatment.json`

要求：

- 采样时间点明确
- 采样节点明确
- 至少覆盖 attacker / service / observer 三类角色

### 2. Looking-Glass State

control / treatment 都必须能回答：

- observer 看到的最佳路由是什么
- hijack 生效前后路径是否变化

### 3. Service Reachability

control / treatment 都必须产出统一格式的：

- `service_reachability.log`

要求：

- 相同 client 角色
- 相同服务目标
- 相同检查顺序

### 4. Artifact Completeness

control / treatment 都必须满足：

- `run_manifest.json`
- `evidence_index.json`
- `output-docker-compose.yml`

## Comparison Rule

下一轮 strict-v2 不能只回答“两个 run 都成功了”，必须回答：

- route state 是否变化
- service outcome 是否变化
- 两者之间是否存在可解释关联

## Reviewer Gate

只有当 control / treatment 使用同一份 observables contract，review 才能把结果视为研究级对照候选。
