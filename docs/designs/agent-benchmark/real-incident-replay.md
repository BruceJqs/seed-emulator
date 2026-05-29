# Real Internet Incident Replay

This track turns public Internet outages into executable SEED tasks. The point
is not to clone the vendor's internal systems. The point is to preserve the
causal structure that makes the incident hard for an operator agent.

## Why SEED Is Necessary

Ordinary Docker or a local LAN can simulate a broken service. They cannot
faithfully evaluate incidents where:

- a service is alive but unreachable due to BGP or DNS
- a control-plane artifact propagates into a data-plane failure
- a route leak changes path selection while the origin remains healthy
- TTL, route convergence, cache warmup, or region failover changes symptoms over
  time
- the agent only sees one organization's side of a multi-AS incident

SEED can model AS boundaries, IX peering, routing policy, DNS, service daemons,
and user probes in one repeatable runtime.

## Case Catalog

| ID | Incident Shape | SEED Model | First Action Surface |
| --- | --- | --- | --- |
| `meta.backbone_dns_bgp.v1` | backbone config change -> DNS health fail -> BGP withdrawal | edge DNS AS, transit AS, DC backbones | restore safe reachability before re-announcing DNS prefix |
| `aws.s3_control_plane_capacity.v1` | maintenance command removes too many index/placement nodes | object frontend, index service, placement service, storage nodes | restore quorum, protect consistency |
| `fastly.edge_config_latent_bug.v1` | legal config triggers latent edge bug globally | config API, compiler, edge proxies, origins | rollback or disable triggering config |
| `cloudflare.feature_file_generation.v1` | DB permission change creates bad feature file | feature DB, generator, distributor, edge proxy | freeze bad artifact, restore last-known-good |
| `bgp.route_leak_optimizer.v1` | optimizer leaks victim prefix through transit | victim AS, small ISP, transit, clients | filter/withdraw leaked route |
| `dyn.authoritative_dns_ddos.v1` | authoritative DNS overload and TTL-dependent failure | primary/secondary DNS, resolvers, clients, origins | enable secondary DNS and rate limiting |
| `google.regional_congestion.v1` | capacity drop causes packet loss and retry amplification | multi-region services and links | reduce cross-region traffic and reroute |

## First Implementation: BGP Route Leak

Start here because it uses existing SEED strengths and is visually obvious.

```text
normal:
  client -> transit -> victim AS -> service prefix

fault:
  optimizer announces victim prefix
  transit accepts route
  clients select wrong path
  service stays healthy but users fail or path degrades

repair:
  filter prefix from optimizer neighbor
  or withdraw leaked route
  verify client best path returns to victim AS
```

Required runtime probes:

- BGP table before/during/after
- AS path from multiple routers
- client curl or ping to victim service
- traceroute path before/during/after
- route-map or prefix-list config evidence

Acceptance:

- agent does not blame origin service or DNS
- agent identifies leaking AS and propagating transit
- repair is scoped to routing policy or leaked announcement
- rollback or restoration is recorded

## Second Implementation: Fastly-Style Edge Config Bug

This is the best service-oriented demo after route leak.

```text
normal:
  config compiler publishes safe bundle
  edge proxies serve origin/cache traffic

fault:
  valid customer config triggers latent edge bug
  many edges return 503
  origin, DNS, and BGP remain healthy

repair:
  rollback config bundle
  freeze rollout
  verify regional edge recovery
```

SEED services needed:

- config API
- bundle compiler
- edge proxy containers in multiple regions
- origin service
- page/API probes

## Deep Cases

### Meta-Style Backbone -> DNS -> BGP Cascade

This should be implemented after route leak and DNS probes are stable. It needs:

- authoritative DNS nodes that withdraw prefixes when DC reachability fails
- health checker logs
- transit BGP table
- recursive resolver behavior
- recovery gate that forbids re-announcing while DNS is unhealthy

### S3-Style Control-Plane Capacity Failure

This should be a service-ops benchmark, not a BGP benchmark. It needs:

- object frontend
- metadata index quorum
- placement service quorum
- downstream services
- integrity-check and cache-warmup timers

The key scoring item is safety: do not skip consistency checks or blindly write
objects when placement is unstable.

### Cloudflare-Style Generated Artifact Failure

This should drive the artifact/oracle system:

- generated feature file
- size and duplicate-row metric
- distribution freeze
- last-known-good fallback
- edge proxy recovery checks

### Dyn-Style DNS DDoS

This is the bridge to red/blue and CTF work. Implement with capacity controls,
not real attack traffic:

- primary authoritative DNS QPS limit
- recursive resolver TTL behavior
- secondary provider disabled or partial
- user probes from multiple resolvers

### Google-Style Congestion

This should come later because it needs metrics over time:

- link loss/delay injection
- cross-region traffic
- retry amplification
- traffic engineering and graceful degradation controls

## Deliverables Per Case

Each case must include:

- `case.md`: public incident summary and preserved causal structure
- `topology.yaml`: nodes, ASes, services, links, observability endpoints
- `normal_state.yaml`: baseline probes and expected outputs
- `fault_injection.yaml`: deterministic trigger and hidden root cause
- `agent_policy.yaml`: observation/action levels and forbidden shortcuts
- `oracle.json`: truth and postchecks
- `scorer.py`: deterministic score calculation

## Research Question

Can a constrained agent recover from cross-layer Internet incidents better than
a free-form ReAct agent when both operate on the same SEED runtime?

Primary comparisons:

- free ReAct vs layered diagnostic policy
- full observation vs restricted observation
- advice-only vs gated repair
- single run vs repeated perturbation runs
