# Runbook: BGP Route Leak Benchmark

This is the operator runbook for the mission-ready implementation. It
intentionally avoids hardcoded container names; resolve them from runtime
inventory.

Agent-facing task card:

```text
codex_task.md
```

Mission export:

```text
../../agent-missions/tasks/TS_B00_ROUTE_LEAK_OPTIMIZER_LIVE.yaml
../../agent-missions/playbooks/ts_b00_route_leak_optimizer_live.yaml
```

## 1. Prepare Runtime

Generate and start a B00 or B30-derived mini Internet with one compose project
name. Keep only one benchmark runtime active while testing this package.

Required visible surfaces:

- runtime inventory
- BGP route summary
- client probe shell or SeedOps probe
- route daemon logs
- replay output directory

## 2. Baseline

Collect:

- route to `10.150.0.0/24` from AS2 and client vantage
- client reachability to AS150 target host or service
- traceroute from client vantage
- selected daemon logs around convergence

Write artifacts:

```text
replay/route_summary.before.json
replay/client_probe.before.json
replay/traceroute.before.txt
```

## 3. Inject

Apply `route_leak_from_as151` with a reversible action.

Preferred action:

```text
AS151 live BGP speaker announces 10.150.0.0/24 toward AS2.
```

Fallback action:

```text
Apply a scoped config/policy change that makes AS151 advertise the victim
prefix, record the exact diff, reload the daemon, and keep rollback metadata.
```

## 4. Observe

Agent must identify:

- service symptom at client vantage
- changed BGP best path or AS path
- leaking AS
- accepting or propagating neighbor
- why DNS/origin restart is not the right primary repair

## 5. Repair

Allowed repairs:

- withdraw leaked route
- add scoped prefix filter for AS151 neighbor
- restore previous route daemon config

Every mutation requires confirmation and a rollback record.

## 6. Verify

Collect:

- client probe after repair
- BGP route summary after repair
- traceroute after repair
- repair or rollback event

Pass condition:

```text
origin AS is AS150, AS151 is absent from selected path, and client probe works.
```

## 7. Score

If the agent generated a semantic replay JSON, score it:

```bash
python3 examples/agent-benchmarks/incident.bgp_route_leak_optimizer.v1/scorer.py \
  --replay /tmp/seed-agent-benchmark/incident.bgp_route_leak_optimizer.v1/semantic_replay.json \
  --validate-schema
```

The replay should follow `evidence_schema.json`. A good run should score at
least `85/100` and have `status=pass`.
