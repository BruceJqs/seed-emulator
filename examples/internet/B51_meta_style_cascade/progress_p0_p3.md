# P0-P3 Progress Note

## Completed in This Round

- P0 repo alignment note: `design_notes/repo_alignment.md`.
- P1 case skeleton: metadata, agent policy, scoring stub, README, generator,
  and controller.
- P2 normal-state target: external resolver/client, edge authoritative DNS,
  edge service, backend dependency, health gate, and route view.
- P3 fault target: internal BGP path policy fault, health-gated external BGP
  withdrawal, and black-box DNS/service failure checks.
- Controller smoke lifecycle: `smoke` now generates, starts, checks, collects,
  and stops the compose project; on failure it still attempts `collect` and
  `down`.
- Runtime scale wording was corrected after review: `scale-smoke` is disabled
  as ambiguous, `runtime-ladder-smoke` is the live S0->S1 command, and
  `telemetry-smoke` is explicitly non-acceptance fixture generation.
- Follow-up P4-P5 first-round intervention support now exists: restricted
  `agent-observe`, policy-limited `agent-act`, internal-policy recovery, and
  recovery validation.

## Validation Commands

```bash
cd examples/internet/B51_meta_style_cascade
SEED_PYTHON=../../../.venv/bin/python bash b51ctl.sh generate
../../../.venv/bin/python -m py_compile meta_style_cascade.py
bash -n b51ctl.sh
bash -n ../../../tests/internet/meta_style_cascade/smoke.sh
COMPOSE_PROJECT_NAME=seed_meta_cascade_s0 \
  PLATFORM=arm \
  SEED_PYTHON=../../../.venv/bin/python \
  bash b51ctl.sh smoke

# Equivalent manual runtime path:
COMPOSE_PROJECT_NAME=seed_meta_cascade_s0 PLATFORM=arm bash b51ctl.sh up
COMPOSE_PROJECT_NAME=seed_meta_cascade_s0 PLATFORM=arm bash b51ctl.sh normal-check
COMPOSE_PROJECT_NAME=seed_meta_cascade_s0 PLATFORM=arm bash b51ctl.sh inject-fault
COMPOSE_PROJECT_NAME=seed_meta_cascade_s0 PLATFORM=arm bash b51ctl.sh fault-check
COMPOSE_PROJECT_NAME=seed_meta_cascade_s0 PLATFORM=arm bash b51ctl.sh collect
COMPOSE_PROJECT_NAME=seed_meta_cascade_s0 PLATFORM=arm bash b51ctl.sh down
```

## Validation Results

Completed:

- `SEED_PYTHON=../../../.venv/bin/python bash b51ctl.sh generate` succeeded and
  produced `output/docker-compose.yml`.
- `SEED_PYTHON=../../../.venv/bin/python PLATFORM=arm bash b51ctl.sh generate`
  succeeded and generated the local multiarch service-router image path
  `../router-service-image-arm`.
- `.venv/bin/python -m py_compile examples/internet/B51_meta_style_cascade/meta_style_cascade.py`
  succeeded.
- `bash -n examples/internet/B51_meta_style_cascade/b51ctl.sh` and
  `bash -n tests/internet/meta_style_cascade/smoke.sh` succeeded.
- Static forbidden-shortcut scan over the generator/controller/smoke scripts
  had no matches for DNS kill, DNS record deletion, client hosts bypass, oracle
  edits, or force-announce shortcuts.
- Generated output contains the expected BIRD and DNS evidence:
  `protocol bgp u_as10`, `protocol bgp c_as30`, authoritative zone
  `meta-bench.test.`, resolver forwarder `10.20.0.53`, and installed
  health/fault scripts.
- `COMPOSE_PROJECT_NAME=seed_meta_cascade_s0 PLATFORM=arm SEED_PYTHON=../../../.venv/bin/python bash b51ctl.sh smoke`
  succeeded on 2026-06-03. The command generated output, built the local
  service-router image, started the compose project, ran `normal-check`,
  injected the internal path fault, ran `fault-check`, collected artifacts, and
  stopped the compose project.
- Normal artifacts show:
  - `normal_dig.txt`: `10.20.0.80`
  - `normal_curl.txt`: `meta-style edge entry reachable from edge-router in AS20`
  - `normal_route.txt`: `10.20.0.0/24 ... via 10.100.0.10 on ix100`
  - `normal_edge_to_backend.txt`: backend HTTP response from AS30.
- Fault artifacts show:
  - `fault_recent_change.log`: `inject internal path policy fault: disabled BGP peer c_as30`
  - `fault_health_gate.log`: `state=unhealthy backend_reachable=false action=withdraw_external_peer`
  - `fault_route.txt`: `Network not found`
  - `fault_dig.txt`: `status: SERVFAIL`
  - `fault_curl.txt`: `curl: (6) Could not resolve host: www.meta-bench.test`
  - `health_status.txt`: `unhealthy`

Blocked:

- No P0-P3 runtime blocker remains after using the local `PLATFORM=arm` image
  path.

## Risks and Remaining Work

- The current smoke path uses `docker-compose` and Docker CLI instead of
  `SeedEmuTestCase`; a local `.venv` was created for declared Python
  dependencies needed by generation, but importing the Python Docker SDK fails
  under Python 3.12 because `distutils` is missing.
- The default AMD image path may still require Docker Hub access on systems
  without `handsonsecurity/seedemu-router:2.0` locally available. The validated
  local smoke used `PLATFORM=arm`.
- P4-P5 now have a first-round runtime path; P6 scorer and replay/report
  artifact format remain to be built.
- BGP route-view checks use `birdc`; the heavier BGP looking glass service is
  intentionally not used in P0-P3.
