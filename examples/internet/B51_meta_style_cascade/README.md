# B51 Meta-style Cascade Benchmark

This is the first Networked Agent Benchmark case in this repository. It models
a Meta/Facebook-style cascade:

```text
internal edge-to-DC path fault
  -> edge health gate marks backend unreachable
  -> health gate withdraws the edge DNS/service prefix through BGP
  -> external resolver/client sees DNS and service failures
```

## Runtime Acceptance

A tier is accepted only when its SEED Docker topology is generated, started, and
checked as live containers. Generated route-view rows, probe logs, or JSON files
are not runtime tier acceptance.

Current runtime ladder:

| Tier | Status | Live container gate | Checked runtime viewpoints |
|---|---|---:|---|
| S0 | implemented runtime | at least 7 | AS50 resolver/client and AS50 route view |
| S1 | implemented runtime | at least 129 | AS51-AS90 probes and AS110-AS121 collectors |
| S1.5 | intermediate runtime test | at least 225 | AS51-AS99/AS102-AS132 probes and AS133-AS148 collectors |
| S2 | local prototype guarded and paused | not passed | 1023-container target requires prepared host limits or distributed runtime |

`scale-smoke` is intentionally disabled because it used to be ambiguous. Use
`runtime-ladder-smoke` for the live SEED Docker ladder. Use `telemetry-smoke`
only for non-acceptance fixture generation.

## Runtime Roles

- AS10: external transit and route-view path.
- AS20: edge authoritative DNS, edge service, and health gate on
  `edge-router`.
- AS30: internal DC/backend dependency on `dc-router`.
- AS50: external probe and recursive resolver on `client-router`.
- AS51-AS90: S1 external probe routers.
- AS110-AS121: S1 route collector routers.
- AS130-AS149, AS151-AS152, AS154-AS199, AS206-AS207: S1
  background-noise routers.
- AS51-AS99 and AS102-AS132: S1.5 external probe routers.
- AS133-AS148: S1.5 route collector routers.
- AS31-AS46 and AS149-AS254: S1.5 background-noise routers. AS255 is
  intentionally avoided because SEED IX auto address assignment maps ASNs only
  through 254.

The case uses router-local service loopback IPs to keep P0-P3 focused on the
control-plane cascade. The authoritative DNS prefix is `10.20.0.0/24`; the edge
DNS IP is `10.20.0.53`; the edge service IP is `10.20.0.80`; the resolver IP is
`10.50.0.53`; the backend dependency IP is `10.30.0.80`; the service name is
`www.meta-bench.test`.

## Run One Runtime Tier

```bash
cd examples/internet/B51_meta_style_cascade

TIER=S0 PLATFORM=arm SEED_PYTHON=../../../.venv/bin/python bash b51ctl.sh generate-runtime
TIER=S0 COMPOSE_PROJECT_NAME=seed_meta_cascade_s0 PLATFORM=arm bash b51ctl.sh up-runtime
TIER=S0 COMPOSE_PROJECT_NAME=seed_meta_cascade_s0 PLATFORM=arm bash b51ctl.sh normal-runtime
TIER=S0 COMPOSE_PROJECT_NAME=seed_meta_cascade_s0 PLATFORM=arm bash b51ctl.sh inject-fault-runtime
TIER=S0 COMPOSE_PROJECT_NAME=seed_meta_cascade_s0 PLATFORM=arm bash b51ctl.sh fault-runtime
TIER=S0 COMPOSE_PROJECT_NAME=seed_meta_cascade_s0 PLATFORM=arm bash b51ctl.sh collect-runtime
TIER=S0 COMPOSE_PROJECT_NAME=seed_meta_cascade_s0 PLATFORM=arm bash b51ctl.sh down-runtime
```

S1 and S1.5 use the same commands with `TIER=S1` or `TIER=S1.5` and a unique
compose project name.
`normal-runtime` writes `test_log/runtime_container_count.txt` or the
tier-specific equivalent and fails if the live container count is below the
tier gate.

