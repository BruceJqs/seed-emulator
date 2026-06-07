# Runtime Scale Correction Note

## Correction

The earlier wording mixed runtime scale with generated telemetry fixtures. That
was wrong. From this revision onward:

- A runtime tier is passed only by live SEED Docker containers.
- Telemetry fixtures are not S1/S2 runtime acceptance.
- S2 is not passed in this round.

## Implemented Runtime Tiers

| Tier | Runtime status | Live container gate | Probe routers | Collector routers | Artifact directory |
|---|---|---:|---|---|---|
| S0 | implemented | >=7 | AS50 client/resolver | AS50 route view | `test_log/runtime/S0/` |
| S1 | implemented | >=129 | AS51-AS90 | AS110-AS121 | `test_log/runtime/S1/` |
| S2 | local prototype guarded and paused | not passed | AS300-AS659 | AS700-AS711 | none accepted |

`b51ctl.sh normal-check` now records and validates the live container count for
the selected runtime tier. `scale-smoke` is disabled because the name was
ambiguous; `runtime-ladder-smoke` is the live ordered scale command.

## Prior S1 Runtime Evidence

The current S1 implementation was run on 2026-06-03 with:

```bash
TIER=S1 COMPOSE_PROJECT_NAME=seed_meta_cascade_s1_hundred \
  PLATFORM=arm SEED_PYTHON=../../../.venv/bin/python bash b51ctl.sh generate

TIER=S1 COMPOSE_PROJECT_NAME=seed_meta_cascade_s1_hundred \
  PLATFORM=arm SEED_PYTHON=../../../.venv/bin/python bash b51ctl.sh up

TIER=S1 COMPOSE_PROJECT_NAME=seed_meta_cascade_s1_hundred \
  PLATFORM=arm SEED_PYTHON=../../../.venv/bin/python bash b51ctl.sh normal-check

TIER=S1 COMPOSE_PROJECT_NAME=seed_meta_cascade_s1_hundred \
  PLATFORM=arm SEED_PYTHON=../../../.venv/bin/python bash b51ctl.sh inject-fault

TIER=S1 COMPOSE_PROJECT_NAME=seed_meta_cascade_s1_hundred \
  PLATFORM=arm SEED_PYTHON=../../../.venv/bin/python bash b51ctl.sh fault-check
```

Observed evidence from that run:

- live S1 container count: `129`.
- normal-check passed across all 12 route collectors and all 40 probes.
- fault-check passed across all 12 route collectors and all 40 probes.
- fault state on edge: `health=unhealthy`, `u_as10 down`, `c_as30 down`.
- AS110 and AS121 collectors: `Network not found` for `10.20.0.0/24`.
- AS51 and AS90 probes: DNS `SERVFAIL`, curl `Could not resolve host`.
- BIND stayed running and the `meta-bench.test` zone file still contained the
  service records, proving the failure was not a DNS kill or zone deletion.

This evidence does not claim S2 runtime success.

## Telemetry Fixtures

The old generated S1/S2 files are now documented as optional telemetry fixtures
under:

```text
examples/internet/B51_meta_style_cascade/test_log/telemetry/S1/
examples/internet/B51_meta_style_cascade/test_log/telemetry/S2/
```

They may be useful for later scorer/replay design, but they are not runtime
scale gates.

## 2026-06-04 Redesign Validation

Commands run after the scale-semantics redesign:

```bash
../../../.venv/bin/python -m py_compile meta_style_cascade.py scale_background.py
bash -n b51ctl.sh
bash -n ../../../tests/internet/meta_style_cascade/smoke.sh
bash -n ../../../tests/internet/meta_style_cascade/scale_smoke.sh
bash -n ../../../tests/internet/meta_style_cascade/full_sequence.sh
../../../.venv/bin/python -m json.tool case_metadata.json
../../../.venv/bin/python -m json.tool scale_tiers.json
../../../.venv/bin/python -m json.tool agent_policy.json
../../../.venv/bin/python -m json.tool scoring_stub.json
SEED_PYTHON=../../../.venv/bin/python bash b51ctl.sh scale-smoke
TIER=S2 SEED_PYTHON=../../../.venv/bin/python bash b51ctl.sh generate-runtime
SEED_PYTHON=../../../.venv/bin/python bash b51ctl.sh telemetry-smoke
TIER=S0 COMPOSE_PROJECT_NAME=seed_meta_cascade_redesign_s0 \
  PLATFORM=arm SEED_PYTHON=../../../.venv/bin/python bash b51ctl.sh smoke
```

