# Cases 02-07 S1.5 Live Validation

Date: 2026-06-06, refreshed on 2026-06-26

Evidence-only record for complete S1.5 live closure of B52-B57. S2 remains
guarded/preflight-only. Input document directories are not modified.

## Commands

Current showcase run used `PLATFORM=amd` and
`SEED_PYTHON=../../../.venv/bin/python` from each case directory:

```sh
COMPOSE_PROJECT_NAME=seed_b52_showcase B52_EXERCISE_ID=showcase-live-20260626 bash b52ctl.sh smoke S1.5
COMPOSE_PROJECT_NAME=seed_b53_showcase B53_EXERCISE_ID=showcase-live-20260626 bash b53ctl.sh smoke S1.5
COMPOSE_PROJECT_NAME=seed_b54_showcase B54_EXERCISE_ID=showcase-live-20260626 bash b54ctl.sh smoke S1.5
COMPOSE_PROJECT_NAME=seed_b55_showcase B55_EXERCISE_ID=showcase-live-20260626 bash b55ctl.sh smoke S1.5
COMPOSE_PROJECT_NAME=seed_b56_showcase B56_EXERCISE_ID=showcase-live-20260626 bash b56ctl.sh smoke S1.5
COMPOSE_PROJECT_NAME=seed_b57_showcase B57_EXERCISE_ID=showcase-live-20260626 bash b57ctl.sh smoke S1.5
```

The smoke chain is:

```text
generate -> up -> normal -> exercise baseline -> inject fault -> impact -> user/frontline -> provider/ops triage -> control-plane/change audit -> mitigation -> recovery verification -> postmortem -> collect -> down
```

## Results

| Case | Runtime status | Containers | Exercise gates | Main evidence |
| --- | --- | ---: | ---: | --- |
| B52 AWS S3 control plane | S1.5 accepted with S3 multi-container control-plane runtime | 182/180 | 8 | 75 normal, 75 fault, and 75 recovery client HTTP checks; fault state records 3 removed index containers, 2 removed placement containers, object-shard health, capacity-registry root cause, API 503, and recovery records restored subsystem containers plus integrity/canary/backlog evidence |
| B53 Fastly edge config bug | S1.5 accepted with case-local Fastly multi-POP/config runtime | 186/185 | 8 | 75 normal, 75 fault, and 75 recovery client HTTP checks; fault state records legal trigger config, validator pass, compiler artifact v43, distributor propagation to 7/8 affected POPs, runtime errors at affected POPs, canary POP contrast, and origin-health contrast |
| B54 Cloudflare feature file proxy | S1.5 accepted with case-local Cloudflare feature-file/core-proxy runtime | 191/190 | 8 | 75 normal, 75 fault, and 75 recovery client HTTP checks; fault state records DB permission rollout, runaway feature generator, bad feature count/size/hash, global distributor state, core proxy 5xx, tail service degradation, and origin-health contrast; recovery records known-good rollback, fail-small, canary, and tail validation |
| B55 Verizon BGP route leak | S1.5 accepted with route-leak control-plane runtime | 177/177 | 8 | 65 unfiltered probes saw `10.55.0.0/25`; filtered probes kept service reachability; collector saw AS path `701 703 702`; recovery withdrew the leak and restored aggregate reachability |
| B56 Dyn authoritative DNS DDoS | S1.5 accepted with DNS-overload runtime | 178/178 | 8 | 65 client fresh lookups failed under overload while `named` stayed alive; secondary-provider lookup returned `10.56.40.80`; recovery cleared the drop and 65 fresh lookups plus HTTP checks passed |
| B57 Google network congestion | S1.5 accepted with case-local Google route/control-plane runtime | 194/194 | 8 | 75 normal, 75 fault, and 75 recovery client route/HTTP checks; fault disables the edge BGP transit peer so external collectors/probes lose `10.57.10.0/24` and curl returns `000`, while edge/workload containers stay locally healthy; recovery re-enables the peer and records control-plane rebuild plus region verification |

## 2026-06-26 Showcase Run

| Case | Command Time | Residual Project Containers | Residual Case Containers | Residual Networks |
|---|---:|---:|---:|---:|
| B52 | `4:04.28` | 0 | 0 | 0 |
| B53 | `4:01.87` | 0 | 0 | 0 |
| B54 | `4:08.73` | 0 | 0 | 0 |
| B55 | `4:21.13` | 0 | 0 | 0 |
| B56 | `5:30.82` | 0 | 0 | 0 |
| B57 | `4:45.37` | 0 | 0 | 0 |

Panel snapshots were generated under each case's
`test_log/runtime/S1_5/showcase_panel/index.html`.

## Artifact Roots

```text
examples/internet/B52_aws_s3_control_plane/test_log/runtime/S1_5/
examples/internet/B53_fastly_edge_config_bug/test_log/runtime/S1_5/
examples/internet/B54_cloudflare_feature_file_proxy/test_log/runtime/S1_5/
examples/internet/B55_verizon_bgp_route_leak/test_log/runtime/S1_5/
examples/internet/B56_dyn_authoritative_dns_ddos/test_log/runtime/S1_5/
examples/internet/B57_google_network_congestion/test_log/runtime/S1_5/
```

## Boundaries

| Case | Included Runtime Mechanism | Boundary |
|---|---|---|
| B52 | S3 API, index, placement, maintenance tool, capacity registry, status dashboard, object-shard health contrast | not a real S3 storage engine |
| B53 | config API, validator, compiler, distributor, release manager, 8 POPs, origins | not a full CDN cache/runtime |
| B54 | feature DB, permission rollout, generator, distributor, known-good store, core proxy, tail services, origins | not a full Cloudflare proxy or Bot Management implementation |
| B55 | BGP route propagation, more-specific leak, filtered/unfiltered probes, route collectors, withdrawal recovery | no S2 run |
| B56 | DNS overload without killing `named`, secondary-DNS contrast, cache-miss recovery validation | no S2 run |
| B57 | maintenance automation, cluster managers, network-control-plane replicas, config store, route distributor, TE controller, route withdrawal/restoration | congestion is modeled through control/TE state and reachability, not packet-level traffic engineering |
