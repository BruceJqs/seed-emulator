# B51 Runtime Ladder Plan

This file defines the scale ladder by runtime acceptance. A tier is not passed
unless the corresponding SEED Docker topology is generated, started, and
checked with live containers.

The previous `scale-smoke` name was ambiguous, so it is disabled. Use:

- `runtime-ladder-smoke` for live runtime validation.
- `telemetry-smoke` for non-acceptance fixture generation.

## Runtime Tiers

| Tier | Runtime status | Runtime AS roles | Live container gate | Probe routers | Collector routers | Noise routers |
|---|---|---:|---:|---|---|---|
| S0 | implemented | 4 | >=7 | AS50 client/resolver | AS50 route view | none |
| S1 | implemented | 126 | >=129 | AS51-AS90 | AS110-AS121 | AS130-AS149, AS151-AS152, AS154-AS199, AS206-AS207 |
| S1.5 | intermediate runtime test | 222 | >=225 | AS51-AS99, AS102-AS132 | AS133-AS148 | AS31-AS46, AS149-AS254 |
| S2 | local prototype guarded and paused | 1010 | not passed | AS300-AS659 | AS700-AS711 | AS800-AS1423 |

S1.5 is a deliberate intermediate local runtime test: it is larger than S1 but
does not represent S2. S2 must not be represented by a smaller live topology. It
needs a real larger runtime target and live normal/fault/recovery checks before
it can be accepted. The current local S2 prototype targets 1023 containers and
is blocked by default because it previously exhausted this host's ARP/neighbor
cache. It requires `B51_ALLOW_S2_RUNTIME=1` and host neighbor thresholds of at
least `gc_thresh1>=4096`, `gc_thresh2>=8192`, and `gc_thresh3>=65536`;
otherwise use DistributedDocker or a multi-host runner.

## Runtime Gates

For every implemented runtime tier, the controller verifies:

- live container count is at or above the tier gate.
- normal health gate status is `healthy`.
- AS50 recursive `dig` returns `10.20.0.80`.
- AS50 `curl http://www.meta-bench.test/` succeeds.
- AS50 BIRD sees `10.20.0.0/24`.
- every tier collector sees `10.20.0.0/24` in normal state.
- every tier probe resolves and reaches the service in normal state.
- the injected fault disables the internal edge-to-DC BGP peer.
- health gate status becomes `unhealthy`.
- AS50 and every tier collector lose `10.20.0.0/24`.
- AS50 and every tier probe fail DNS/service access after the fault.

## Ordered Runtime Command

```bash
cd examples/internet/B51_meta_style_cascade

COMPOSE_PROJECT_NAME=seed_meta_cascade_runtime \
  PLATFORM=arm \
  SEED_PYTHON=../../../.venv/bin/python \
  bash b51ctl.sh runtime-ladder-smoke
```

The command runs:

```text
S0 generate -> up -> normal-check -> inject-fault -> fault-check -> collect -> down
S1 generate -> up -> normal-check -> inject-fault -> fault-check -> collect -> down
```

## Single Runtime Tier Commands

```bash
TIER=S1 PLATFORM=arm SEED_PYTHON=../../../.venv/bin/python bash b51ctl.sh generate-runtime
TIER=S1 COMPOSE_PROJECT_NAME=seed_meta_cascade_s1 PLATFORM=arm bash b51ctl.sh up-runtime
TIER=S1 COMPOSE_PROJECT_NAME=seed_meta_cascade_s1 PLATFORM=arm bash b51ctl.sh normal-runtime
TIER=S1 COMPOSE_PROJECT_NAME=seed_meta_cascade_s1 PLATFORM=arm bash b51ctl.sh inject-fault-runtime
TIER=S1 COMPOSE_PROJECT_NAME=seed_meta_cascade_s1 PLATFORM=arm bash b51ctl.sh fault-runtime
TIER=S1 COMPOSE_PROJECT_NAME=seed_meta_cascade_s1 PLATFORM=arm bash b51ctl.sh collect-runtime
TIER=S1 COMPOSE_PROJECT_NAME=seed_meta_cascade_s1 PLATFORM=arm bash b51ctl.sh down-runtime
```

Use `TIER=S1.5` for the intermediate runtime test. The controller canonicalizes
`S1.5`, `S1_5`, and `S15` to the same generated tier.

`TIER=S2 ... generate-runtime` is blocked by the S2 safety preflight unless the
operator explicitly enables S2 and the host networking limits are prepared. This
guard is intentional and S2 still has not passed runtime acceptance.

## S2 Host Diagnostics

Before any future S2 runtime attempt, run the diagnostic-only host checks:

```bash
bash b51ctl.sh host-diagnose before-s2
bash b51ctl.sh s2-preflight
```

These commands do not start containers. They capture Docker counts, host links,
neighbor table state, bridge FDB state, recent network-related dmesg lines, and
the S2 neighbor-threshold readiness report. `s2-preflight` must pass before an
operator enables S2 runtime on a local host; a passing preflight is still not
S2 acceptance because normal/fault/recovery live checks must also pass.

## Telemetry Fixtures

`telemetry-smoke` generates deterministic route-view/probe-log fixtures under
`test_log/telemetry/<tier>/` for future scorer and replay work. It does not
start containers and does not pass any runtime tier.

Artifacts:

- `as_inventory.jsonl`
- `links.jsonl`
- `route_views.jsonl`
- `probe_logs.jsonl`
- `events.jsonl`
- `verification_report.json`

Command:

```bash
SEED_PYTHON=../../../.venv/bin/python bash b51ctl.sh telemetry-smoke
```

Deprecated aliases `scale-generate`, `scale-check`, and `logical-scale-smoke`
still print warnings and route to telemetry commands. `scale-smoke` is disabled
because it hid the runtime-vs-fixture distinction.

## Next Runtime Redesign Work

The next real scale step is not another JSON generator. It is a larger runtime
profile with:

- conflict-aware IPAM instead of fixed `10.<asn>.0.0/24` assumptions.
- explicit live normal/fault/recovery gates for S2.
- distributed runner support if one local Docker host cannot start and validate
  the tier without neighbor cache exhaustion.
- the same human/agent intervention surface: live probes, BIRD route views,
  health gate state, recent changes, and restricted recovery actions.
