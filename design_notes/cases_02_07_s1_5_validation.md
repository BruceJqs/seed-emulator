# Cases 02-07 S1.5 Live Validation

Date: 2026-06-06

This note records the first complete S1.5 live closure for the six post-Meta agent benchmark cases. It is evidence-only: S2 remains guarded/preflight-only, and the input document directories are not modified.

## Commands

Each case was run with a unique compose project name:

```sh
COMPOSE_PROJECT_NAME=seed_b52_s1_5_live_check bash b52ctl.sh smoke S1.5
COMPOSE_PROJECT_NAME=seed_b52_mechanism_s1_5 bash b52ctl.sh smoke S1.5
COMPOSE_PROJECT_NAME=seed_b53_s1_5_live_check bash b53ctl.sh smoke S1.5
COMPOSE_PROJECT_NAME=seed_b53_mechanism_s1_5 bash b53ctl.sh smoke S1.5
COMPOSE_PROJECT_NAME=seed_b54_s1_5_live_check bash b54ctl.sh smoke S1.5
COMPOSE_PROJECT_NAME=seed_b54_mechanism_s1_5 bash b54ctl.sh smoke S1.5
COMPOSE_PROJECT_NAME=seed_b55_s1_5_live_check bash b55ctl.sh smoke S1.5
COMPOSE_PROJECT_NAME=seed_b56_s1_5_live_check bash b56ctl.sh smoke S1.5
COMPOSE_PROJECT_NAME=seed_b57_s1_5_live_check bash b57ctl.sh smoke S1.5
COMPOSE_PROJECT_NAME=seed_b57_mechanism_s1_5 bash b57ctl.sh smoke S1.5
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

## Artifact Roots

```text
examples/internet/B52_aws_s3_control_plane/test_log/runtime/S1_5/
examples/internet/B53_fastly_edge_config_bug/test_log/runtime/S1_5/
examples/internet/B54_cloudflare_feature_file_proxy/test_log/runtime/S1_5/
examples/internet/B55_verizon_bgp_route_leak/test_log/runtime/S1_5/
examples/internet/B56_dyn_authoritative_dns_ddos/test_log/runtime/S1_5/
examples/internet/B57_google_network_congestion/test_log/runtime/S1_5/
```

## Limits

B52, B53, B54, and B57 have been upgraded beyond the old shared runtime. B52 has case-local S3 API, index, placement, maintenance-tool, capacity-registry, status-dashboard, and object-shard containers. B53 has case-local config API, validator, compiler, distributor, release manager, edge POPs, and origins. B54 has case-local feature DB, permission rollout, generator, distributor, known-good store, core-proxy POPs, tail services, and origins. B57 has case-local maintenance automation, cluster managers, network-control-plane replicas, config store, route distributor, TE controller, region frontends, workloads, and a real BGP peer disable/enable path for route withdrawal/restoration.

These are still benchmark reproductions, not full commercial service implementations. B52 is not a real S3 storage engine. B53 is not a full CDN cache/runtime. B54 is not a full Cloudflare proxy or Bot Management implementation. B57 models congestion through control/TE state and route reachability, not full packet-level traffic engineering.

B55 and B56 have stronger domain-specific live mechanisms in this round. B55 exercises BGP route propagation and withdrawal. B56 exercises DNS overload without killing `named`, with secondary-DNS contrast and cache-miss recovery validation.

S2 was not run.