Observed:

- `scale-smoke` exited non-zero and told the operator to choose
  `runtime-ladder-smoke` or `telemetry-smoke`.
- `TIER=S2 ... generate-runtime` exited non-zero and did not accept S2 runtime.
- `telemetry-smoke` generated and verified S1/S2 fixtures while explicitly
  logging that no runtime tier was accepted.
- S1 runtime generation succeeded before the S0 smoke; generated compose
  inspection found 129 `container_name` entries, 40 S1 probe routers, 12 S1
  collectors, and 70 S1 noise routers.
- S0 runtime smoke passed with live container gate `7 >= 7`, normal DNS result
  `10.20.0.80`, fault route view `Network not found`, fault DNS `SERVFAIL`,
  and fault curl `Could not resolve host`.
- Post-smoke Docker cleanup check found no `b51-` or `seed_meta_cascade*`
  containers or networks.

## 2026-06-04 S1 Runtime Startup Validation

After the user requested real startup validation, S1 was started and checked as
live runtime, then rerun after fixing artifact directory hygiene:

```bash
B51_RUNTIME_LADDER=S1 TIER=S1 \
  COMPOSE_PROJECT_NAME=seed_meta_cascade_redesign_s1_clean \
  PLATFORM=arm SEED_PYTHON=../../../.venv/bin/python \
  bash b51ctl.sh runtime-ladder-smoke
```

Observed from the clean run:

- live S1 container gate passed: `live_containers=129`,
  `minimum_required=129`.
- normal S1 probe artifacts: 40 files, AS51 sample `10.20.0.80`.
- normal S1 collector artifacts: 12 files, AS110 saw
  `10.20.0.0/24 ... [AS20i] via 10.100.0.10 on ix100`.
- fault injection log:
  `inject internal path policy fault: disabled BGP peer c_as30`.
- health gate log:
  `state=unhealthy backend_reachable=false action=withdraw_external_peer`.
- fault S1 route collector artifacts: 12 files, AS121 sample
  `Network not found`.
- fault S1 probe artifacts: 40 files, AS90 curl sample
  `Could not resolve host: www.meta-bench.test`.
- post-run Docker cleanup check found no `b51-`,
  `seed_meta_cascade_redesign_s1`, or
  `seed_meta_cascade_redesign_s1_clean` containers or networks.

The controller now clears `test_log/runtime/<tier>/` at the start of each
runtime tier smoke so stale artifacts cannot be counted as fresh evidence.

## 2026-06-04 Ordered S0-to-S1 Runtime Ladder Validation

The ordered live runtime ladder was then run from S0 into S1 with one command:

```bash
COMPOSE_PROJECT_NAME=seed_meta_cascade_redesign_ladder \
  PLATFORM=arm \
  SEED_PYTHON=../../../.venv/bin/python \
  bash b51ctl.sh runtime-ladder-smoke
```

Observed:

- command exited 0 with `runtime-ladder-smoke passed`.
- S0 started, passed normal-check, injected the internal policy fault, passed
  fault-check, collected artifacts, and shut down before S1 started.
- S0 live gate artifact: `live_containers=7`, `minimum_required=7`.
- S1 then started, passed normal-check across all 12 collectors and 40 probes,
  injected the internal policy fault, passed fault-check across all 12
  collectors and 40 probes, collected artifacts, and shut down.
- S1 live gate artifact: `live_containers=129`, `minimum_required=129`.
- S1 normal artifact counts: 40 probe DNS files and 12 route collector files.
- S1 fault artifact counts: 40 probe curl files and 12 route collector files.
- S1 normal examples: AS51 `dig` returned `10.20.0.80`; AS110 saw
  `10.20.0.0/24 ... [AS20i] via 10.100.0.10 on ix100`.
- S1 fault examples: injection disabled BGP peer `c_as30`; health gate logged
  `state=unhealthy backend_reachable=false action=withdraw_external_peer`;
  AS121 saw `Network not found`; AS90 curl reported
  `Could not resolve host: www.meta-bench.test`.
- post-ladder Docker cleanup checks found no
  `seed_meta_cascade_redesign_ladder` or `b51-` containers or networks.

This is the first ordered S0-to-S1 runtime evidence. It still does not claim S2
runtime success.

## 2026-06-04 S1 Restricted Intervention Validation

