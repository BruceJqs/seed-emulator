# Internet Outage Benchmark Internal Test Notes

## Purpose

Use this file for rehearsal, command execution, and code defense. It is not a
presentation script.

## Preflight

```sh
git status --short --branch
docker ps --format '{{.Names}}' | wc -l
tests/internet/agent_benchmark_cases/doc_links.sh
tests/internet/agent_benchmark_cases/static_contract.sh
```

Expected before a live run:

| Check | Expected |
|---|---|
| branch | `feat/agent-benchmark-internet-outage-cases` |
| untracked input dirs | `meta_seed_benchmark_codex_goal_pack_v0_3/`, `seed_agent_benchmark_cases_2_7/` |
| docs | no CJK in benchmark docs |
| S2 | `s2-preflight` only unless host limits are prepared |

## Seven-Case Smoke Commands

Run one case at a time unless the host has been cleared.

```sh
cd examples/internet/B52_aws_s3_control_plane
COMPOSE_PROJECT_NAME=seed_b52_showcase bash b52ctl.sh smoke S1.5

cd ../B53_fastly_edge_config_bug
COMPOSE_PROJECT_NAME=seed_b53_showcase bash b53ctl.sh smoke S1.5

cd ../B54_cloudflare_feature_file_proxy
COMPOSE_PROJECT_NAME=seed_b54_showcase bash b54ctl.sh smoke S1.5

cd ../B55_verizon_bgp_route_leak
COMPOSE_PROJECT_NAME=seed_b55_showcase bash b55ctl.sh smoke S1.5

cd ../B56_dyn_authoritative_dns_ddos
COMPOSE_PROJECT_NAME=seed_b56_showcase bash b56ctl.sh smoke S1.5

cd ../B57_google_network_congestion
COMPOSE_PROJECT_NAME=seed_b57_showcase bash b57ctl.sh smoke S1.5
```

Artifacts:

```text
examples/internet/B5*/test_log/runtime/S1_5/
```

## B51 Full Demonstration Run

Start with a unique project and exercise id:

```sh
cd examples/internet/B51_meta_style_cascade
export TIER=S1.5
export PLATFORM=amd
export COMPOSE_PROJECT_NAME=seed_meta_cascade_showcase
export B51_EXERCISE_ID=showcase-run-001
export SEED_PYTHON=../../../.venv/bin/python
```

Generate and start with the Internet Map:

```sh
B51_ENABLE_INTERNET_MAP=1 B51_INTERNET_MAP_PORT=8080 bash b51ctl.sh generate-runtime S1.5
B51_ENABLE_INTERNET_MAP=1 B51_INTERNET_MAP_PORT=8080 bash b51ctl.sh up-runtime S1.5
```

Open:

```text
http://127.0.0.1:8080/pro/home
http://127.0.0.1:8510/
```

Start the panel in another terminal before opening port `8510`:

```sh
bash b51ctl.sh panel-runtime S1.5 8510
```

Run the incident:

