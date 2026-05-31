# Repository-Wide IPv6 Readiness Design

This document defines how SEED Emulator should evolve from IPv4-first
examples to optional dual-stack capability across the repository. The current
branch already provides the control-plane foundation: core topology objects,
Docker compilation, BIRD/FRR, ExaBGP, and Looking Glass can carry IPv6 when a
scenario explicitly enables it. This document is the migration contract for
the rest of the repository.

## 中文摘要

IPv6 不应该被理解成几个示例的局部能力，而是仿真器级别的可选能力。
默认仍然是 IPv4-only；旧示例、旧 API、旧输出都应保持稳定。只有用户在
`Base`、网络、接口或相关 service API 中显式启用 IPv6，编译结果才进入
双栈状态。

全仓库迁移遵守下面的边界：

- core 保存拓扑、地址、前缀、绑定和 endpoint 的通用语义；
- layer 只表达协议或系统 intent；
- service 读取地址族能力并生成自身配置；
- compiler 把已经存在的模型状态编译成运行制品；
- examples 用新增 IPv6 variant 展示新能力，不改旧示例含义。

## Address-Family Contract

Existing IPv4 APIs remain IPv4 APIs:

- `Network.getPrefix()` returns the IPv4 prefix.
- `Interface.getAddress()` returns the IPv4 address.
- `Filter(ip=...)` and `Filter(prefix=...)` remain accepted and now parse either
  IPv4 or IPv6 literals.

Dual-stack aware code should use the explicit IPv6 APIs or the shared helpers:

- `Network.hasIpv6Prefix()` / `Network.getIpv6Prefix()`.
- `Interface.hasIpv6Address()` / `Interface.getIpv6Address()`.
- `AddressFamily`, `getInterfaceAddress(...)`, `formatHostPort(...)`,
  `getNodeAddress(...)`, `getNodeAddresses(...)`, `getNodePreferredAddress(...)`,
  `formatUrl(...)`, and `formatMultiaddr(...)` from `seedemu.core`.

Services must not assume that the first interface address is the only usable
address. A service should either select IPv4 explicitly, select IPv6
explicitly, or generate both families when its daemon supports dual stack.

## Core Readiness

Implemented foundation:

- Optional IPv6 root prefix and deterministic AS/IX `/64` allocation.
- IPv6 state on `Network` and `Interface`.
- IPv6-aware BGP/OSPF intent rendering for BIRD and FRR.
- IPv6-aware ExaBGP speaker service and Looking Glass route-state queries.
- Docker Compose dual-stack network/IPAM and service `ipv6_address` output.
- IPv6-aware `Filter` / `Binding` matching and `Action.NEW` placement.
- Optional IPv6 service network prefix, with per-node `ipv6_address` emitted
  only for service-network attachments that carry IPv6 state.
- Optional IPv6 address on `attachCustomContainer(...)` and
  `attachInternetMap(...)`.

Deferred core items:

- `crossConnect(...)` remains IPv4-only in this branch. It is used heavily by
  SCION and legacy examples, so dual-stack cross-connect links need a separate
  design rather than an implicit API change.
- Real-world connectivity and OpenVPN remain IPv4-oriented.
- DHCP remains IPv4-only; DHCPv6/SLAAC behavior should be designed separately.

## Service Readiness Matrix

