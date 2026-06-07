# S1.5 Incident Demonstration Runbook

This runbook is for a live S1.5 demonstration of the Meta-style cascade. The
point is not to show a known CVE exploit or a toy teaching outage. The point is
to show a networked production failure where different actors see different
partial truths, and the operator must move from symptoms to control-plane and
dependency evidence before repairing anything.

This file is a facilitator aid. It is not the acceptance path for the S1.5 test.
For the participatory exercise contract, staged role permissions, ledger gates,
and command surface, use `interactive_exercise_design.md` and the `exercise-*`
commands in `b51ctl.sh`.

## Demonstration Goal

Show that SEED Emulator can reproduce a complex Internet-scale incident pattern:

```text
internal edge-to-DC reachability loss
  -> edge health gate marks the backend unreachable
  -> edge withdraws the public DNS/service prefix through BGP
  -> recursive resolvers and users see DNS/service failure
  -> operators correlate external feedback, route visibility, health state,
     and recent changes
  -> operators roll back the internal path fault
  -> health gate reannounces only after backend health is restored
```

S1.5 is the largest validated live runtime tier on this host: 225 live
containers, 80 probes, and 16 route collectors. It is the current demonstration
target. S2 remains guarded and is not used in this runbook.

## Actors

| Actor | Runtime viewpoint | What they can see |
|---|---|---|
| Ordinary users | AS50, AS51, AS99, AS132 probes | DNS answer or failure, HTTP success or failure |
| Cloudflare-like recursive resolver | AS50 recursive resolver/client router | Resolver failures, route to Meta edge prefix, direct authoritative reachability |
| External network observers | AS133 and AS148 collectors | BGP visibility of `10.20.0.0/24` |
| Meta NOC | AS20 edge router | health-gate status, edge-to-backend probe, health-gate log, recent change log |
| Meta network engineers | AS20/AS30 BIRD state | BGP peer state, route export state, internal dependency path |
| DC/backend team | AS30 DC router | backend service health and DC-side routing |

## Start With The Map

Generate S1.5 with the Internet Map enabled:

```bash
cd examples/internet/B51_meta_style_cascade

TIER=S1.5 \
  PLATFORM=arm \
  SEED_PYTHON=../../../.venv/bin/python \
  B51_ENABLE_INTERNET_MAP=1 \
  B51_INTERNET_MAP_PORT=8080 \
  bash b51ctl.sh generate-runtime
```

Then start the runtime:

```bash
TIER=S1.5 \
  COMPOSE_PROJECT_NAME=seed_meta_cascade_s1_5_demo \
  PLATFORM=arm \
  B51_ENABLE_INTERNET_MAP=1 \
  B51_INTERNET_MAP_PORT=8080 \
  COMPOSE_PARALLEL_LIMIT=16 \
  bash b51ctl.sh up-runtime
```

Open the Internet Map:

```text
http://127.0.0.1:8080/map.html
```

Use the map to point out:

- AS10: external transit and route-view path.
- AS20: Meta edge DNS/service and health gate.
- AS30: Meta DC/backend dependency.
- AS50: Cloudflare-like resolver and public client.
- AS51-AS99 and AS102-AS132: distributed user probes.
- AS133-AS148: external route collectors.
- AS31-AS46 and AS149-AS254: background-noise networks.
- IX100: external Internet exchange.
- IX101: internal backbone exchange between edge and DC.

The map is an observation aid, not part of the fault mechanism. If map startup
adds the `meta-cascade-internet-map` UI container, the accepted S1.5 runtime
gate still refers to the 225 SEED network containers.

## Time-Ordered Scenario

### T0 Normal State

Run:

```bash
TIER=S1.5 COMPOSE_PROJECT_NAME=seed_meta_cascade_s1_5_demo \
  bash b51ctl.sh normal-runtime S1.5

TIER=S1.5 COMPOSE_PROJECT_NAME=seed_meta_cascade_s1_5_demo \
  bash b51ctl.sh demo-snapshot-runtime S1.5 t0-normal
```

Explain:

- Ordinary users resolve `www.meta-bench.test` to `10.20.0.80`.
- HTTP succeeds.
- Route collectors see `10.20.0.0/24`.
- Meta edge health is `healthy`.
- Edge-to-DC backend reachability works.

Evidence directory:

```text
test_log/runtime/S1_5/demo/t0-normal/
```

Read in this order:

- `10-public-user-as50.txt`
- `11-regional-user-as51.txt`
- `13-enterprise-user-as132.txt`
- `21-route-collector-as133.txt`
- `22-route-collector-as148.txt`
- `30-meta-edge-noc.txt`
- `31-meta-edge-routing.txt`

### T1 Fault Happens

Inject the benchmark fault:

```bash
TIER=S1.5 COMPOSE_PROJECT_NAME=seed_meta_cascade_s1_5_demo \
  bash b51ctl.sh inject-fault-runtime S1.5
```

Narration:

- Do not say the root cause immediately.
- Treat this as a recent internal routing or policy change.
- The audience should first see symptoms from users and external networks.

### T2 User And Cloudflare-Like Feedback

Run:

```bash
TIER=S1.5 COMPOSE_PROJECT_NAME=seed_meta_cascade_s1_5_demo \
  bash b51ctl.sh demo-snapshot-runtime S1.5 t2-user-feedback
```

Explain:

- Some user classes report the service is down.
- The Cloudflare-like resolver sees DNS failure or authoritative reachability
  failure.
