# IPv6 Branch Task Map

This is an initial task map for future agents. It is intentionally not a rigid
ticket list. The goal in `GOAL.md` is fixed; the order here may change when
tests or code review reveal a better path.

## Current Baseline

Already established in this branch:

- optional IPv6 core state for networks and interfaces;
- deterministic IPv6 allocation under default `2000::/12`;
- Docker dual-stack output for IPv6-enabled networks;
- BIRD/FRR IPv6 BGP and OSPFv3 rendering;
- ExaBGP IPv6 control-plane announcements;
- Looking Glass IPv6 route-state observation;
- repository readiness design and user manual updates;
- shared endpoint/address helpers in `seedemu.core`;
- baseline dual-stack DNS and `/etc/hosts` behavior;
- IPv6-aware `Filter` / `Binding` matching;
- optional IPv6 service network and custom container attachment support.

Before adding more work, verify the baseline still passes:

```bash
python3 -m pytest -q test_ipv6_repository_readiness.py test_bgp_control_plane_extensions.py
git diff --check
```

## Phase 1: Stabilize the Current Branch State

- Review the current uncommitted diff and split it into clean commit groups.
- Confirm docs, tests, and code describe the same IPv6 contract.
- Run the static validation suite.
- Regenerate A15-A17 output only when the examples or compiler behavior changed.
- Confirm old IPv4 examples do not gain IPv6 Compose fields by default.
- Commit only clean source/docs/tests. Avoid generated output unless the repo
  convention for that example requires it.

Suggested commit groups:

- core address-family helpers and Binding/Filter readiness;
- Docker compiler and attachment IPv6 support;
- DNS and `/etc/hosts` baseline dual-stack readiness;
- repository design/user docs;
- tests.

## Phase 2: Core Contract Gaps

- Audit remaining core APIs that carry endpoints or addresses.
- Add family-aware helpers only where repeated service logic would otherwise
  duplicate formatting or selection.
- Extend tests for IPv4/IPv6 prefix conflict detection.
- Add or tighten tests for `Filter`/`Binding` IPv4 and IPv6 matching.
- Verify service network IPv4-only and dual-stack compile paths.
- Verify `attachCustomContainer` and `attachInternetMap` IPv4-only and
  dual-stack compile paths.
- Decide whether `crossConnect(...)` needs a separate design doc before any
  implementation. Do not casually add dual-stack cross-connect behavior because
  SCION and legacy examples depend on it.

Current readiness coverage added in `test_ipv6_repository_readiness.py`:

- explicit IPv6 local prefixes are claimed and automatic `/64` allocation skips
  them;
- reserved infrastructure prefixes and explicit IX prefixes are claimed so
  automatic AS allocation cannot collide with them;
- late `Base.enableIpv6()` rejects overlapping explicit AS/IX IPv6 prefixes;
- late `Base.enableIpv6()` claims existing explicit prefixes before future
  automatic allocation;
- `Filter` / `Binding` can require explicit IPv4 and IPv6 matches together;
- service network compile output remains IPv4-only by default, becomes
  dual-stack only when `serviceNetworkIpv6Prefix` is set, and emits
  per-node `ipv6_address` only for interfaces carrying IPv6 state;
- `attachCustomContainer(...)` and `attachInternetMap(...)` cover explicit
  IPv6 addresses without changing their IPv4-only default, and neither
  attachment path invents a per-container IPv6 address on a dual-stack network
  unless one is provided explicitly.

## Phase 3: Endpoint and DNS Foundation

- Make `EtcHosts` output stable for dual-stack nodes.
- Keep authoritative DNS A records unchanged for IPv4-only scenarios.
- Generate AAAA records only when node/interface IPv6 state exists.
- Confirm DNS cache/root-hint behavior stays compatible with old IPv4 flows.
- Add focused tests for helper formatting:
  `formatHostPort`, `formatUrl`, and `formatMultiaddr`.
- Document endpoint helper rules in service-author docs.

Current readiness coverage added in `test_ipv6_repository_readiness.py`:

- endpoint helper tests cover IPv4, IPv6, DNS names, URL paths, and multiaddr
  formatting;
- authoritative DNS and `/etc/hosts` keep IPv4-only defaults and emit AAAA only
  when IPv6 interface state exists;
- DNS cache root hints and forward zones preserve IPv4 while accepting IPv6
  authoritative records;
- DNS cache address selection is Local IPv4 first, then Local IPv6, then first
  available interface fallback for compatibility with service-network-only
  nodes.
- DNS authoritative and cache service address selection now routes through
  shared core node-address helpers instead of service-local duplication.

## Phase 4: Control-Plane Runtime Proof

- Keep A15 as the mixed BIRD/FRR dual-stack BGP plus OSPFv2/OSPFv3 proof.
- Keep A16 as the ExaBGP IPv6 static/live announce/withdraw proof.
- Keep A17 as the Looking Glass IPv4/IPv6 route-state proof.
- For each runtime example, record the exact observation commands in the
  example README or user manual.
