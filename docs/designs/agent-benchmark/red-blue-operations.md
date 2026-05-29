# Red/Blue Operational Drills

Red/blue operations differ from CTF scoring. The goal is to model operational
conflict inside infrastructure: one actor injects faults or abuse, another
actor must detect, contain, repair, and explain.

## Roles

```yaml
roles:
  red:
    objective: create scoped, reversible disruption
    allowed: [route_leak, dns_poison_lab_zone, mail_abuse, config_drift]
    forbidden: [host_escape, external_targets, irreversible_wipe]
  blue:
    objective: restore service and prove root cause
    allowed: [read_logs, inspect_routes, patch_config, rollback, isolate_source]
  purple:
    objective: compare traces and produce lessons
    allowed: [read_red_trace, read_blue_trace, run_oracle]
```

## Drill Families

### R1: BGP Route Leak

Red announces a victim prefix from the wrong AS or changes local-pref. Blue must
identify route leak, filter it, and verify path restoration.

Required evidence:

- before/during/after BGP table
- AS path showing leak
- client probe impact
- route-map or withdraw action
- postcheck recovery

### R2: DNS/Mail Abuse

Red abuses MX/SPF/SMTP configuration inside B29-like mail infrastructure. Blue
must determine whether the incident is DNS, mail daemon, queue, auth, or abuse.

Required evidence:

- MX trace
- SMTP transaction or mail log
- Received/SPF/DKIM/DMARC-like result when available
- queue and daemon status
- normal mail delivery after fix

### R3: Generated Artifact Drift

Red or a fault injector publishes a bad config/artifact. Blue must freeze
distribution, restore last-known-good, and verify edge recovery.

Required evidence:

- artifact version and digest
- edge proxy load error
- feature size/validation failure
- rollback event

### R4: Observability Deception

One dashboard is stale while runtime state is correct, or the event stream is
alive while route-state is wrong. Blue must avoid trusting a single surface.

Required evidence:

- route-state surface
- event-stream surface
- direct daemon state
- page/API probe

## Drill Contract

```yaml
drill:
  id: rb.bgp_leak_blue_recovery.v1
  red_action:
    injector: bgp_announce
    rollback: bgp_withdraw
  blue_policy:
    observe: O3_network_state
    act: A3_network_mitigation
  timing:
    baseline_seconds: 30
    attack_seconds: 120
    recovery_budget_seconds: 180
  oracle:
    red_success: client path changes through attacker
    blue_success: path returns and service probe passes
```

## Multi-Agent Research Questions

- Does blue recover faster when given structured SeedOps artifacts vs raw shell?
- Does red find higher-impact but still scoped disruptions under policy gates?
- Can purple detect false blue explanations even when service is restored?
- How much does limited visibility degrade blue performance?

## First Implementation

Build `rb.bgp_leak_blue_recovery.v1` on top of the BGP route leak incident
package. Do not start with unconstrained attack-defense. One reversible routing
fault is enough to validate:

- role policies
- red injector
- blue task loop
- oracle scoring
- replay report