- This does not yet prove that DNS software was killed.
- It also does not prove the backend service itself is down.

Read:

- `10-public-user-as50.txt`
- `11-regional-user-as51.txt`
- `12-mobile-user-as99.txt`
- `13-enterprise-user-as132.txt`
- `20-cloudflare-like-resolver-as50.txt`

Expected fault symptoms:

- `SERVFAIL`, timeout, or no A answer from resolver-side DNS checks.
- HTTP request fails because the domain cannot be resolved or reached.

### T3 External Network Evidence

Run the formal fault check:

```bash
TIER=S1.5 COMPOSE_PROJECT_NAME=seed_meta_cascade_s1_5_demo \
  bash b51ctl.sh fault-runtime S1.5
```

Then inspect the same snapshot:

```bash
TIER=S1.5 COMPOSE_PROJECT_NAME=seed_meta_cascade_s1_5_demo \
  bash b51ctl.sh demo-snapshot-runtime S1.5 t3-external-routes
```

Explain:

- Route collectors no longer see `10.20.0.0/24`.
- That points toward a BGP/control-plane withdrawal of the edge prefix.
- Because many independent probes and collectors agree, this is not a single
  user host issue.

Read:

- `21-route-collector-as133.txt`
- `22-route-collector-as148.txt`
- `20-cloudflare-like-resolver-as50.txt`

Expected route symptom:

```text
Network not found
```

### T4 Meta Internal Triage

Run:

```bash
TIER=S1.5 COMPOSE_PROJECT_NAME=seed_meta_cascade_s1_5_demo \
  bash b51ctl.sh agent-observe-runtime S1.5
```

Also read:

```text
test_log/runtime/S1_5/demo/t3-external-routes/30-meta-edge-noc.txt
test_log/runtime/S1_5/demo/t3-external-routes/31-meta-edge-routing.txt
test_log/runtime/S1_5/demo/t3-external-routes/32-meta-dc-backend.txt
test_log/runtime/S1_5/agent_blackbox_dig.txt
test_log/runtime/S1_5/agent_route_view.txt
test_log/runtime/S1_5/agent_health_status.txt
test_log/runtime/S1_5/agent_edge_to_backend.txt
test_log/runtime/S1_5/agent_recent_change_tail.txt
```

Explain the reasoning ladder:

1. User DNS/HTTP is failing.
2. External collectors do not see the edge prefix.
3. Edge health gate says `unhealthy`.
4. Edge cannot reach the backend dependency.
5. Recent changes show an internal path policy change.
6. Therefore the best first mitigation is to roll back the internal path
   policy fault, not to kill DNS, edit zone files, bypass client DNS, or force
   announce an unhealthy prefix.

### T5 Recovery

Run the restricted recovery:

```bash
TIER=S1.5 COMPOSE_PROJECT_NAME=seed_meta_cascade_s1_5_demo \
  bash b51ctl.sh recover-runtime S1.5
```

Explain:

- The recovery action clears the internal path fault.
- The operator does not directly force public prefix announcement.
- The health gate reannounces only after it verifies backend health.

Important artifacts:

```text
test_log/runtime/S1_5/agent_action_rollback-internal-policy.txt
test_log/runtime/S1_5/agent_action_verify-health.txt
test_log/runtime/S1_5/agent_action_canary-reannounce.txt
```

### T6 Verification

Run:

```bash
TIER=S1.5 COMPOSE_PROJECT_NAME=seed_meta_cascade_s1_5_demo \
  bash b51ctl.sh recovery-runtime S1.5

TIER=S1.5 COMPOSE_PROJECT_NAME=seed_meta_cascade_s1_5_demo \
  bash b51ctl.sh demo-snapshot-runtime S1.5 t6-recovered
```

Explain:

- Users again resolve `www.meta-bench.test` to `10.20.0.80`.
- HTTP succeeds again.
- AS133 and AS148 see `10.20.0.0/24` again.
- Meta edge health is `healthy`.
- The backend dependency is reachable.

Read:

- `10-public-user-as50.txt`
- `13-enterprise-user-as132.txt`
- `21-route-collector-as133.txt`
- `22-route-collector-as148.txt`
- `30-meta-edge-noc.txt`

### T7 Collect And Stop

Run:

```bash
TIER=S1.5 COMPOSE_PROJECT_NAME=seed_meta_cascade_s1_5_demo \
  bash b51ctl.sh collect-runtime S1.5

TIER=S1.5 COMPOSE_PROJECT_NAME=seed_meta_cascade_s1_5_demo \
  bash b51ctl.sh down-runtime S1.5
```

Confirm cleanup:

```bash
docker ps -a --filter label=com.docker.compose.project=seed_meta_cascade_s1_5_demo --format '{{.Names}}'
docker network ls --filter name=seed_meta_cascade_s1_5_demo --format '{{.Name}}'
```

## Why This Is Different From A Teaching CVE Scenario

This scenario is not centered on one vulnerable binary or a single exploit
string. The interesting part is the dependency chain:

- application name resolution depends on public reachability to the edge
  authoritative DNS prefix;
- public reachability depends on BGP export from the edge;
- BGP export depends on health-gate policy;
- health-gate policy depends on internal edge-to-DC reachability;
- the correct fix depends on distinguishing DNS symptoms from routing and
  dependency causes.

That makes the case useful for demonstrating SEED Emulator as a platform for
agent-oriented network operations, even before a formal agent benchmark scorer
is added.
