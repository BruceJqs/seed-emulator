# SEED Design Principles

This file records reusable design principles for SEED Emulator feature work and
AI-assisted extensions. It should evolve with the codebase and remain concise
enough for students and agents to apply during reviews.

## 1. Put Responsibilities at the Right Layer

- `Base` owns topology: ASes, IXes, routers, hosts, networks, and attachments.
- Protocol layers own intent: BGP peers, relationships, route policy, OSPF
  interface intent, and other protocol semantics.
- Rendering layers own daemon output: BIRD config, FRR config, startup commands,
  host routing, and backend-specific files.
- Services own node-scoped application behavior and should be installed through
  explicit service APIs and bindings when the abstraction is mature enough.
- Operator scripts may orchestrate generation, startup, tests, and cleanup, but
  they should not be the only place where feature semantics live.

## 2. Model Intent Before Syntax

SEED scenarios should describe what the emulation means before deciding how a
daemon implements it. For routing, this means `Ebgp`, `Ibgp`, `Ospf`, and shared
metadata should record relationships and policies, while `Routing` renders BIRD
or FRR syntax later.

Good examples:

- router backend choice belongs on `Router`, not a separate fake layer.
- ExaBGP peer declarations record BGP intent before daemon-specific config is
  written.
- Email provider declarations record domain, AS, IP, ports, and DNS intent
  before Docker containers are attached.

## 3. Match the Abstraction to the Runtime Role

Do not force every feature into the same class shape. Pick the abstraction that
matches the runtime role:

- BIRD and FRR are full routing-daemon backends for `Router`.
- ExaBGP is a BGP speaker service, not a transit router backend.
- Looking Glass is an observer service, not a routing participant.
- B29 Email is currently a compiler helper plus scenario-owned DNS/topology; a
  future version should move toward standard `Service + Binding` semantics.

The design should state current maturity honestly. A helper is acceptable during
iteration if the future migration path is explicit.

## 4. Keep Cross-Component Effects Declarative

Some services need to affect another component. That is allowed when the effect
is recorded as intent and rendered by the owning layer.

Example: `ExaBgpService.addPeer()` may install BGP session intent on the peer
router, but it should not directly write BIRD or FRR config. `Routing` remains
responsible for daemon-specific output.

This rule keeps feature APIs useful without breaking ownership boundaries.

## 5. Separate Observation Semantics

Different tools observe different facts. Do not merge them just because they are
shown together in a demo:

- route-state views answer what a router currently selects and exports.
- event-stream views answer what a speaker announced, withdrew, or logged over
  time.
- service-chain checks answer whether the application works end to end.

Looking Glass and ExaBGP dashboards can complement each other, but they should
not be described as the same observability surface.

## 6. Make Runtime Evidence Part of the Contract

Generated files are not enough. A feature should define the evidence required to
prove it works in a running emulator.

Typical evidence:

- generated daemon config exists and matches the chosen backend.
- the expected daemon process is running and the wrong daemon is absent.
- neighbors, routes, AS paths, next hops, and policy effects match intent.
- live announce/withdraw or mutation paths change runtime state and roll back.
- service scenarios prove DNS, connectivity, protocol logs, mailbox/page/API
  state, and user-visible behavior.

Validation commands should be stable, documented, and repeatable.

## 7. Preserve Compatibility While Moving Examples Forward

Compatibility shims can remain for old scenarios, but new examples and docs
should use the canonical API. Defaults should stay stable unless a migration is
intentional and documented.

For routing:

- default routers remain BIRD unless the scenario requests FRR.
- FRR is selected with `createRouter(..., routingBackend="frr")`.
- ExaBGP examples should use `ExaBgpService + Binding`.
- Looking Glass examples should install a service host and explicitly register
  observed routers.

## 8. Keep Documentation Design-Oriented

Formal design docs should explain:

- design position in the SEED architecture.
- core file and class map.
- API flow from scenario code to runtime output.
- design boundaries and non-goals.
- validation contract.
- future migration path.

Avoid committing one-off review notes, temporary runbooks, or short-lived demo
scripts as architecture documentation.

## 9. Treat Agent Work as Supervised Operations

Agent-facing work should start from runtime evidence and operate under explicit
safety rules:

- inspect before acting.
- separate read-only tools from mutation tools.
- require risk metadata and confirmation for dynamic changes.
- scope every mutation and record rollback.
- verify after action and export replayable evidence.
- never grade a run as successful without evidence.

Benchmark packages should define scenario setup, fault injection, allowed
actions, oracle expectations, scoring, and replay schema separately from the
mission prompt.

## 10. Keep AI Assets Close to Code but Small

Repository-owned AI assets belong under `ai/` so they can evolve with the
implementation. They should be reusable engineering assets, not local Codex
state.

Rules:

- skills capture reusable design or operation workflows.
- MCP contracts separate read-only inspection, controlled mutation, and evidence
  export.
- do not commit secrets, generated runtime output, personal logs, or local
  virtual environments.
- keep skill instructions concise; move large references into skill-local
  `references/` only when needed.

## 11. Prefer Reusable Scenarios Over One-Off Demos

A good scenario should be useful beyond the first review. It should have:

- a clear topology and service purpose.
- deterministic startup and cleanup.
- stable validation entry points.
- documented observations and expected outcomes.
- enough structure for agents, students, and CI-style checks to reuse it.

When a scenario becomes a benchmark, make the package machine-readable and keep
the mission export as a derived interface, not the source of truth.

## 12. Say What Is Not Supported

A clean design states its limits. Unsupported modes should be rejected or marked
as future work rather than silently implied.

Examples:

- ExaBGP v1 does not claim arbitrary remote multihop peering, iBGP transit,
  OSPF transit, or full router replacement.
- B29 Email does not claim production mail security; SPF, DKIM, DMARC, STARTTLS,
  MTA-STS, and DANE are future optional modes.
- Agent missions do not bypass confirmation gates for risky runtime mutation.