After adding the restricted human/agent intervention surface, S1 was run as a
live recovery scenario:

```bash
B51_RUNTIME_LADDER=S1 TIER=S1 \
  COMPOSE_PROJECT_NAME=seed_meta_cascade_s1_intervention \
  PLATFORM=arm SEED_PYTHON=../../../.venv/bin/python \
  bash b51ctl.sh runtime-intervention-ladder-smoke
```

Observed:

- command exited 0 with `runtime-intervention-ladder-smoke passed`.
- S1 live gate artifact: `live_containers=129`, `minimum_required=129`.
- normal-check passed across all 12 collectors and 40 probes.
- fault-check passed across all 12 collectors and 40 probes.
- agent observation after fault showed DNS `SERVFAIL`, route view
  `Network not found`, health status `unhealthy`, and edge-to-backend
  `Couldn't connect to server`.
- forbidden action check rejected `force-announce-unhealthy-prefix` with
  `result=denied`.
- recovery action only cleared the internal path policy fault:
  `c_as30: enabled`.
- health verification then showed `health=healthy` and the backend HTTP
  response.
- health-gate-managed canary route visibility returned after two initial
  `Network not found` samples, then showed
  `10.20.0.0/24 ... [AS20i] via 10.100.0.10 on ix100`.
- recovery-check passed across all 12 collectors and 40 probes.
- recovery artifact counts: 40 recovered probe DNS files and 12 recovered route
  collector files.
- AS90 recovered DNS sample returned `10.20.0.80`; AS121 recovered route sample
  saw the prefix via `10.100.0.10`.
- health gate timeline showed
  `state=unhealthy ... action=withdraw_external_peer`, followed by
  `state=healthy ... action=announce_external_peer`.
- recent-change timeline showed the injected `c_as30` disable followed by the
  recovery `c_as30` enable.
- post-run Docker cleanup checks found no
  `seed_meta_cascade_s1_intervention` or `b51-` containers or networks.

This validates first-round P4-P5 behavior for S1. It still does not claim S2
runtime success.

## 2026-06-04 S2 Local Runtime Pause And Environment Cleanup

After a real S2 local runtime attempt, S2 was stopped and paused. This is not an
accepted S2 result.

Observed S2 runtime failure mode:

- The S2 local prototype reached 1023 live Docker containers.
- AS20 health gate stayed healthy and AS20 could reach the backend.
- AS10 could ping, curl, and dig AS20 service IPs.
- AS50 still had a route toward `10.20.0.0/24`, but AS50 could not reach
  `10.20.0.53` or `10.20.0.80`.
- Host/container diagnostics showed repeated
  `neighbour: arp_cache: neighbor table overflow!`.

The practical root cause for this host is ARP/neighbor-cache exhaustion under
the local 1023-container runtime, not DNS process failure, DNS zone deletion,
client host bypass, or scorer/oracle edits.

Cleanup and host state checks:

```bash
docker ps -a --filter label=com.docker.compose.project=seed_meta_cascade_s2_runtime --format '{{.Names}}'
docker ps -a --filter name=b51- --format '{{.Names}}'
docker network ls --filter label=com.docker.compose.project=seed_meta_cascade_s2_runtime --format '{{.Name}}'
docker volume ls --filter label=com.docker.compose.project=seed_meta_cascade_s2_runtime --format '{{.Name}}'
sysctl -n net.ipv4.neigh.default.gc_thresh1 net.ipv4.neigh.default.gc_thresh2 net.ipv4.neigh.default.gc_thresh3
```

Observed:

- S2 compose containers: `0`.
- Any `b51-*` containers: `0`.
- S2 compose networks: `0`.
- S2 compose volumes: `0`.
- Host neighbor thresholds: `128`, `512`, `1024`.

Guard added:

- S2 is no longer part of the default ladder; default remains `S0 S1`.
- S2 runtime commands require `B51_ALLOW_S2_RUNTIME=1`.
- Even with that flag, S2 is blocked unless host neighbor thresholds are at
  least `gc_thresh1>=4096`, `gc_thresh2>=8192`, and `gc_thresh3>=65536`.
- The guard covers generate, up, normal/fault checks, injection, restricted
  observe/action, recovery, and recovery checks. `down-runtime S2` remains
  available for cleanup.

Validation after adding the guard:

