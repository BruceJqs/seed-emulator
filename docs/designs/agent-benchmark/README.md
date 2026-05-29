# SEED Agent Benchmark Design

This directory turns the current SeedAgent discussion into an implementation plan.
The target is not another demo prompt. The target is a reproducible benchmark
platform where agents operate inside a running SEED runtime, diagnose incidents,
repair safely, and leave evidence that an oracle can score.

## Positioning

SeedAgent should be evaluated on incident lifecycle work:

```text
attach -> observe -> localize -> propose -> gate -> act -> verify -> report
```

The benchmark must preserve the reason SEED is useful:

- real containers, daemons, routes, DNS, mail, web pages, and logs
- multi-AS and cross-layer failures that ordinary Docker Compose cannot model
- repeatable fault injection without touching the real Internet
- permission views that can hide topology, logs, or control-plane state
- deterministic oracles for route state, service health, page probes, and logs

## Architecture

The benchmark is a runtime system around SEED, not a prompt collection:

```text
scenario package
  |-- topology / normal state / fault / policy / oracle
  v
SEED runtime output  <----- fault injector
  |                         |
  |                         v
  |                  replay artifacts
  v                         ^
SeedOps tools ----> policy gate ----> SeedAgent
  |                         |
  v                         v
evidence store       proposed actions
  |                         |
  +----------> oracle / scorer <----------+
                         |
                         v
                report and benchmark score
```

Responsibilities:

- SEED builds the network world: AS boundaries, services, routing, DNS, mail,
  pages, logs, and containers.
- SeedOps exposes structured runtime evidence and scoped mutation tools.
- SeedAgent reasons over the allowed tools and must keep an evidence trail.
- The policy gate enforces observation/action permissions outside the prompt.
- The oracle and scorer use hidden truth plus replay artifacts to grade the run.
- InternetMap can later render topology, path changes, event timeline, and
  agent evidence, but it is not the oracle.

## Design Principles

1. Runtime first. Tasks attach to a running emulator output and collect live
   evidence. Source topology may be used by the oracle, not by the agent unless
   the task grants it.
2. Evidence before action. Every diagnosis must cite artifacts: command output,
   structured SeedOps result, route table, DNS answer, log line, page response,
   or metric.
3. Permission is part of the task. The same incident should have black-box,
   service, network, and operator variants.
4. Repair requires gates. Mutating actions need declared scope, precheck,
   rollback, and postcheck.
5. Scoring is not just final success. The scorer must capture root-cause
   accuracy, safety, minimality, recovery validation, and evidence quality.
6. Scenarios are reusable assets. A scenario is a package containing topology,
   normal state, fault injection, policy, oracle, scorer, and replay artifacts.

## Document Map

- [task-package-spec.md](task-package-spec.md): common package contract,
  permission model, oracle/scorer schema, and mission mapping.
- [real-incident-replay.md](real-incident-replay.md): Meta, AWS S3, Fastly,
  Cloudflare, BGP route leak, Dyn DNS, and Google congestion replay plan.
- [hackathon-sandbox.md](hackathon-sandbox.md): project deployment sandbox for
  Dockerfile/Compose/database/API projects.
- [ctf-ai-attack-defense.md](ctf-ai-attack-defense.md): CTF and AI offense-defense
  tournament design.
- [red-blue-operations.md](red-blue-operations.md): role-based red/blue/purple
  operations in SEED.
- [restricted-permission-benchmark.md](restricted-permission-benchmark.md):
  benchmark levels for limited observation and limited action.
- [roadmap.md](roadmap.md): staged implementation plan, first milestones, and
  acceptance criteria.
- [implementation-index.md](implementation-index.md): concrete build order,
  first interfaces, and what not to implement first.

## AgentAAA Decomposition

The `agentaaa.md` research notes are split into benchmark tracks instead of one
large document:

| Research line | Benchmark track | First concrete artifact |
| --- | --- | --- |
| real Internet outage replay | [real-incident-replay.md](real-incident-replay.md) | `incident.bgp_route_leak_optimizer.v1` |
| hackathon project sandbox | [hackathon-sandbox.md](hackathon-sandbox.md) | `sandbox.compose_db_migration.v1` |
| CTF / AI attack-defense | [ctf-ai-attack-defense.md](ctf-ai-attack-defense.md) | web + DNS/mail abuse package |
| red/blue/purple operations | [red-blue-operations.md](red-blue-operations.md) | `rb.bgp_leak_blue_recovery.v1` |
| restricted-permission agent benchmark | [restricted-permission-benchmark.md](restricted-permission-benchmark.md) | route leak `O0A0/O3A0/O3A3/O4A3` variants |
| reusable package/oracle/scorer | [task-package-spec.md](task-package-spec.md) | scenario package schema |

This keeps the research ambition high while preserving an implementation path:
each track must eventually produce a package, a runtime fault, allowed tools,
evidence artifacts, repair gates, and an oracle.

## First Deliverable Target

The first runnable slice should be small but real:

```text
BGP route leak incident package
  runtime: B00 or B30-derived mini Internet
  fault: wrong prefix announcement from a non-owner AS
  observe: black-box curl/traceroute + BGP summary
  act: scoped route-map or withdrawal after confirmation
  oracle: victim route restored, leaked route filtered, client probe succeeds
```

This slice exercises the same platform pieces needed by the broader roadmap:
runtime attachment, fault injection, permission policy, structured evidence,
safe mutation, rollback, and deterministic scoring.

The initial package skeleton lives at:

```text
examples/agent-benchmarks/incident.bgp_route_leak_optimizer.v1/
```