| Area | Status | Migration rule |
| --- | --- | --- |
| Routing control plane | Supported | Keep protocol intent family-aware; render backend syntax only in `Routing`. |
| ExaBGP | Supported | Service speaker may use IPv4 or IPv6 shared peer address. |
| Looking Glass | Supported | Route-state views separate IPv4/IPv6 output. |
| Docker compiler | Supported | Emit IPv6 only for networks/interfaces carrying IPv6 state. |
| `/etc/hosts` | Baseline dual-stack | Generate IPv4 and IPv6 local entries when available. |
| DNS authoritative | Baseline dual-stack | Generate A and AAAA for node-backed records; masters may include both families; reverse DNS keeps IPv4 `in-addr.arpa.` PTR records and adds `ip6.arpa.` PTR records only when interfaces carry IPv6 state. |
| DNS cache | Compatible | Prefer IPv4 for old resolver behavior; accept IPv6 forwarders/root hints. |
| Web/CA | Compatible | Existing IPv4 behavior preserved; CA certificate-install filters match IPv4/IPv6 address and prefix selectors; ACME directory URLs use shared URL helpers and can bracket explicit IPv6 CA endpoint literals, but Web HTTPS and ACME runtime behavior still need validation before a full support claim. |
| Traffic services | Compatible | Raw receiver targets are unchanged; receiver vnodes can be resolved to IPv4 or IPv6 targets through shared node-address helpers, but each tool still needs runtime validation before a full support claim. |
| Kubo/IPFS | Compatible | Bootstrap RPC URLs and peer multiaddrs use shared endpoint helpers, default to IPv4, and may explicitly select IPv6; broader Kubo runtime behavior still needs validation before a full support claim. |
| Botnet | Compatible | Binding-based C2/dropper URLs use shared node-address and URL helpers, preserve the first-interface IPv4 default, and may explicitly select bracketed IPv6 URLs; BYOB client/server runtime behavior and DGA endpoints still need validation before a full support claim. |
| Monero | Compatible | Seed and full-node RPC endpoint lists use shared address-family and host-port helpers, default to IPv4, and may explicitly select IPv6; daemon listener/runtime behavior still needs validation before a full support claim. |
| Chainlink | Compatible | Generated Chainlink RPC, faucet, utility, and node WebSocket/HTTP URLs use shared endpoint helpers, default to IPv4, and may explicitly select bracketed IPv6 URLs; Ethereum/Chainlink runtime behavior still needs validation before a full support claim. |
| Email | IPv4-first | Provider/gateway/default-route logic must be redesigned before IPv6 claim. |
| Tor | IPv4-first | Directory-authority downloader URLs and hidden-service backend target formatting are helper-ready, but bind/listener, directory authority addressing, consensus, and daemon runtime need a separate migration before an IPv6 support claim. |
| Ethereum | Compatible | Faucet and utility HTTP URLs use shared endpoint helpers, default to IPv4, and may explicitly select bracketed IPv6; ENR, bootnode, peer discovery, and daemon runtime behavior still need validation before a full support claim. |
| SCION | Separate design | Underlay, crossConnect, and SCION control tooling currently assume IPv4. |
| MPLS/EVPN | Separate design | Routing identifiers and dataplane assumptions need dedicated validation. |
| k8s/internetmap2 | Out of this branch | Do not claim IPv6 support until their own branch validates it. |

## Migration Pattern for Services

A service migration should follow this order:

1. Keep the old IPv4 path unchanged.
2. Add explicit address-family selection or generate both families only when
   the target node/interface has IPv6 state.
3. Use shared endpoint helpers for URLs, `host:port`, and multiaddr strings.
4. Add a minimal IPv6 example or test without changing old examples.
5. Document unsupported daemon features clearly instead of generating partial
   IPv6 config.

The acceptance rule is simple: enabling IPv6 must not make an IPv4-only service
silently wrong. It may continue using IPv4, or it may clearly expose dual-stack
support after tests prove it.

## Validation Baseline

Repository-level IPv6 work should keep these checks green:

- Existing IPv4 examples compile without IPv6 Compose fields.
- A15-A17 keep proving the control-plane path.
- `Filter` / `Binding` match IPv4 and IPv6 addresses/prefixes.
- IPv6 prefix allocation rejects reserved infrastructure reuse and overlapping
  explicit AS/IX prefixes, including late `Base.enableIpv6()` migration paths.
- Service network and custom containers compile as IPv4-only by default and
  dual-stack only when IPv6 is provided; service-network interface opt-out,
  custom container attachments, and custom Internet Map attachments without an
  explicit IPv6 address suppress per-node `ipv6_address` even on a dual-stack
  network.
- DNS and `/etc/hosts` emit stable A/AAAA and hosts entries when IPv6 exists.
- DNS address selection uses shared core helpers so service code does not
  duplicate Local-vs-service-network fallback rules.
