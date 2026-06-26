# Internet Outage Case Implementation Notes

## Showcase Matrix

| Case | Runtime | Panel | Mechanism | First Observation | Code Entry |
|---|---:|---:|---|---|---|
| [B51 Meta cascade](../examples/internet/B51_meta_style_cascade/) | 225/225 | 8510 | health-gated DNS/BGP withdrawal | DNS and service fail after edge-to-DC loss | [meta_style_cascade.py](../examples/internet/B51_meta_style_cascade/meta_style_cascade.py), [b51ctl.sh](../examples/internet/B51_meta_style_cascade/b51ctl.sh) |
| [B52 S3 control plane](../examples/internet/B52_aws_s3_control_plane/) | 182/180 | 8520 | maintenance removes index and placement capacity | API 503, object shards healthy | [aws_s3_control_plane.py](../examples/internet/B52_aws_s3_control_plane/aws_s3_control_plane.py), [b52ctl.sh](../examples/internet/B52_aws_s3_control_plane/b52ctl.sh) |
| [B53 edge config](../examples/internet/B53_fastly_edge_config_bug/) | 186/185 | 8530 | valid config triggers POP runtime bug | affected POPs 5xx, origins healthy | [fastly_edge_config_bug.py](../examples/internet/B53_fastly_edge_config_bug/fastly_edge_config_bug.py), [b53ctl.sh](../examples/internet/B53_fastly_edge_config_bug/b53ctl.sh) |
| [B54 feature file proxy](../examples/internet/B54_cloudflare_feature_file_proxy/) | 191/190 | 8540 | generated feature file breaks core proxy | proxy/tail 5xx, origins healthy | [cloudflare_feature_file_proxy.py](../examples/internet/B54_cloudflare_feature_file_proxy/cloudflare_feature_file_proxy.py), [b54ctl.sh](../examples/internet/B54_cloudflare_feature_file_proxy/b54ctl.sh) |
| [B55 route leak](../examples/internet/B55_verizon_bgp_route_leak/) | 177/177 | 8550 | more-specific BGP leak via Verizon path | unfiltered probes learn `10.55.0.0/25` | [verizon_route_leak.py](../examples/internet/B55_verizon_bgp_route_leak/verizon_route_leak.py), [b55ctl.sh](../examples/internet/B55_verizon_bgp_route_leak/b55ctl.sh) |
| [B56 DNS DDoS](../examples/internet/B56_dyn_authoritative_dns_ddos/) | 178/178 | 8560 | authoritative DNS path overload | fresh lookups fail, `named` stays alive | [dyn_dns_ddos.py](../examples/internet/B56_dyn_authoritative_dns_ddos/dyn_dns_ddos.py), [b56ctl.sh](../examples/internet/B56_dyn_authoritative_dns_ddos/b56ctl.sh) |
| [B57 control-plane deschedule](../examples/internet/B57_google_network_congestion/) | 194/194 | 8570 | automation drops network control plane | external route withdrawn, workloads local healthy | [google_network_congestion.py](../examples/internet/B57_google_network_congestion/google_network_congestion.py), [b57ctl.sh](../examples/internet/B57_google_network_congestion/b57ctl.sh) |

`Runtime` is `live containers / minimum gate`. S2 remains preflight-only on the
current host.

## Run

Run one target case from its directory. B55 is the route-control example:

```sh
cd examples/internet/B55_verizon_bgp_route_leak
COMPOSE_PROJECT_NAME=seed_b55_showcase bash b55ctl.sh smoke S1.5
```

The common smoke path:

```text
generate -> up -> normal -> baseline -> inject fault -> impact
-> user/frontline -> provider triage -> change audit -> mitigation
-> recovery verification -> postmortem -> collect -> down
```

Open the read-only panel after a run or from collected artifacts:

```sh
bash b55ctl.sh panel-snapshot-runtime S1.5
bash b55ctl.sh panel-runtime S1.5 8550
```

## Evidence Roots

| Evidence | Path |
|---|---|
| S1.5 validation record | [cases_02_07_s1_5_validation.md](cases_02_07_s1_5_validation.md) |
| container gate | `test_log/runtime/S1_5/runtime_container_count.txt` |
| panel snapshot | `test_log/runtime/S1_5/showcase_panel/index.html` |
| role observations | `test_log/runtime/S1_5/exercise/<id>/observations/` |
| gated actions | `test_log/runtime/S1_5/exercise/<id>/actions/` |
| host collection | `test_log/runtime/S1_5/host/` |

## Code Points

| Purpose | File | Detail |
|---|---|---|
| shared lifecycle | [agent_case_ctl_common.sh](../examples/internet/_agent_benchmark_common/agent_case_ctl_common.sh) | generate/up/check/exercise/collect/down contract |
| shared panel | [showcase_panel.py](../examples/internet/_agent_benchmark_common/showcase_panel.py) | read-only view of generated output, live count, artifacts, policy |
| B51 controller | [b51ctl.sh](../examples/internet/B51_meta_style_cascade/b51ctl.sh) | custom Meta cascade plus map/demo support |
| B52-B57 static test | [static_contract.sh](../tests/internet/agent_benchmark_cases/static_contract.sh) | policy denial, ledger gates, doc links |
| B52-B57 generate smoke | [generate_smoke.sh](../tests/internet/agent_benchmark_cases/generate_smoke.sh) | S0 generation plus panel snapshot |

[agent_case_ctl_common.sh](../examples/internet/_agent_benchmark_common/agent_case_ctl_common.sh)

```bash
ab_smoke() {
  ab_generate
  ab_up
  ab_normal_check
  ab_exercise_init
  # Staged observations and gates continue through recovery and postmortem.
}
```

[showcase_panel.py](../examples/internet/_agent_benchmark_common/showcase_panel.py)

```python
def build_state(case_dir, case_id, tier, project, prefix):
    artifact_dir = case_dir / "test_log" / "runtime" / tier
    return {
        "output": {"compose_exists": (case_dir / "output/docker-compose.yml").exists()},
        "runtime": {"live_containers": docker_live_count(project),
                    "artifacts": artifact_summary(artifact_dir)},
    }
```

## Visual Assets

| Asset | File | Prompt | Role |
|---|---|---|---|
| seven-case overview | [internet_outage_cases_overview.png](assets/internet_outage_cases_overview.png) | [internet_outage_cases_overview.prompt.txt](assets/internet_outage_cases_overview.prompt.txt) | optional opening slide; direct AI infographic with case scale and mechanism |
| per-case panel | `test_log/runtime/S1_5/showcase_panel/index.html` | controller-generated | primary demo surface after each run |

Overview image record: Right Code `gpt-image-2`, streaming chat, requested
`1536x1024`, actual `1672x941`.

Runtime proof comes from controller checks, panel snapshots, and collected
artifacts.

## Validation

```sh
tests/internet/agent_benchmark_cases/doc_links.sh
tests/internet/agent_benchmark_cases/static_contract.sh
git diff --check
```
