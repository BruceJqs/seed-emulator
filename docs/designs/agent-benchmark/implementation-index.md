# Agent Benchmark Implementation Index

This page is the bridge from design to code. It keeps the first implementation
small enough to build while preserving the research target.

## Build First

Start with one incident package:

```text
examples/agent-benchmarks/incident.bgp_route_leak_optimizer.v1/
```

It should reuse a B00/B30-style mini Internet and add a deterministic route
leak. The runtime must prove:

- origin service is healthy before and during the incident
- client path changes through the leaking AS
- BGP table contains the abnormal prefix and AS path
- scoped withdraw or prefix filter restores the path
- scorer rejects fixes that only restart the origin or edit DNS

## Minimal Components

### Scenario Loader

Reads package files and returns:

- runtime base example
- required generated output directory
- fault injector command
- permission policy
- oracle checks

It should not replace SEED's Python APIs. It should only adapt package metadata
to existing examples, SeedOps tools, and SeedAgent missions.

### Fault Injector

First injector: BGP route leak.

Required behavior:

- capture baseline BGP route and client probe
- announce or install the leaked route
- record the fault event in `replay/`
- expose a rollback command
- verify rollback restores the expected route

### Policy Gate

Policy must bind to tools, not text instructions. The first gate can be simple:

- allow read-only SeedOps tools for observe stages
- require confirmation before mutation
- block direct source-topology reads unless the package grants them
- log denied tool calls for scoring

### Oracle / Scorer

The oracle checks runtime facts:

- selected path before fault
- selected path during leak
- selected path after repair
- victim service probe
- absence of forbidden shortcuts

The scorer reads replay artifacts and produces a deterministic JSON score.

## Build Later

Do not start with these:

- a large SDK that hides SEED core abstractions
- free-form multi-agent CTF
- unrestricted exploit tooling
- long-running dynamic world
- UI-first dashboards without an oracle

Those are useful after the package, policy, injector, evidence, and scorer loop
works on one controlled incident.

## Interfaces To Keep Stable

Scenario package:

```text
package.yaml
case.md
topology.yaml
normal_state.yaml
fault_injection.yaml
agent_policy.yaml
oracle.json
scorer.py
replay/
```

Runtime stages:

```text
baseline -> inject -> observe -> propose -> gate -> act -> verify -> score
```

Evidence categories:

```text
config, process, neighbor, route, page, log, probe, action, rollback
```

These names should appear consistently in SeedOps artifacts, replay files, and
benchmark reports.