```bash
bash -n b51ctl.sh
../../../.venv/bin/python -m py_compile meta_style_cascade.py scale_background.py
../../../.venv/bin/python -m json.tool case_metadata.json
TIER=S2 PLATFORM=arm SEED_PYTHON=../../../.venv/bin/python bash b51ctl.sh generate-runtime
B51_ALLOW_S2_RUNTIME=1 TIER=S2 PLATFORM=arm SEED_PYTHON=../../../.venv/bin/python bash b51ctl.sh generate-runtime
TIER=S2 PLATFORM=arm SEED_PYTHON=../../../.venv/bin/python bash b51ctl.sh agent-observe-runtime
TIER=S2 PLATFORM=arm SEED_PYTHON=../../../.venv/bin/python bash b51ctl.sh agent-act-runtime verify-health
B51_ALLOW_S2_RUNTIME=1 TIER=S2 PLATFORM=arm SEED_PYTHON=../../../.venv/bin/python bash b51ctl.sh agent-act-runtime verify-health
TIER=S0 COMPOSE_PROJECT_NAME=seed_meta_cascade_envcheck_s0 PLATFORM=arm SEED_PYTHON=../../../.venv/bin/python bash b51ctl.sh smoke
```

Observed:

- Syntax, JSON, and Python compile checks passed.
- S2 `generate-runtime` without `B51_ALLOW_S2_RUNTIME=1` exited `2` before
  generation and printed the disabled-by-default warning.
- S2 `generate-runtime` with `B51_ALLOW_S2_RUNTIME=1` exited `2` before
  generation because this host still reports `gc_thresh1=128`,
  `gc_thresh2=512`, and `gc_thresh3=1024`.
- Direct S2 restricted observation/action runtime entries are also blocked by
  the same preflight.
- S0 smoke still passed after the guard: live gate `7 >= 7`, normal route
  visibility for `10.20.0.0/24`, normal DNS answer `10.20.0.80`, fault route
  withdrawal `Network not found`, and fault DNS/service checks passed.
- Post-smoke cleanup found no `seed_meta_cascade_envcheck_s0`,
  `seed_meta_cascade_s2_runtime`, or `b51-*` containers or networks.

## 2026-06-04 S2 Diagnostic-Only Follow-Up

To avoid another accidental S2 restart, the controller gained diagnostic-only
commands that do not start containers:

```bash
bash b51ctl.sh host-diagnose post-s2-cleanup
bash b51ctl.sh s2-preflight
```

Observed:

- `host-diagnose post-s2-cleanup` exited `0` and wrote
  `test_log/host_diagnostics/post-s2-cleanup/`.
- `s2-preflight` exited `2`, as expected on this host, and wrote
  `test_log/host_diagnostics/S2-preflight/`.
- `s2-preflight` reported `starts_containers=false`,
  `s2_runtime_enabled=0`, observed thresholds `128/512/1024`, required
  thresholds `4096/8192/65536`, and two blockers:
  `B51_ALLOW_S2_RUNTIME is not set` plus neighbor cache thresholds below
  minimums.
- The host cleanup snapshot reported `containers=0`, `running_containers=0`,
  `networks=3`, `compose_project_containers=0`, `b51_named_containers=0`,
  host neighbor count `1`, and bridge FDB count `15`.
- The diagnostic tail still contains S2 cleanup-era bridge/veth activity. The
  earlier kernel evidence includes `neighbour: arp_cache: neighbor table
  overflow!`, so future S2 attempts must collect host diagnostics before and
  after startup on a prepared host.

This follow-up did not run S2 and does not change S2 acceptance status.

## 2026-06-05 S1.5 Full Intervention Runtime Validation

S1.5 was added as an intermediate live runtime tier between S1 and the guarded
S2 prototype. It is not a telemetry fixture and not an S2 substitute; it starts
real SEED Docker containers and runs the full normal/fault/recovery path.

Commands run:

```bash
TIER=S1.5 PLATFORM=arm SEED_PYTHON=../../../.venv/bin/python \
  bash b51ctl.sh generate-runtime

TIER=S1.5 B51_RUNTIME_LADDER=S1.5 \
  COMPOSE_PROJECT_NAME=seed_meta_cascade_s1_5_full \
  PLATFORM=arm SEED_PYTHON=../../../.venv/bin/python \
  COMPOSE_PARALLEL_LIMIT=16 \
  bash b51ctl.sh runtime-intervention-tier-smoke S1.5

TIER=S1.5 COMPOSE_PROJECT_NAME=seed_meta_cascade_s1_5_full \
  bash b51ctl.sh host-diagnose after-s1_5
```