## Interactive S1.5 Incident Exercise

The S1.5 test is an interactive incident exercise, not a result-only demo. The
operator must collect role-scoped observations, record notes, pass staged ledger
gates, use only allowed mitigation actions, and validate recovery externally.

Read the exercise design first:

```text
interactive_exercise_design.md
```

Main controller surface:

```bash
TIER=S1.5 COMPOSE_PROJECT_NAME=seed_meta_cascade_s1_5_exercise \
  B51_EXERCISE_ID=classroom-run-001 \
  bash b51ctl.sh exercise-init-runtime S1.5

TIER=S1.5 COMPOSE_PROJECT_NAME=seed_meta_cascade_s1_5_exercise \
  B51_EXERCISE_ID=classroom-run-001 \
  bash b51ctl.sh exercise-phase-runtime S1.5 baseline

TIER=S1.5 COMPOSE_PROJECT_NAME=seed_meta_cascade_s1_5_exercise \
  B51_EXERCISE_ID=classroom-run-001 \
  bash b51ctl.sh exercise-observe-runtime S1.5 public-users

TIER=S1.5 COMPOSE_PROJECT_NAME=seed_meta_cascade_s1_5_exercise \
  B51_EXERCISE_ID=classroom-run-001 \
  bash b51ctl.sh exercise-note-runtime S1.5 facilitator "baseline evidence collected"

TIER=S1.5 COMPOSE_PROJECT_NAME=seed_meta_cascade_s1_5_exercise \
  B51_EXERCISE_ID=classroom-run-001 \
  bash b51ctl.sh exercise-gate-runtime S1.5 baseline
```

Exercise artifacts are written under:

```text
test_log/runtime/S1_5/exercise/<B51_EXERCISE_ID>/
```

`demo_s1_5_incident_runbook.md` and `demo-snapshot-runtime S1.5 PHASE` remain
available as facilitator aids, but they are not the acceptance path. The
exercise ledger and gates are the path that makes the run participatory and
auditable.

To include the Internet Map in the generated compose output:

```bash
TIER=S1.5 \
  PLATFORM=arm \
  SEED_PYTHON=../../../.venv/bin/python \
  B51_ENABLE_INTERNET_MAP=1 \
  B51_INTERNET_MAP_PORT=8080 \
  bash b51ctl.sh generate-runtime
```

Then open:

```text
http://127.0.0.1:8080/map.html
```

The map is an observation aid and adds a UI container named
`meta-cascade-internet-map` when enabled. It is not part of the BGP/DNS fault
mechanism; the accepted S1.5 runtime gate remains the 225 SEED network
containers.

During a live S1.5 run, `demo-snapshot-runtime S1.5 PHASE` captures presentation
snapshots under `test_log/runtime/S1_5/demo/<phase>/`. For the real exercise,
prefer `exercise-observe-runtime S1.5 ROLE`, because it keeps observations
role-scoped and records them in the operator ledger.

## S2 Safety

S2 is not part of the default runtime ladder. A local 1023-container prototype
exists, but it has not passed runtime acceptance and previously exhausted the
host ARP/neighbor cache on this machine, causing AS50 resolver timeouts. The
controller blocks S2 runtime commands unless both conditions are true:

- `B51_ALLOW_S2_RUNTIME=1` is set by the operator.
- Host neighbor cache thresholds pass preflight:
  `gc_thresh1>=4096`, `gc_thresh2>=8192`, and `gc_thresh3>=65536`.

With the current host defaults (`128/512/1024`), do not run S2 locally. Use a
prepared host, DistributedDocker, or a multi-host runner before trying S2
runtime validation again. `down-runtime S2` remains usable for cleanup.

Two diagnostic commands are safe to run without starting S2:

```bash
bash b51ctl.sh host-diagnose post-s2-cleanup
bash b51ctl.sh s2-preflight
```

