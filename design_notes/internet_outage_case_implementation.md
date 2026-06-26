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

## Code Walkthrough Order

| Step | Open | What To Show |
|---|---|---|
| 1 | case generator | `build_case()` creates provider roles, client/probe roles, control-plane views, and S1.5 expansion |
| 2 | case controller | normal, fault, recovery, and exercise commands map to live observations and bounded actions |
| 3 | shared controller | `ab_smoke()` enforces the same incident timeline for B52-B57 |
| 4 | policy | forbidden actions reject shortcuts before recovery is accepted |
| 5 | panel | runtime and artifact readers expose generated output, live counts, and exercise evidence |
| 6 | tests | static contract and generate smoke catch missing files, missing links, shortcut leakage, and panel generation |

## Per-Case Code Entry

| Case | Generator Entry | Controller Entry | Runtime Detail To Show |
|---|---|---|---|
| B51 | [meta_style_cascade.py](../examples/internet/B51_meta_style_cascade/meta_style_cascade.py) `build_case()` | [b51ctl.sh](../examples/internet/B51_meta_style_cascade/b51ctl.sh) `fault_check`, `exercise_gate`, `recovery_check` | health gate withdraws and reannounces the DNS/service prefix |
| B52 | [aws_s3_control_plane.py](../examples/internet/B52_aws_s3_control_plane/aws_s3_control_plane.py) `build_case()` | [b52ctl.sh](../examples/internet/B52_aws_s3_control_plane/b52ctl.sh) | index and placement capacity are restored before canary PUT |
| B53 | [fastly_edge_config_bug.py](../examples/internet/B53_fastly_edge_config_bug/fastly_edge_config_bug.py) `build_case()` | [b53ctl.sh](../examples/internet/B53_fastly_edge_config_bug/b53ctl.sh) | POP failures are separated from origin health |
| B54 | [cloudflare_feature_file_proxy.py](../examples/internet/B54_cloudflare_feature_file_proxy/cloudflare_feature_file_proxy.py) `build_case()` | [b54ctl.sh](../examples/internet/B54_cloudflare_feature_file_proxy/b54ctl.sh) | generated feature-file state drives proxy failures |
| B55 | [verizon_route_leak.py](../examples/internet/B55_verizon_bgp_route_leak/verizon_route_leak.py) `build_case()` | [b55ctl.sh](../examples/internet/B55_verizon_bgp_route_leak/b55ctl.sh) | collectors distinguish leaked more-specific routes from valid aggregate routes |
| B56 | [dyn_dns_ddos.py](../examples/internet/B56_dyn_authoritative_dns_ddos/dyn_dns_ddos.py) `build_case()` | [b56ctl.sh](../examples/internet/B56_dyn_authoritative_dns_ddos/b56ctl.sh) | overload affects authoritative lookup path while DNS processes remain alive |
| B57 | [google_network_congestion.py](../examples/internet/B57_google_network_congestion/google_network_congestion.py) `build_case()` | [b57ctl.sh](../examples/internet/B57_google_network_congestion/b57ctl.sh) | automation deschedules control-plane jobs before routes and service recover |

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
        "runtime": {
            "compose_live_containers": docker_live_count(project),
            "prefix_live_containers": docker_prefix_live_count(prefix),
            "artifacts": artifact_summary(artifact_dir),
        },
    }
```

The panel displays both Docker-derived live counts and recorded
`runtime_container_count.txt` values so a live demo and a collected snapshot can
be read the same way.

## Visual Assets

| Asset | File | Prompt | Role |
|---|---|---|---|
| seven-case overview | [internet_outage_cases_overview.png](assets/internet_outage_cases_overview.png) | [internet_outage_cases_overview.prompt.txt](assets/internet_outage_cases_overview.prompt.txt) | optional opening slide; direct AI infographic with case scale and mechanism |
| macro-to-micro structure | [internet_outage_macro_to_micro.png](assets/internet_outage_macro_to_micro.png) | [internet_outage_macro_to_micro.prompt.txt](assets/internet_outage_macro_to_micro.prompt.txt) | benchmark family, runtime tier, roles, exercise, evidence |
| B51 S1.5 topology | [internet_outage_b51_s1_5_topology.png](assets/internet_outage_b51_s1_5_topology.png) | [internet_outage_b51_s1_5_topology.prompt.txt](assets/internet_outage_b51_s1_5_topology.prompt.txt) | concrete Meta cascade topology and scale groups |
| B51 incident sequence | [internet_outage_b51_incident_sequence.png](assets/internet_outage_b51_incident_sequence.png) | [internet_outage_b51_incident_sequence.prompt.txt](assets/internet_outage_b51_incident_sequence.prompt.txt) | fault and recovery timeline |
| per-case panel | `test_log/runtime/S1_5/showcase_panel/index.html` | controller-generated | primary demo surface after each run |

Generated image record: Right Code `gpt-image-2`, streaming chat, requested
`1536x1024`, actual `1672x941` for each generated image.

Runtime proof comes from controller checks, panel snapshots, and collected
artifacts.

## Validation

```sh
tests/internet/agent_benchmark_cases/doc_links.sh
tests/internet/agent_benchmark_cases/static_contract.sh
tests/internet/agent_benchmark_cases/generate_smoke.sh
git diff --check
```