Observed:

- generated runtime tier marker: `S1_5`.
- generated compose container entries: `225`.
- live S1.5 container gate passed:
  `live_containers=225`, `minimum_required=225`.
- normal-check passed across 16 collectors and 80 probes.
- normal artifact counts: 80 probe DNS files and 16 route collector files.
- AS51 and AS132 normal DNS samples returned `10.20.0.80`.
- AS133 and AS148 normal collector samples saw
  `10.20.0.0/24 ... [AS20i] via 10.100.0.10 on ix100`.
- fault injection disabled the internal BGP peer:
  `inject internal path policy fault: disabled BGP peer c_as30`.
- health gate withdrew only through the BGP control plane:
  `state=unhealthy backend_reachable=false action=withdraw_external_peer`.
- fault-check passed across 16 collectors and 80 probes.
- fault artifact counts: 80 failed probe curl files and 16 withdrawn route
  collector files.
- AS148 fault collector sample reported `Network not found`.
- AS132 fault curl sample reported
  `Could not resolve host: www.meta-bench.test`.
- restricted agent observation after fault showed DNS `SERVFAIL`, route view
  `Network not found`, health status `unhealthy`, and failed service access.
- restricted recovery only cleared the internal path policy fault:
  `c_as30: enabled`.
- health verification returned `health=healthy` and the backend dependency
  response.
- canary reannounce first saw `Network not found`, then saw
  `10.20.0.0/24 ... [AS20i] via 10.100.0.10 on ix100`.
- recovery-check passed across 16 collectors and 80 probes.
- recovery artifact counts: 80 recovered probe DNS files and 16 recovered route
  collector files.
- AS132 recovered DNS sample returned `10.20.0.80`; AS148 recovered collector
  sample saw the edge prefix via IX100.
- post-run cleanup diagnostics reported `containers=0`,
  `running_containers=0`, `compose_project_containers=0`,
  `b51_named_containers=0`, host neighbor count `1`, and bridge FDB count `15`.
- fresh S2 preflight after the S1.5 run remained diagnostic-only
  (`starts_containers=false`) and blocked on `B51_ALLOW_S2_RUNTIME` not being
  set plus neighbor cache thresholds `128/512/1024` below `4096/8192/65536`.

S1.5 is now the largest validated live runtime tier on this host. S2 remains
guarded and not accepted because the earlier 1023-container attempt exhausted
the host neighbor cache and current thresholds remain `128/512/1024`.

## 2026-06-05 S1.5 Incident Demonstration Packaging

After the live S1.5 validation, the case gained presentation-focused support for
showing the scenario as a time-ordered incident rather than as a benchmark
smoke log.

Added:

- `demo_s1_5_incident_runbook.md`, a role-based incident walkthrough covering
  normal state, user and Cloudflare-like resolver feedback, external route
  collector evidence, Meta edge/DC triage, restricted recovery, and final
  validation.
- optional Internet Map generation controlled by `B51_ENABLE_INTERNET_MAP=1`
  and `B51_INTERNET_MAP_PORT`.
- a `demo-snapshot-runtime S1.5 PHASE` command that collects role-oriented
  observations under `test_log/runtime/S1_5/demo/<phase>/`.

Checks run:

```bash
bash -n b51ctl.sh
../../../.venv/bin/python -m py_compile meta_style_cascade.py scale_background.py
B51_ENABLE_INTERNET_MAP=1 B51_INTERNET_MAP_PORT=8080 \
  TIER=S1.5 PLATFORM=arm SEED_PYTHON=../../../.venv/bin/python \
  bash b51ctl.sh generate-runtime
```

Observed from the generated compose output:

- `225` `b51-` runtime container entries remain the S1.5 topology container
  count.
- the Internet Map is a separate `meta-cascade-internet-map` UI container.
- total compose `container_name` entries are `226` when the map is enabled.
- the map port is `8080:8080/tcp`.

This packaging step did not start S1.5 containers and did not run S2.

## 2026-06-06 S1.5 Interactive Exercise Redesign

The S1.5 test definition was corrected from a result-oriented demonstration to
a participatory incident exercise. The important distinction is that the case
now has an operator ledger and staged phase gates; a final normal/fault/recovery
result is not enough to accept the exercise.

Added or updated:

