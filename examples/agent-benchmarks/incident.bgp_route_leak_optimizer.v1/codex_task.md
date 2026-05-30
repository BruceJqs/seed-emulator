# Codex Task: Route Leak Optimizer Live Drill

You are attached to a running SEED mini Internet runtime. Treat this as an
incident response benchmark, not a generic routing demo.

## Objective

Diagnose and repair a route leak where AS151 behaves like a small route
optimizer and leaks the AS150 victim prefix `10.150.0.0/24` toward AS2.

## Operating Rules

- Work from runtime evidence first: inventory, BGP route summaries, traceroute,
  client probes, and route daemon logs.
- Do not use `oracle.json`, `fault_injection.yaml`, or this package's hidden
  root-cause fields while acting as the agent.
- Do not restart the AS150 victim service as the primary fix.
- Do not edit DNS to hide a routing failure.
- Do not hardcode a route on a single client.
- Do not disable all BGP sessions on AS2.
- Any mutation must be scoped and followed by rollback or repair evidence.

## Required Evidence

Collect and report:

- before route state for `10.150.0.0/24`
- before client reachability or traceroute evidence
- during-fault route state showing AS151 in the selected or candidate path
- evidence that AS150/DNS are not the primary fault
- repair action and rollback record
- after route state showing AS150 restored and AS151 absent from selected path

## Preferred Live Drill

Use the exported mission task when available:

```bash
examples/agent-missions/run_task_demo.sh \
  --task TS_B00_ROUTE_LEAK_OPTIMIZER_LIVE \
  --objective "Diagnose AS151 route leak for 10.150.0.0/24, repair it, and record before/during/after evidence" \
  --attach-output-dir examples/internet/B00_mini_internet/output \
  --context-json '{"target_prefix":"10.150.0.0/24","leaking_asn":"151","victim_asn":"150","propagating_asn":"2"}' \
  --risk on \
  --confirm-token YES_RUN_DYNAMIC_FAULTS
```

If you are running manually, use the same stages:

1. Baseline route summary and client probe.
2. Inject AS151 announcement for `10.150.0.0/24`.
3. Observe changed AS path and client symptom.
4. Withdraw the leak or apply a scoped filter.
5. Verify AS150 is restored.
6. Produce `semantic_replay.json` using `evidence_schema.json`.

## Report Shape

End with:

- root cause
- evidence timeline
- repair chosen
- why victim restart and DNS edit were wrong
- postchecks
- replay/scorer path if generated
