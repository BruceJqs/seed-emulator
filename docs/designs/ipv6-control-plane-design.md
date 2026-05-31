# IPv6 Control Plane Design

This branch adds optional dual-stack IPv6 support to the SEED control plane. IPv4 remains the default. IPv6 is enabled explicitly through `Base(enableIpv6=True, ipv6RootPrefix="2000::/12")` or `base.enableIpv6(...)`.

## Core Shape

The core model keeps the existing IPv4 API stable and adds IPv6 fields beside it.

| Concern | IPv4 API kept | IPv6 API added |
| --- | --- | --- |
| Network prefix | `Network.getPrefix()` | `Network.getIpv6Prefix()`, `Network.hasIpv6Prefix()` |
| Interface address | `Interface.getAddress()` | `Interface.getIpv6Address()`, `Interface.hasIpv6Address()` |
| Node attachment | `joinNetwork(net, address="auto")` | optional `ipv6Address="auto"|None|explicit` |
| AS network | `createNetwork(..., prefix="auto")` | optional `ipv6Prefix="auto"|None|explicit` |
| IX network | `createInternetExchange(..., prefix="auto")` | optional `ipv6Prefix`, `rsIpv6Address` |

This avoids breaking existing examples and services that expect IPv4 objects from `getPrefix()` and `getAddress()`.

## Address Plan

`Ipv6Addressing` owns deterministic IPv6 allocation.

- Root prefix defaults to `2000::/12`.
- AS allocation uses stable `/48` prefixes.
- AS local networks use `/64` prefixes under the AS `/48`.
- IX peering LANs use stable `/64` prefixes under the same root.
- Host/router/route-server interface IDs reuse the existing `AddressAssignmentConstraint` offsets, so old assignment intent stays recognizable.
- If an ASN or IX id collides in the auto allocator, the allocator advances deterministically and asserts if the root is exhausted.

The `2000::/12` prefix is an emulation public-style default, not a claim that generated routes are globally reachable.

## Control Plane Flow

The branch keeps the control-plane boundary from the FRR/ExaBGP/Looking Glass work.

```text
Base / AS / IX
-> Network + Interface carry optional IPv6 state
-> Ebgp / Ibgp / Ospf record address-family intent
-> _bgp_metadata normalizes BGP sessions and OSPF interface intent
-> Routing renders BIRD or FRR syntax
-> Docker compiler emits dual-stack compose networks and container addresses
```

Important rule: protocol layers do not write daemon-specific IPv6 syntax. BIRD/FRR syntax stays in `Routing`.

## BIRD and FRR Rendering

BIRD:

- keeps IPv4 `t_direct`, `t_ospf`, and `t_bgp`;
- adds IPv6 `t_direct6`, `t_ospf6`, and `t_bgp6` only when IPv6 is present;
- renders BGP family blocks from the same session intent;
- renders OSPFv3 as a separate IPv6 OSPF protocol/table.

FRR:

- keeps OSPFv2 and IPv4 BGP behavior;
- enables `ospf6d` for IPv6 routers;
- renders `address-family ipv6 unicast`;
- renders OSPFv3 interface commands for IPv6-capable interfaces.

## Services

ExaBGP remains a service speaker. It resolves the shared network with the peer router, installs router-side BGP intent, and writes `/etc/exabgp/exabgp.conf` with `ipv6 unicast` when IPv6 is available or IPv6 prefixes are announced.

Looking Glass remains a route-state observer. The proxy queries BIRD route state through `birdc` and FRR route state through `vtysh`, including IPv6 BGP and OSPFv3 commands.

## Examples and Validation

| Example | Purpose | Evidence |
| --- | --- | --- |
| `A15_bgp_ipv6_dual_stack` | BIRD/FRR mixed dual-stack BGP with OSPFv2/OSPFv3 | IPv6 compose IPAM, `ip -6 addr`, `birdc show route all`, FRR `show bgp ipv6 unicast`, `show ipv6 ospf6 neighbor` |
| `A16_exabgp_ipv6_control_plane` | ExaBGP IPv6 static/live announce | `exabgp.conf` has `ipv6 unicast`, peer learns and withdraws IPv6 prefixes |
| `A17_ipv6_looking_glass` | IPv6 route-state observability | Looking Glass `/api/state` includes BIRD and FRR IPv6 route-state |

Existing A12-A14 remain the IPv4 regression baseline.