`host-diagnose` records Docker, neighbor, bridge/FDB, and recent network dmesg
state under `test_log/host_diagnostics/<label>/`. `s2-preflight` records the
same host snapshot plus S2 readiness under
`test_log/host_diagnostics/S2-preflight/`; it exits non-zero when the host is
not prepared and does not create containers or networks.

## Run The Ordered Runtime Ladder

```bash
cd examples/internet/B51_meta_style_cascade

COMPOSE_PROJECT_NAME=seed_meta_cascade_runtime \
  PLATFORM=arm \
  SEED_PYTHON=../../../.venv/bin/python \
  bash b51ctl.sh runtime-ladder-smoke
```

The ladder runs:

```text
S0 generate -> up -> normal-check -> inject-fault -> fault-check -> collect -> down
S1 generate -> up -> normal-check -> inject-fault -> fault-check -> collect -> down
```

Generated files go under `output/`; smoke artifacts go under `test_log/`.
Both are ignored by the repository.

## Run Human/Agent Intervention

The intervention path exposes a restricted operator/agent surface. The agent can
observe black-box symptoms, route visibility, health-gate state, backend
reachability, and recent change logs. The recovery action only rolls back the
internal path policy fault; external reannouncement is handled by the health
gate after backend health returns.

```bash
cd examples/internet/B51_meta_style_cascade

B51_RUNTIME_LADDER="S1" \
  COMPOSE_PROJECT_NAME=seed_meta_cascade_s1_intervention \
  PLATFORM=arm \
  SEED_PYTHON=../../../.venv/bin/python \
  bash b51ctl.sh runtime-intervention-ladder-smoke
```

The intervention sequence is:

```text
generate -> up -> normal-check -> inject-fault -> fault-check
  -> agent-observe -> recover -> recovery-check -> collect -> down
```

Forbidden actions are rejected by policy, including
`force-announce-unhealthy-prefix`, `disable-health-gate`, `kill-dns`,
`delete-zone`, `client-hosts-bypass`, `edit-oracle`, and `global-reset`.

## Telemetry Fixtures

The old S1/S2 route-view and probe-log generator is kept only as optional
telemetry input for future scorer/replay work:

```bash
SEED_PYTHON=../../../.venv/bin/python bash b51ctl.sh telemetry-smoke
```

This command does not start containers and does not make S1 or S2 pass. The
fixture outputs go under `test_log/telemetry/`.

## Expected Runtime Evidence

Normal state:

- `dig @10.50.0.53 www.meta-bench.test A` returns `10.20.0.80`.
- `curl http://www.meta-bench.test/` returns the edge service page.
- `/var/run/meta-health-status` on the edge router is `healthy`.
- `birdc show route 10.20.0.0/24` shows the route from AS50 and S1 collectors.
- S1 probe routers resolve and reach the service.

Fault state:

- `/var/log/meta-recent-change.log` records the internal BGP policy fault.
- `/var/run/meta-health-status` on the edge router is `unhealthy`.
- AS50 and S1 collectors no longer see `10.20.0.0/24`.
- External `dig` and `curl` fail or time out.
- BIND remains running and DNS zone records remain intact.

## Intervention Model

Human operators can inspect containers directly with Docker. Agent-facing work
uses restricted controller actions and collected artifacts: black-box dig/curl,
BIRD route views, edge-to-backend reachability, health-gate status/logs, and
recent change logs. The policy forbids DNS process kills, zone edits, client
hosts bypass, oracle/scorer edits, and force-announcing an unhealthy prefix.

## Current Limits

This directory covers P0-P5 at first-round depth: S0/S1 runtime cascade,
restricted observation, internal-policy recovery, and recovery validation. S2
runtime is a guarded local prototype only, not an accepted tier. Full scoring
and replay/report packaging remain future work. Until S2 is generated, started,
and normal/fault/recovery checked on a prepared runtime, it is not passed.
