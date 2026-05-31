# IPv6 Dual-Stack Emulation

IPv6 support is optional. Existing emulations stay IPv4-only unless the base
layer enables IPv6 explicitly. When IPv6 is enabled, the emulator keeps the
existing IPv4 APIs and adds IPv6 state beside them.

```python
base = Base(enableIpv6=True)
```

Users may also enable IPv6 after building the base topology, as long as this is
done before rendering:

```python
base = Base()
as150 = base.createAutonomousSystem(150)
as150.createNetwork("net0")
base.createInternetExchange(100)

base.enableIpv6()
```

## Address Plan

The default IPv6 root prefix is `2000::/12`. It is a public-style emulation
prefix; it does not claim that generated routes are globally reachable outside
the emulator. Users can override the root prefix:

```python
base = Base(enableIpv6=True, ipv6RootPrefix="2000::/12")
```

Automatic allocation uses the following plan:

- one stable `/48` per AS;
- one stable `/64` per AS local network;
- one stable `/64` per Internet Exchange peering LAN;
- `2000:ffff::/48` is reserved for routing infrastructure, such as loopback
  addresses used by the `Routing` layer.

IPv6 address assignment follows the existing `AddressAssignmentConstraint`
intent. Hosts use the host offset range, routers use the router offset range,
and IX participants prefer ASN-derived offsets.

## Network and Interface APIs

The existing IPv4 accessors remain IPv4-only:

```python
network.getPrefix()
interface.getAddress()
```

Use the IPv6 accessors when dual-stack state is needed:

```python
network.hasIpv6Prefix()
network.getIpv6Prefix()
interface.hasIpv6Address()
interface.getIpv6Address()
```

## Per-Network Control

With global IPv6 enabled, local AS networks and IX peering LANs use automatic
IPv6 prefixes by default.

```python
as150.createNetwork("net0")
base.createInternetExchange(100)
```

Users can override or disable IPv6 on a specific network:

```python
as150.createNetwork("explicit", ipv6Prefix="2000:0:150::/64")
as150.createNetwork("v4only", ipv6Prefix=None)
base.createInternetExchange(200, ipv6Prefix="2000:8:0:200::/64")
```

## Per-Interface Control

`joinNetwork()` also accepts an IPv6 address intent. The default is `"auto"`.
Use `None` for an IPv4-only attachment on a dual-stack network, or provide an
explicit IPv6 address.

```python
as150.createHost("web").joinNetwork("net0")
as150.createHost("legacy").joinNetwork("net0", ipv6Address=None)
as150.createHost("fixed").joinNetwork("net0", ipv6Address="2000:0:150::71")
```

## Routing

The routing layers remain intent based. `Ebgp`, `Ibgp`, and `Ospf` record
peering and interface intent. The `Routing` layer renders address-family
specific BIRD or FRR configuration.

When IPv6 is present:

- BIRD receives IPv6 routing tables and IPv6 BGP/OSPFv3 blocks as needed;
- FRR receives `address-family ipv6 unicast` and OSPFv3 configuration as
  needed;
- OSPFv2 and OSPFv3 stay separate;
- ExaBGP can announce IPv6 prefixes when the speaker and peer share IPv6 on the
  peering network;
- Looking Glass can report IPv4 and IPv6 route-state separately.

See [routing.md](./routing.md) for backend selection and
[IPv6 Addressing and Control Plane Design](../designs/ipv6-control-plane-design.md)
for the design boundary.

## Docker Compiler

The Docker compiler emits IPv6 runtime configuration only for networks that
have IPv6 prefixes. Dual-stack networks include `enable_ipv6: true`, IPv6 IPAM,
and service-level `ipv6_address` entries.

For `selfManagedNetwork=True`, the compiler uses dummy IPv6 subnets and rewrites
container addresses at startup, matching the existing IPv4 self-managed network
behavior.

## Repository Readiness

IPv6 support is being expanded as a repository-level contract. The control
plane, Docker compiler, ExaBGP, Looking Glass, DNS baseline, and `/etc/hosts`
now have explicit dual-stack behavior. Other services remain IPv4-compatible
until each service is migrated and tested.

Current categories:

- supported: core addressing, Docker dual-stack networks, BIRD/FRR BGP,
  OSPFv3, ExaBGP, Looking Glass;
- baseline dual-stack: DNS authoritative records and `/etc/hosts`;
- compatible but not fully migrated: DNS cache, Web/CA, traffic wrappers;
- IPv4-first pending design: Email, Kubo, Tor, Ethereum, Monero, Chainlink;
- separate design required: SCION underlay, cross-connect, DHCPv6, MPLS/EVPN,
  real-world connectivity, OpenVPN, k8s, internetmap2.

See
[Repository-Wide IPv6 Readiness Design](../designs/ipv6-repository-readiness-design.md)
for the migration contract.

## Service Author Rules

Keep `getAddress()` and `getPrefix()` as IPv4-only APIs. A service that needs
IPv6 should use `hasIpv6Address()`, `getIpv6Address()`, or the shared helpers in
`seedemu.core`:

```python
from seedemu.core import AddressFamily, getInterfaceAddress, formatHostPort, formatUrl, formatMultiaddr
```

Use `formatHostPort()` or `formatUrl()` instead of manually concatenating
`host:port`, because IPv6 literals need brackets in URLs. Use
`formatMultiaddr()` when generating IPFS/libp2p multiaddrs.

Do not claim service-level IPv6 support until the service has a minimal IPv6 or
dual-stack example and a regression check showing that old IPv4 behavior is
unchanged.
