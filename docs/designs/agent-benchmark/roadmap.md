# Agent Benchmark Roadmap

This roadmap turns the design into a staged implementation. Each stage must
produce a runnable artifact, not only prose.

## Stage 0: Environment And Branch Setup

Current branch:

```text
feat/agent-benchmark-scenarios
```

Scope:

- design docs only
- no core SEED changes
- no seed-agent submodule edits
- no push until reviewed

## Stage 1: Package Skeleton

Deliver:

- `examples/agent-benchmarks/README.md`
- one package directory for `incident.bgp_route_leak_optimizer.v1`
- schema files:
  - `package.yaml`
  - `case.md`
  - `topology.yaml`
  - `normal_state.yaml`
  - `fault_injection.yaml`
  - `agent_policy.yaml`
  - `oracle.json`
  - `scorer.py`
  - `runbook.md`

Acceptance:

- package validates with a schema checker
- scorer can read a saved replay and return a score
- no runtime mutation yet required

Current seed artifact:

```text
examples/agent-benchmarks/incident.bgp_route_leak_optimizer.v1/
```

## Stage 2: BGP Route Leak Runnable Slice

Deliver:

- B00/B30-derived route leak scenario
- deterministic fault injector
- rollback action
- SeedOps evidence collection wrapper
- oracle checks for before/during/after state

Acceptance:

- baseline client probe succeeds
- fault changes selected route/path
- repair restores selected route/path
- scorer distinguishes correct repair from origin restart or DNS edit

## Stage 3: Fastly-Style Edge Config Demo

Deliver:

- small multi-edge reverse proxy example
- config bundle generator
- faulting config pattern
- rollback/freeze control
- page/API health probes

Acceptance:

- origin remains healthy during incident
- edge 503 appears after config rollout
- last-known-good rollback recovers
- agent report excludes DNS/BGP/origin as root cause

## Stage 4: Permission Variants

Deliver:

- route leak `O0A0`, `O3A0`, `O3A3`, `O4A3` variants
- tool allowlist enforcement in SeedAgent/SeedOps
- repeated-run perturbations

Acceptance:

- black-box agent cannot call forbidden tools
- network-operator agent can produce stronger evidence
- mutation requires confirmation
- scorer reports degradation by permission level

## Stage 5: Hackathon Sandbox Demo

Deliver:

- one intentionally imperfect Docker project
- import-to-SEED scenario adapter
- build/run/probe workflow
- minimal patch scorer

Acceptance:

- agent repairs deployment without exposing DB
- `/health` and functional flow pass
- patch touches allowed files only

## Stage 6: Red/Blue Drill

Deliver:

- red route leak injector
- blue recovery task
- judge timeline
- purple report template

Acceptance:

- red disruption is scoped and reversible
- blue identifies and repairs routing fault
- judge records availability and evidence quality

## Tooling Backlog

SeedOps:

- backend-aware BIRD/FRR/ExaBGP route summaries
- DNS trace schema
- mail trace schema
- page probe schema
- log query with semantic artifact types
- fault injection API with rollback metadata

SeedAgent:

- permission policy bound to MCP tools
- observe/propose/act/verify state machine
- artifact-aware report writer
- scorer/oracle adapter
- replay export and repeated-run harness

InternetMap:

- read-only control-plane summary already started
- future: incident timeline overlay
- future: route leak/path change visualization

## High-Value Demo Narrative

```text
We first show that SeedAgent can attach to a real runtime and collect evidence.
Then we inject a real class of Internet failure: route leak.
The origin service stays healthy; DNS is correct; the path is wrong.
The agent must diagnose from allowed evidence, propose a scoped route-policy
repair, pass a confirmation gate, execute, verify route recovery, and produce a
short evidence report. The oracle scores both the final state and the path taken.
```
