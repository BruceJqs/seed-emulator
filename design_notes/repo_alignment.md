# Meta-style Cascade Benchmark Repo Alignment

## Project Shape Read

The SEED Emulator repository builds emulations from Python source into Docker
Compose output. The relevant reusable pieces for the first benchmark case are:

- `seedemu.layers.Base`, `Routing`, `Ebgp`, `Ibgp`, and `Ospf` for AS, IX,
  router, and BGP reachability modeling.
- `seedemu.services.DomainNameService` and `DomainNameCachingService` for edge
  authoritative DNS and recursive resolver roles.
- Existing Internet examples:
  - `examples/internet/B00_mini_internet` for AS/IX/BGP construction patterns.
  - `examples/internet/B01_dns_component` and `B02_mini_internet_with_dns` for
    DNS service and resolver binding.
  - `examples/internet/B24_ip_anycast` and its test for runtime BIRD session
    enable/disable checks.
- Existing dynamic tests under `tests/` use `SeedEmuTestCase`, Docker, and
  `docker-compose`; this environment has Docker and `docker-compose`, but the
  Python Docker SDK harness is not a reliable first-round path in the local
  Python 3.12 venv because importing `docker` fails on missing `distutils`.

## Chosen First-round Landing

The first S0 benchmark case is placed under
`examples/internet/B51_meta_style_cascade`. This keeps it with Internet control
plane examples and avoids changes to core `seedemu` APIs. A small smoke entry is
placed under `tests/internet/meta_style_cascade` for discoverability.

The S0 runtime co-locates several benchmark roles on routers with loopback
service IPs: AS20 `edge-router` hosts edge authoritative DNS, edge HTTP, and the
health gate; AS30 `dc-router` hosts the backend dependency; AS50
`client-router` hosts the recursive resolver and external probe. This is a
case-local workaround for first-round host-forwarding instability and does not
change SEED router or service APIs.

## Missing Capabilities and Substitutes

The repository does not currently provide a generic networked-agent benchmark,
agent policy, scorer, or replay framework. P0-P3 therefore add case-local
metadata, policy, scoring stubs, and a shell/Python controller. Full agent,
recovery, scorer, and replay logic remain later P4-P6 work.

`BgpLookingGlassService` exists, but its build path downloads external
dependencies. The P0-P3 route-view evidence uses BIRD control commands inside
route-view routers instead, which is lighter for smoke validation.

The service routers use a case-local Docker image override
(`b51-router-services-base-amd` or `b51-router-services-base-arm`) that layers
`bind9` and `nginx-light` on the existing SEED router image. This keeps the
benchmark-specific DNS/HTTP/runtime scripts local to the case and avoids core
compiler or image API changes.

S0 and S1 are runtime tiers in this round and are accepted only through live
Docker containers. The case-local `scale_background.py` generator has been
reclassified as a telemetry fixture generator for later scorer/replay work. It
can generate AS inventory, relationship rows, route-view rows, probe logs, and
event timelines from `scale_tiers.json`, but those files do not make S1 or S2
pass. S2 now has a local 1023-container prototype, but it is guarded and not
accepted because the local host hit ARP/neighbor-cache exhaustion during live
validation. S2 requires a prepared host, DistributedDocker, or a multi-host
runner before it can be accepted.

## Control-plane Boundary

The failure is not modeled by stopping DNS, deleting records, changing client
hosts, or editing scorer/oracle state. A case-local fault script changes the
edge-to-DC internal path policy. The edge health gate observes backend
reachability loss and withdraws the edge DNS/service prefix by disabling the
external BGP peer through BIRD.
