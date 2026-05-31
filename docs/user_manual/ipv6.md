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

User-provided IPv6 prefixes under the root are normalized and reserved before
later automatic allocation. Padded CIDR strings and bracketed IPv6 literals are
accepted consistently across root, AS network, IX LAN, and service-network
prefix inputs. Overlapping explicit AS/IX prefixes are rejected, and automatic
allocation skips claimed prefixes instead of reusing them.

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

Explicit IPv4 and IPv6 interface address literals are normalized before being
stored. Padded values and bracketed IPv6 literals such as
`ipv6Address="[2000:0:150::71]"` are accepted, while `getAddress()` remains the
IPv4 accessor and `getIpv6Address()` remains the IPv6 accessor.

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

Manual BGP session intent accepts the same address-family aliases and address
literal normalization as services. Padded IPv4/IPv6 values and bracketed IPv6
literals are canonicalized before BIRD/FRR/ExaBGP config is rendered.

See [routing.md](./routing.md) for backend selection and
[IPv6 Addressing and Control Plane Design](../designs/ipv6-control-plane-design.md)
for the design boundary.

## Docker Compiler

The Docker compiler emits IPv6 runtime configuration only for networks that
have IPv6 prefixes. Dual-stack networks include `enable_ipv6: true`, IPv6 IPAM,
and service-level `ipv6_address` entries only for interfaces carrying IPv6
state. Interfaces that opt out with `ipv6Address=None` remain IPv4-only even on
a dual-stack service network. Custom container and Internet Map attachments
follow the same explicit-address rule: a dual-stack network does not imply a
static per-container `ipv6_address` unless `ipv6_address` is provided.

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
- baseline dual-stack: DNS authoritative and reverse records, and `/etc/hosts`;
- compatible but not fully migrated: DNS cache, Domain Registrar dynamic A/AAAA
  updates, Web/CA, traffic wrappers, Kubo bootstrap endpoints, Botnet
  C2/dropper endpoint formatting, Monero seed/RPC endpoint formatting,
  Chainlink generated URL formatting, Ethereum faucet/utility, faucet-user,
  and bootnode/beacon helper HTTP URL formatting;
- IPv4-first pending design: Email; Cymru IP origin ASN mapping remains
  IPv4-only with normalized IPv4 prefix inputs; Tor remains IPv4-first with
  directory-authority downloader and hidden-service backend target formatting
  guarded by shared endpoint helpers;
- separate design required: SCION underlay, cross-connect, DHCPv6, MPLS/EVPN,
  real-world connectivity, OpenVPN, k8s, internetmap2.

Reverse DNS preserves existing IPv4 `in-addr.arpa.` PTR generation. When
interfaces carry IPv6 state, `ReverseDomainNameService` also populates
`ip6.arpa.` PTR records; IPv4-only topologies do not create the IPv6 reverse
zone.

Domain Registrar dynamic updates preserve A as the default record type. The
registration page also allows users to explicitly choose AAAA records for IPv6
addresses. The registrar still follows the existing TLD/master-DNS placement
model; this is not a broader DNS workflow redesign.

Traffic generators preserve existing raw receiver target lists. For explicit
address-family selection, use `addReceiverVnodes(..., family=AddressFamily.IPv6)`
to resolve receiver virtual nodes through the shared node-address helpers.

Kubo bootstrap endpoints preserve IPv4 defaults and select bootstrap node
addresses through the shared Local-network-first helper, falling back to the
service network when a bootstrap node has no Local interface. The legacy Kubo
`getIP` utility follows the same rule: IPv4 remains the default, and callers
may explicitly request IPv6. For explicit IPv6 bootstrap RPC URLs and peer
multiaddrs, use
`KuboService(bootstrapAddressFamily=AddressFamily.IPv6)` or
`setBootstrapAddressFamily(AddressFamily.IPv6)`.

Botnet C2/dropper endpoints preserve the existing first-interface IPv4
default. In a dual-stack emulation, call
`BotnetServer.setEndpointAddressFamily(AddressFamily.IPv6)` to generate a
bracketed IPv6 dropper URL for binding-based clients. DGA dropper runners may
consume preformatted HTTP(S) URLs without adding their own host/path wrapper,
but BYOB client/server runtime behavior and DGA endpoints have not been
validated as full IPv6 support.

Looking Glass route-state observation remains separate from ExaBGP event
dashboards. Its frontend-to-proxy traffic preserves the IPv4 default. In a
dual-stack emulation, call
`BgpLookingGlassServer.setProxyAddressFamily(AddressFamily.IPv6)` to generate
bracketed IPv6 proxy URLs for the frontend; this selects only the management
endpoint family, not the set of route families queried from the router.

