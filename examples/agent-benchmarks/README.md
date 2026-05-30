# SEED Agent Benchmarks

This directory contains reusable SeedAgent benchmark packages. A package is not
just a mission prompt. It defines runtime setup, normal state, fault injection,
allowed observations/actions, oracle checks, scoring, and replay artifacts.

## Package Families

- `incident.*`: real Internet incident replay
- `sandbox.*`: project deployment sandbox
- `ctf.*`: CTF / AI attack-defense scenario
- `rb.*`: red/blue operational drill
- `perm.*`: restricted-permission benchmark variant

## First Package

```text
incident.bgp_route_leak_optimizer.v1/
```

This package is the first mission-ready implementation target because SEED can
already model AS boundaries, BGP path changes, client probes, and scoped
routing repairs.

Agent mission export:

```text
examples/agent-missions/tasks/TS_B00_ROUTE_LEAK_OPTIMIZER_LIVE.yaml
examples/agent-missions/playbooks/ts_b00_route_leak_optimizer_live.yaml
```

## Expected Run Loop

```text
generate runtime -> collect baseline -> inject fault -> attach agent
  -> collect evidence -> propose repair -> gate action -> repair
  -> verify -> score -> write replay
```

The package skeleton is machine-readable planning material. Runtime adapters,
injectors, and scorers should be added incrementally.

For Codex/agent-facing instructions, start from:

```text
examples/agent-benchmarks/incident.bgp_route_leak_optimizer.v1/codex_task.md
```

Live mission command:

```bash
examples/agent-missions/run_task_demo.sh \
  --task TS_B00_ROUTE_LEAK_OPTIMIZER_LIVE \
  --objective "Diagnose AS151 route leak for 10.150.0.0/24, repair it, and record before/during/after evidence" \
  --attach-output-dir examples/internet/B00_mini_internet/output \
  --context-json '{"target_prefix":"10.150.0.0/24","leaking_asn":"151","victim_asn":"150","propagating_asn":"2"}' \
  --risk on \
  --confirm-token YES_RUN_DYNAMIC_FAULTS
```

## Validation

Validate all benchmark packages:

```bash
python3 examples/agent-benchmarks/validate_package.py --run-scorer
```

Validate one package:

```bash
python3 examples/agent-benchmarks/validate_package.py \
  examples/agent-benchmarks/incident.bgp_route_leak_optimizer.v1 \
  --run-scorer
```

The package scorer reports `incomplete` until real replay artifacts are
produced. That is intentional: a package with no runtime evidence should not
pass. Semantic replay samples can still be scored to validate the grading
contract.

Score the included semantic replay samples:

```bash
python3 examples/agent-benchmarks/incident.bgp_route_leak_optimizer.v1/scorer.py \
  --replay examples/agent-benchmarks/incident.bgp_route_leak_optimizer.v1/replay/samples/correct_repair.json

python3 examples/agent-benchmarks/incident.bgp_route_leak_optimizer.v1/scorer.py \
  --replay examples/agent-benchmarks/incident.bgp_route_leak_optimizer.v1/replay/samples/wrong_origin_restart.json
```