```sh
bash b51ctl.sh exercise-init-runtime S1.5

bash b51ctl.sh normal-runtime S1.5
bash b51ctl.sh exercise-phase-runtime S1.5 baseline
bash b51ctl.sh exercise-observe-runtime S1.5 public-users
bash b51ctl.sh exercise-observe-runtime S1.5 resolver-support
bash b51ctl.sh exercise-observe-runtime S1.5 external-routing
bash b51ctl.sh exercise-observe-runtime S1.5 meta-noc
bash b51ctl.sh exercise-note-runtime S1.5 facilitator "baseline checked"
bash b51ctl.sh exercise-gate-runtime S1.5 baseline

bash b51ctl.sh exercise-action-runtime S1.5 inject-fault
bash b51ctl.sh fault-runtime S1.5
bash b51ctl.sh exercise-phase-runtime S1.5 impact
bash b51ctl.sh exercise-observe-runtime S1.5 public-users
bash b51ctl.sh exercise-note-runtime S1.5 public-users "DNS and HTTP failure reported"

bash b51ctl.sh exercise-phase-runtime S1.5 external-routing
bash b51ctl.sh exercise-observe-runtime S1.5 external-routing

bash b51ctl.sh exercise-phase-runtime S1.5 meta-triage
bash b51ctl.sh exercise-observe-runtime S1.5 meta-noc
bash b51ctl.sh exercise-observe-runtime S1.5 meta-neteng
bash b51ctl.sh exercise-observe-runtime S1.5 dc-team

bash b51ctl.sh exercise-phase-runtime S1.5 change-audit
bash b51ctl.sh exercise-observe-runtime S1.5 change-audit
bash b51ctl.sh exercise-note-runtime S1.5 meta-neteng "root cause points to internal path policy; no forced unhealthy prefix"

bash b51ctl.sh exercise-phase-runtime S1.5 mitigation
bash b51ctl.sh exercise-action-runtime S1.5 rollback-internal-policy

bash b51ctl.sh exercise-phase-runtime S1.5 recovery-verification
bash b51ctl.sh exercise-action-runtime S1.5 verify-health
bash b51ctl.sh exercise-action-runtime S1.5 canary-reannounce
bash b51ctl.sh exercise-action-runtime S1.5 validate-recovery
bash b51ctl.sh recovery-runtime S1.5
bash b51ctl.sh exercise-observe-runtime S1.5 public-users
bash b51ctl.sh exercise-observe-runtime S1.5 external-routing
bash b51ctl.sh exercise-observe-runtime S1.5 meta-noc
bash b51ctl.sh exercise-gate-runtime S1.5 recovery-verification

bash b51ctl.sh collect-runtime S1.5
bash b51ctl.sh down-runtime S1.5
```

Residual check:

```sh
docker ps -a --filter label=com.docker.compose.project=seed_meta_cascade_showcase --format '{{.Names}}'
docker network ls --filter name=seed_meta_cascade_showcase --format '{{.Name}}'
```

## B51 Evidence Checklist

| Phase | Evidence |
|---|---|
| baseline | `runtime_container_count.txt`, DNS answer `10.20.0.80`, route `10.20.0.0/24`, health `healthy` |
| fault | route collectors report no `10.20.0.0/24`, probes fail DNS/HTTP, health `unhealthy` |
| triage | resolver, external-routing, meta-noc, meta-neteng, dc-team observations exist |
| mitigation | action result for `rollback-internal-policy` is success |
| recovery | health `healthy`, route visible, DNS/HTTP pass, `validate-recovery` success |
| cleanup | compose project containers gone |

Artifact root:

```text
examples/internet/B51_meta_style_cascade/test_log/runtime/S1_5/
```

## During The Live Run, Watch

| Command | Watch For | Meaning |
|---|---|---|
| `up-runtime` | S1.5 topology count reaches 225; map uses a separate UI container | the live gate is topology scale, not the optional map |
| `normal-runtime` | DNS answer `10.20.0.80`, HTTP 200, route `10.20.0.0/24`, health `healthy` | public path, resolver path, BGP view, and edge gate agree |
| `exercise-observe-runtime public-users` | user view has only user-visible symptoms | the exercise does not reveal root cause too early |
| `exercise-observe-runtime external-routing` | route view changes after the fault | control-plane evidence is separate from application logs |
| `exercise-observe-runtime meta-neteng` | edge-to-DC or policy evidence appears | operator can narrow the root cause without editing clients |
| `fault-runtime` | health `unhealthy`, route missing, DNS/HTTP fail | withdrawal follows the health gate |
| `exercise-action-runtime rollback-internal-policy` | action result is success | recovery starts at the internal fault |
| `exercise-action-runtime canary-reannounce` | prefix returns after health verification | no forced unhealthy announcement |
| `recovery-runtime` | health, route, DNS, and HTTP all pass | external recovery is validated |
| `down-runtime` | residual container and network checks are empty | demo cleanup is complete |

## Panel Reading Order

| Panel Area | Read First |
|---|---|
| runtime | live container count, recorded runtime count, generated tier |
| flow | normal, fault, recovery sequence for the case |
| evidence | normal/fault/recovery artifact presence |
| exercise | phase directories, observation files, action results |
| policy | allowed observations/actions and forbidden shortcuts |
| files | generated compose and collected host artifacts |

## Code Defense Map