CA certificate installation filters accept IPv4 and IPv6 address/prefix
selectors. For example, `installCACert(Filter(ipv6="2000:0:3::72"))` installs
the root CA certificate only on nodes with that IPv6 address; CA address and
prefix matching, including helper utilities, normalize padded and bracketed
IPv6 literals through the shared address helpers. CA domain inputs trim DNS
names and normalize padded or bracketed IPv4/IPv6 endpoint literals before Web
HTTPS ACME directory URLs use shared URL helpers, but Web HTTPS and ACME runtime
behavior remain compatible and not fully migrated.

Monero seed and full-node RPC endpoint lists preserve IPv4 defaults and select
node addresses through the shared Local-network-first helper, falling back to
the service network when a node has no Local interface. In a dual-stack
emulation, call `blockchain.setEndpointAddressFamily(AddressFamily.IPv6)` to
generate bracketed IPv6 `host:port` endpoints for those lists. Monero daemon
listener behavior has not been runtime-validated as full IPv6 support.

Chainlink generated URLs preserve IPv4 defaults and select referenced Ethereum,
faucet, and utility endpoints through the shared Local-network-first helper,
falling back to the service network when a referenced node has no Local
interface. In a dual-stack emulation, call
`chainlink.setEndpointAddressFamily(AddressFamily.IPv6)` or pass
`endpointAddressFamily=AddressFamily.IPv6` to generate bracketed IPv6 RPC,
faucet, utility, and WebSocket/HTTP node URLs. The underlying Ethereum and
Chainlink runtime path has not been validated as full IPv6 support.

Ethereum faucet/utility generated URLs, faucet-user request URLs, faucet
funding-script server URLs, and bootnode/beacon helper fetch URLs preserve IPv4
defaults and select referenced nodes through the shared Local-network-first
helper, falling back to the service network when a referenced node has no Local
interface. In a dual-stack emulation, call
`blockchain.setEndpointAddressFamily(AddressFamily.IPv6)` or
`faucetUserService.setEndpointAddressFamily(AddressFamily.IPv6)` to generate
bracketed IPv6 HTTP RPC, faucet, enode-fetch, beacon-identity, and beacon-setup
helper URLs. The Lighthouse validator beacon-node URL template accepts a
preformatted helper URL so IPv6 literals are bracketed when supplied, but the
current PoS validator install path remains IPv4-first. Ethereum ENR content,
peer discovery, bootnode bind/listener, and daemon runtime behavior have not
been runtime-validated as full IPv6 support.

Tor remains IPv4-first. Directory-authority fingerprint downloader URLs and
hidden-service backend targets use shared endpoint helpers so explicit IPv6
literals are normalized and bracketed correctly without bracketing DNS names.
Hidden-service backends linked with `linkByVnode(...,
family=AddressFamily.IPv6)` resolve through the shared Local-network-first
helper and fall back to the service network when the backend node has no Local
interface. Tor bind/listener, directory authority, consensus, and daemon
runtime behavior still require a separate migration.

See
[Repository-Wide IPv6 Readiness Design](../designs/ipv6-repository-readiness-design.md)
for the migration contract.

## Service Author Rules

Keep `getAddress()` and `getPrefix()` as IPv4-only APIs. A service that needs
IPv6 should use `hasIpv6Address()`, `getIpv6Address()`, or the shared helpers in
`seedemu.core`:

```python
from seedemu.core import (
    AddressFamily,
    getInterfaceAddress,
    getNodeAddress,
    getNodeAddresses,
    getNodePreferredAddress,
    nodeHasAddress,
    nodeHasAddressInPrefix,
    formatHostPort,
    formatUrl,
    formatMultiaddr,
    normalizeAddressList,
    normalizePrefix,
    normalizeAddressRecord,
)
```

Use `formatHostPort()` or `formatUrl()` instead of manually concatenating
`host:port`, because IPv6 literals need brackets in URLs. Use
`formatMultiaddr()` when generating IPFS/libp2p multiaddrs. Use
`getNodeAddress()`, `getNodePreferredAddress()`, or `getNodeAddresses()` when a
service needs stable Local-network-first address selection with service-network
fallback. Use `nodeHasAddress()` and `nodeHasAddressInPrefix()` when matching a
node against IPv4 or IPv6 address/prefix selectors. Use
`normalizeAddressList()` when a service accepts a list of IPv4/IPv6 literals,
including bracketed IPv6 address literals. Use `normalizePrefix()` when a
service accepts IPv4/IPv6 CIDR prefixes, and use `normalizeAddressRecord()` when
a service accepts DNS-style manual A/AAAA records and needs canonical IPv4/IPv6
literals without changing other record types.

Do not claim service-level IPv6 support until the service has a minimal IPv6 or
dual-stack example and a regression check showing that old IPv4 behavior is
unchanged.
