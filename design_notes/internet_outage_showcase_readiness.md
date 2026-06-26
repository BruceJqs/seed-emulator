# Internet Outage Benchmark Showcase Readiness Review

This review covers B51-B57 after the first integrated implementation pass. It
is written as an operator-facing checklist for usability, design quality, and
showcase readiness. It is not a substitute for rerunning the live acceptance
sequence on the presentation host.

## Current Acceptance Boundary

The accepted local showcase target is S1.5. S1.5 means a real SEED Docker
runtime with roughly 10^2 live containers, staged normal/fault/recovery checks,
role-scoped observations, constrained actions, collection, shutdown, and
residual cleanup. Static generation, route-view fixture generation, and
telemetry files do not count as runtime acceptance.

S2 remains guarded by preflight. It should not be started on this host without
explicit operator approval and prepared neighbor-cache limits.

## Case Availability

| Case | S1.5 accepted live containers | Primary mechanism | Cache or stale-state guard | Showcase port |
|---|---:|---|---|---:|
| B51 | 225 | Health-gated BGP withdrawal after edge-to-DC fault | Resolver and authoritative DNS checks, route withdrawal, health-gate state | 8510 |
| B52 | 182 | Maintenance selector removes control-plane capacity | Canary PUT and ordered index/placement recovery | 8520 |
| B53 | 186 | Valid edge config triggers POP runtime failures | Origin-health contrast and POP canary before full restore | 8530 |
| B54 | 191 | Feature-file expansion breaks core proxy path | Known-good rollback, fail-small behavior, tail-service validation | 8540 |
| B55 | 177 | More-specific BGP route leak | Aggregate versus more-specific route checks from filtered and unfiltered networks | 8550 |
| B56 | 178 | Authoritative DNS path overload | Fresh lookup/cache-miss validation, secondary-DNS contrast, named process remains alive | 8560 |
| B57 | 194 | Maintenance automation removes control-plane route distribution | Local workload health contrast, external route withdrawal, region-by-region recovery | 8570 |

## Design Quality Assessment

The case set intentionally uses case-local mechanisms instead of changing core
SEED APIs. This keeps the examples portable and limits regression risk. The
shared controller layer is limited to runtime orchestration, exercise ledger
behavior, policy gates, S2 preflight, and the read-only showcase panel. Each
fault mechanism remains in the individual case.

The current S1.5 sizes are appropriate for classroom and lab presentation
because they cross the toy-example boundary without forcing the host into the
resource profile required by S2. The sizes are deliberately uneven because the
roles differ: B51 needs many probes and collectors, B53/B54 need POP and
customer-service fanout, B55/B56 need network-view diversity, and B57 needs
regional and control-plane replicas.

The strongest cases for network-level demonstration are B51, B55, and B56.
B52, B53, B54, and B57 are stronger as control-plane/state-machine incidents
with networked viewpoints; they should be presented as realistic distributed
service failures rather than full replicas of the production systems named in
their titles.

## Showcase Flow

For a live presentation, use one case at a time:

1. Generate and start S1.5 with a unique compose project name.
2. Start the case showcase panel on its default port.
3. Run `normal-runtime S1.5` and show baseline evidence in the panel.
4. Move the exercise ledger through baseline observations and notes.
5. Inject the fault and run `fault-runtime S1.5`.
6. Use role-scoped observations to compare public symptoms, provider health,
   route or control-plane state, and recent-change evidence.
7. Apply the allowed mitigation through the exercise action surface.
8. Run recovery validation, collect artifacts, and shut down.
9. Confirm no containers or networks remain for the compose project.

The showcase panel is a read-only aid. It does not mutate containers, inject
faults, recover service, or replace the exercise ledger. It is useful because it
keeps the operator, audience, and code review aligned around the same evidence
contract.

## Documentation and Code Quality Rules

New benchmark documentation, configs, tests, and panel text must remain
English-only. `tests/internet/agent_benchmark_cases/static_contract.sh` enforces
this by rejecting CJK text in benchmark source documentation, configs, and
tests.

The preferred code shape is:

- Keep mechanism logic case-local.
- Keep shared helpers small and operational.
- Do not hardcode absolute workspace paths.
- Do not add core SEED APIs for benchmark-only behavior.
- Keep comments targeted at non-obvious state transitions, not line-by-line
  narration.

## Remaining Risks

- S1.5 should be rerun on the final presentation host because Docker image
  cache, neighbor table behavior, and compose startup timing can differ.
- B52/B53/B54/B57 model complex provider incidents with compact state machines;
  they are valid benchmark scenarios but not full production-system clones.
- The showcase panel reports current artifacts. If a phase has not been run, it
  will report missing evidence rather than silently marking it accepted.
- S2 is still a future host-preparation task, not a presentation dependency.