- `interactive_exercise_design.md`, defining the exercise semantics, roles,
  phases, evidence gates, wrong hypotheses, forbidden shortcuts, and S2
  boundary.
- `b51ctl.sh` interactive commands:
  `exercise-init`, `exercise-phase`, `exercise-note`, `exercise-status`,
  `exercise-observe`, `exercise-action`, and `exercise-gate`, with runtime
  variants.
- `exercise-observe` and `exercise-action` now require the S1.5 live container
  gate before collecting evidence or changing the network. This prevents
  no-container fake observations.
- `exercise-gate` checks ledger completeness for phases such as `baseline`,
  `resolver-triage`, `external-routing`, `meta-triage`, `neteng-triage`,
  `change-audit`, `mitigation`, and `recovery-verification`.
- `README.md`, `case_metadata.json`, `agent_policy.json`, and
  `tests/internet/meta_style_cascade/README.md` now describe the exercise path
  as separate from smoke-test acceptance.
- `tests/internet/meta_style_cascade/exercise_static.sh` provides a non-runtime
  static ledger check for exercise command wiring and invalid input rejection.

This redesign did not start S1.5 containers and did not run S2. The previously
validated live S1.5 runtime evidence remains the latest live execution evidence
until the full interactive exercise is run end to end.

## 2026-06-06 Final Case Closeout

The Meta-style case was closed for handoff so the next benchmark cases can
start from a clean boundary.

Added:

- `HANDOFF.md`, the case-local closure document with the completed scope,
  runtime commands, S1.5 exercise entry point, recorded evidence, S2 guard, and
  closeout checklist.

Fixes made during closeout:

- `exercise-action` now records a failed live-runtime preflight in the action
  ledger instead of losing the result when an allowed action is attempted
  without S1.5 containers.
- `tests/internet/meta_style_cascade/exercise_static.sh` now checks that:
  - missing observations keep the baseline gate from passing;
  - invalid roles are rejected;
  - invalid actions return usage error;
  - forbidden actions reach the policy-deny path;
  - allowed live actions attempted without S1.5 runtime fail and still leave an
    action result ledger.

Closeout checks run:

```bash
bash -n examples/internet/B51_meta_style_cascade/b51ctl.sh \
  tests/internet/meta_style_cascade/exercise_static.sh \
  tests/internet/meta_style_cascade/full_sequence.sh \
  tests/internet/meta_style_cascade/intervention_smoke.sh \
  tests/internet/meta_style_cascade/smoke.sh \
  tests/internet/meta_style_cascade/scale_smoke.sh

cd examples/internet/B51_meta_style_cascade
../../../.venv/bin/python -m py_compile meta_style_cascade.py scale_background.py

python3 -m json.tool examples/internet/B51_meta_style_cascade/agent_policy.json
python3 -m json.tool examples/internet/B51_meta_style_cascade/case_metadata.json
python3 -m json.tool examples/internet/B51_meta_style_cascade/scale_tiers.json
python3 -m json.tool examples/internet/B51_meta_style_cascade/scoring_stub.json

tests/internet/meta_style_cascade/exercise_static.sh
bash b51ctl.sh s2-preflight
```

Observed:

- shell syntax checks passed;
- Python compile checks passed;
- all JSON metadata/policy/scoring files parsed;
- `exercise_static.sh` exited 0 with
  `exercise static ledger check passed`;
- S2 preflight exited blocked with `starts_containers=false`,
  `s2_runtime_enabled=0`, thresholds `128/512/1024`, and required thresholds
  `4096/8192/65536`;
- Docker cleanup checks found no `b51-`, `seed_meta_cascade_s1_5_full`, or
  `seed_meta_cascade_exercise_static` containers.

`git add -n examples/internet/B51_meta_style_cascade
tests/internet/meta_style_cascade design_notes` showed only source, docs,
metadata, policy, scoring, and test entry files. Ignored `output/`, `test_log/`,
and `__pycache__/` paths were not included. The input goal-pack directories
remain untracked and outside the closeout commit scope.

## Remaining Runtime Work

- Move S2 to a prepared host or distributed runtime and rerun live
  normal/fault/recovery checks before claiming S2.
- Add conflict-aware IPAM before scaling beyond the current fixed subnet plan.
- Add DistributedDocker/multi-host support if a single Docker host cannot start
  the target container count.
- Extend the first-round P4-P5 policy/recovery surface into a full P6 scorer,
  replay, and report format.
