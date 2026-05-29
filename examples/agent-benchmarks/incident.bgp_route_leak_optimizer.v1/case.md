# Case: BGP Route Leak Via Optimizer

## Original Incident Shape

A small network or route optimizer announces routes it should not originate or
propagate. An upstream accepts and spreads the leaked path. Some clients select
the wrong AS path, sending traffic through a network that cannot correctly
serve or carry it. The victim origin may remain healthy, which makes service
debugging misleading unless the operator checks routing state.

This package preserves the causal structure, not a vendor-specific topology.

## Reproduction Goal

Create a SEED mini Internet where:

- a victim AS owns and serves a prefix
- a leaking AS advertises the victim prefix or a more attractive route
- a transit AS accepts the bad route
- at least one client path changes through the leaking AS
- the service symptom is visible from the client side
- the correct repair is scoped routing mitigation, not DNS or origin restart

## Experiment Environment

Base runtime:

```text
examples/internet/B00_mini_internet
```

Initial concrete mapping:

```text
victim AS: AS150
leaking AS: AS151
transit/propagating AS: AS2
client vantage: AS152 or AS154 host
target prefix: 10.150.0.0/24
IX: IX100
```

The exact node names should be resolved from generated runtime inventory, not
hardcoded into the agent prompt.

## Normal State

- victim service is reachable from the client vantage
- BGP best path for the target prefix points to AS150
- AS path does not include AS151
- traceroute does not traverse AS151

## Fault Injection

The injector announces or installs a leaked path for `10.150.0.0/24` from AS151
and records the action in `replay/`.

The preferred implementation is a reversible control-plane action:

- dynamic announce/withdraw when ExaBGP or a live BGP speaker is available
- otherwise a scoped route-policy/config change with explicit rollback

## Agent Observation

The agent must work from runtime evidence:

- client curl/ping/traceroute
- BGP route summary from approved routers
- AS path before/during/after
- route daemon logs or event log
- repair action and rollback evidence

Source topology is oracle material unless the policy explicitly grants it.

## Agent Actions

Valid repairs:

- withdraw the leaked announcement
- add a scoped prefix/AS path filter at the accepting neighbor
- lower local preference for the leaked path if the scenario exposes policy

Forbidden shortcuts:

- restart the victim origin service as the primary repair
- edit DNS records to hide a routing failure
- hardcode a route on one client only
- disable all BGP sessions on the transit AS

## Success Conditions

- client probe succeeds after repair
- BGP best path returns to AS150
- leaked AS path is absent from the selected route
- the repair is scoped and rollback is recorded
- the report explains why origin and DNS were not the root cause

## High-Score Solution

1. Establish baseline service and route state.
2. Confirm the incident changes path selection while origin remains healthy.
3. Identify AS151 as the leaking AS and AS2 as the propagating neighbor.
4. Apply a scoped withdraw or prefix filter.
5. Verify route restoration and client recovery.
6. Produce an evidence report with before/during/after artifacts.
