---
name: seed-control-plane-design
description: Use when designing or reviewing SEED Emulator routing control-plane features, including BIRD, FRR, ExaBGP, BGP, OSPF, Looking Glass services, runtime validation, and example topology semantics.
metadata:
  short-description: SEED control-plane design review
---

# SEED Control-Plane Design

Use this skill when adding or reviewing routing control-plane features in SEED
Emulator.

## Design Rules

- Router daemon choice belongs on `Router`: prefer
  `createRouter(..., routingBackend="bird|frr")` for full routing daemons.
- Protocol layers describe intent: `Ebgp`, `Ibgp`, and `Ospf` should record
  peers, relationships, route policy, and OSPF interface intent.
- `Routing` renders daemon-specific config from intent. BIRD and FRR templates
  live behind backend-specific rendering paths.
- Do not model FRR or ExaBGP as a Layer just to switch a router daemon.
  Compatibility shims are fine, but examples should use Router backend APIs.
- ExaBGP is a control-plane BGP speaker service when it speaks BGP on an IX or
  router-facing link. Treat it as a speaker installed through
  `ExaBgpService + Binding`, not as a full BIRD/FRR transit backend.
- ExaBGP v1 supports eBGP, static announcements, live announce/withdraw, event
  logs, and dashboard. Reject iBGP/OSPF transit with clear errors.
- Looking Glass is a Service: install it on a host via Binding, then declare
  observed routers with `.addRouter(asn, routerName)`.
- Keep route-state views and event-stream views separate. Classic Looking Glass
  reads router route state; ExaBGP dashboard shows event/log stream.

## Example Quality Bar

Every control-plane example should prove runtime semantics, not only generated
files:

- Regenerate `output` from source.
- Build and start with a unique `COMPOSE_PROJECT_NAME`.
- Check generated daemon config.
- Check daemon processes inside containers.
- Check BGP/OSPF neighbors and learned routes.
- Check route attributes when relevant: AS path, next hop, local-pref,
  communities.
- Check pages and logs for dashboard/Looking Glass features.
- Explain which source file connects the feature into SEED.

## Review Checklist

- Existing default BIRD examples still work without source changes.
- Router backend state is visible from the Router API and metadata labels.
- BIRD routers do not receive FRR/ExaBGP startup commands.
- FRR routers do not start BIRD.
- ExaBGP speaker nodes expose `/etc/exabgp/exabgp.conf`,
  `/run/exabgp/live.in`, event log, and dashboard.
- Looking Glass service uses Binding for the host and explicit router
  registration for observed route state.