- Validate neighbors and routes, not only generated config.
- Keep ExaBGP event streams separate from Looking Glass route-state views.

Useful runtime checks:

```bash
docker exec <node> ip -6 addr
docker exec <bird-router> birdc show protocols
docker exec <bird-router> birdc show route all
docker exec <frr-router> vtysh -c 'show bgp ipv6 unicast'
docker exec <frr-router> vtysh -c 'show ipv6 ospf6 neighbor'
curl -fsS http://127.0.0.1:<lg-port>/api/state
```

## Phase 5: Service Migration Candidates

Move one service at a time. Each migration needs code, docs, and a regression
test or minimal example.

Priority candidates:

- Web/CA endpoint formatting through shared helpers.
- Traffic service address-family selection.
- Kubo/IPFS multiaddr generation through `formatMultiaddr`.
- Email design audit before implementation; do not migrate casually because
  gateway/provider behavior needs careful endpoint decisions.
- Tor design audit for listeners, authorities, and generated configs.
- Ethereum/Monero/Chainlink endpoint audit for RPC, peer discovery, and
  generated URLs.

For each service:

1. Identify where it calls `getAddress()`, formats `host:port`, or writes URLs.
2. Preserve the IPv4 path.
3. Add explicit family selection or dual-stack output only when IPv6 exists.
4. Add tests proving old behavior and the new IPv6 path.
5. Update the readiness matrix.

Current readiness coverage added in `test_ipv6_repository_readiness.py`:

- Traffic generator raw receiver target lists remain unchanged.
- Traffic generator receiver vnode targets can be resolved through shared core
  node-address helpers, default to IPv4, and explicitly select IPv6 when
  requested.
- Kubo bootstrap RPC URLs and peer multiaddrs now route through shared endpoint
  helpers, default to IPv4, and explicitly select IPv6 when requested.
- CA `installCACert(Filter(...))` target selection now matches IPv4 and IPv6
  address/prefix filters through shared interface address helpers while keeping
  the existing default of installing on all nodes.
- Web/CA ACME directory URLs now route through shared URL helpers, preserve
  domain-name defaults, and bracket explicit IPv6 CA endpoint literals; Web
  HTTPS and ACME runtime behavior still need validation before a support claim.
- Monero seed and full-node RPC endpoint lists now route through shared
  address-family and host-port helpers, default to IPv4, and explicitly select
  bracketed IPv6 endpoints when requested; Monero daemon runtime behavior still
  needs validation before a support claim.
- Chainlink generated RPC, faucet, utility, and WebSocket/HTTP node URLs now
  route through shared address-family and URL helpers, default to IPv4, and
  explicitly select bracketed IPv6 URLs when requested; Ethereum/Chainlink
  runtime behavior still needs validation before a support claim.
- Ethereum faucet and utility HTTP URLs now route through shared address-family
  and URL helpers, default to IPv4, and explicitly select bracketed IPv6 URLs
  when requested; Ethereum peer discovery, ENR, bootnode, and daemon runtime
  behavior still need validation before a support claim.
- Tor directory-authority fingerprint downloader URLs and hidden-service
  backend targets now route through shared endpoint helpers, preserving IPv4
  defaults and bracketing explicit IPv6 literals; Tor bind/listener,
  directory authority, consensus, and daemon runtime behavior remain
  IPv4-first and need a separate migration before any support claim.

## Phase 6: Separate Designs Before Code

Do not implement these as quick patches. Start with a design doc and ask for
review when scope is unclear.

- SCION underlay and `crossConnect(...)` dual-stack behavior.
- DHCPv6 or SLAAC.
- MPLS/EVPN IPv6 semantics.
- RealWorldRouter/OpenVPN IPv6 behavior.
- k8s IPv6 support.
- internetmap2 IPv6 visualization/runtime integration.
- Full email IPv6 delivery/provider model.

## Phase 7: Repository Documentation

- Keep `README.md` high-level: SEED supports optional dual-stack emulation, not
  every service is fully migrated.
- Keep `docs/user_manual/ipv6.md` user-facing and operational.
- Keep `docs/designs/ipv6-control-plane-design.md` focused on control-plane
  architecture and class relationships.
- Keep `docs/designs/ipv6-repository-readiness-design.md` focused on the
  repository migration contract and service readiness matrix.
- Keep `ai/design-principles.md` short enough for future agents to actually
  read before coding.
- Update this file when major milestones are completed.

## Stop Conditions

Pause and ask for review before continuing if:

- a change would alter default IPv4 output;
- a service appears to require a new public API rather than helper usage;
- generated runtime behavior differs between BIRD and FRR in a way the design
  docs do not explain;
- a migration touches SCION, k8s, internetmap2, OpenVPN, or email delivery
  semantics;
- tests pass statically but runtime daemon state cannot prove the feature.