| Question | File | Function Or Data |
|---|---|---|
| where is the topology built | [meta_style_cascade.py](../examples/internet/B51_meta_style_cascade/meta_style_cascade.py) | `build_case()` |
| where are S1.5 counts defined | [case_metadata.json](../examples/internet/B51_meta_style_cascade/case_metadata.json) | `scale_tiers.S1_5` |
| where is the health gate installed | [meta_style_cascade.py](../examples/internet/B51_meta_style_cascade/meta_style_cascade.py) | edge router service scripts and bindings |
| where is BGP withdrawal tested | [b51ctl.sh](../examples/internet/B51_meta_style_cascade/b51ctl.sh) | `fault_check`, agent observe/action path |
| where are role gates enforced | [b51ctl.sh](../examples/internet/B51_meta_style_cascade/b51ctl.sh) | `exercise_gate` |
| where are common B52-B57 phases enforced | [agent_case_ctl_common.sh](../examples/internet/_agent_benchmark_common/agent_case_ctl_common.sh) | `ab_smoke`, `ab_exercise_gate` |
| where is the panel state built | [showcase_panel.py](../examples/internet/_agent_benchmark_common/showcase_panel.py) | `build_state()` and `artifact_summary()` |
| where are policy shortcuts rejected | [agent_policy.json](../examples/internet/B51_meta_style_cascade/agent_policy.json) and [static_contract.sh](../tests/internet/agent_benchmark_cases/static_contract.sh) | forbidden actions |

## If Asked During Code Review

| Question | Direct Answer |
|---|---|
| How do we know the topology is live? | controller writes `runtime_container_count.txt`; panel also reads current Docker counts by compose project and service prefix |
| How do we know the fault is not a DNS kill? | B51 checks health-gated route withdrawal; B56 keeps DNS processes alive and validates cache-miss behavior |
| How do we know users do not get privileged answers? | observations are role-scoped and stored per role under the exercise directory |
| How do we know recovery is bounded? | policy files list allowed actions; gates require the staged evidence before recovery validation |
| How do we know S1.5 is the accepted tier? | validation record lists measured counts and smoke times; S2 remains preflight-only |
| How do we explain the code quickly? | generator builds roles and scale; controller drives runtime; common shell enforces timeline; panel reads artifacts |

## Short Code Excerpts

[agent_case_ctl_common.sh](../examples/internet/_agent_benchmark_common/agent_case_ctl_common.sh)

```bash
ab_smoke() {
  ab_generate
  ab_up
  ab_normal_check
  ab_exercise_init
  ab_exercise_phase baseline
  ab_exercise_observe public-users
  ab_exercise_observe provider-ops
}
```

[showcase_panel.py](../examples/internet/_agent_benchmark_common/showcase_panel.py)

```python
def artifact_summary(artifact_dir):
    files = list(artifact_dir.rglob("*")) if artifact_dir.exists() else []
    regular = [path for path in files if path.is_file()]
    return {
        "runtime_count": key_values(artifact_dir / "runtime_container_count.txt"),
        "exercise_dirs": len(list((artifact_dir / "exercise").glob("*"))) if (artifact_dir / "exercise").exists() else 0,
    }
```

## Rejected Shortcuts

| Shortcut | Reason |
|---|---|
| kill DNS | hides the health-gated BGP mechanism |
| edit client hosts | bypasses recursive DNS and routing evidence |
| force announce unhealthy prefix | violates the gate; recovery must restore backend health first |
| skip canary | removes external recovery proof |
| edit scorer or oracle | not an operator action |
| global reset | hides root cause and invalidates the ledger |

## If Asked Why S1.5

| Tier | Answer |
|---|---|
| S0 | mechanism smoke only |
| S1 | first hundred-container rehearsal |
| S1.5 | largest accepted live showcase tier on the current host |
| S2 | guarded; previous local attempt reached 1023 containers but is not accepted |

## Closeout Checks

```sh
tests/internet/agent_benchmark_cases/doc_links.sh
tests/internet/agent_benchmark_cases/static_contract.sh
rg -n --pcre2 '\p{Han}' design_notes examples/internet/B51_meta_style_cascade examples/internet/B52_aws_s3_control_plane examples/internet/B53_fastly_edge_config_bug examples/internet/B54_cloudflare_feature_file_proxy examples/internet/B55_verizon_bgp_route_leak examples/internet/B56_dyn_authoritative_dns_ddos examples/internet/B57_google_network_congestion examples/internet/_agent_benchmark_common tests/internet/agent_benchmark_cases tests/internet/meta_style_cascade
git diff --check
```
