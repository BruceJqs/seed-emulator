from __future__ import annotations

from enum import Enum
from ipaddress import ip_address, ip_network
from typing import Iterable, List, Optional, TYPE_CHECKING, Tuple, Union

from .enums import NetworkType

if TYPE_CHECKING:
    from .Node import Interface, Node


class AddressFamily(Enum):
    """Address-family selector used by dual-stack aware services."""

    IPv4 = "ipv4"
    IPv6 = "ipv6"


def normalizeAddressFamily(family: Union[AddressFamily, str, int]) -> AddressFamily:
    """Normalize common address-family spellings to AddressFamily."""

    if isinstance(family, AddressFamily):
        return family

    value = str(family).strip().lower()
    if value in ("2", "4", "af_inet", "inet", "ip4", "ipv4", "v4"):
        return AddressFamily.IPv4
    if value in ("6", "10", "af_inet6", "inet6", "ip6", "ipv6", "v6"):
        return AddressFamily.IPv6

    raise ValueError("unsupported address family {}".format(family))


def normalizeAddressList(addrs: Iterable[Union[str, object]]) -> List[str]:
    """Normalize IPv4/IPv6 address literals while preserving list order."""

    return [str(ip_address(str(addr).strip())) for addr in addrs]


def normalizeAddressRecord(record: Union[str, object], trimNonAddressRecord: bool = False) -> str:
    """Normalize DNS-style A/AAAA record address literals.

    Non-address records are returned unchanged unless trimNonAddressRecord is
    set for callers whose historical API already trimmed those records.
    """

    value = str(record)
    parts = value.strip().split()
    if len(parts) >= 3 and parts[-2].upper() in ("A", "AAAA"):
        parts[-2] = parts[-2].upper()
        parts[-1] = str(ip_address(parts[-1]))
        return " ".join(parts)
    return value.strip() if trimNonAddressRecord else value


def _parseHostIpLiteral(host: Union[str, object]):
    value = str(host).strip()
    candidate = value
    if value.startswith("[") and value.endswith("]"):
        candidate = value[1:-1].strip()

    try:
        return ip_address(candidate)
    except ValueError:
        return None


def getInterfaceAddress(iface: "Interface", family: Union[AddressFamily, str, int] = AddressFamily.IPv4):
    """Return an interface address for the requested address family."""

    selected = normalizeAddressFamily(family)
    if selected == AddressFamily.IPv4:
        return iface.getAddress()
    return iface.getIpv6Address() if iface.hasIpv6Address() else None


def hasInterfaceAddress(iface: "Interface", family: Union[AddressFamily, str, int] = AddressFamily.IPv4) -> bool:
    """Check if an interface has an address for the requested address family."""

    return getInterfaceAddress(iface, family) is not None


def nodeHasAddress(node: "Node", address: Union[str, object]) -> bool:
    """Check whether a node has an IPv4 or IPv6 address literal."""

    requested = ip_address(str(address).strip())
    family = AddressFamily.IPv4 if requested.version == 4 else AddressFamily.IPv6
    for iface in node.getInterfaces():
        iface_addr = getInterfaceAddress(iface, family)
        if iface_addr is not None and str(iface_addr) == str(requested):
            return True
    return False


def nodeHasAddressInPrefix(node: "Node", prefix: Union[str, object]) -> bool:
    """Check whether any node address is inside an IPv4 or IPv6 prefix."""

    network = ip_network(str(prefix).strip())
    family = AddressFamily.IPv4 if network.version == 4 else AddressFamily.IPv6
    for iface in node.getInterfaces():
        iface_addr = getInterfaceAddress(iface, family)
        if iface_addr is not None and iface_addr in network:
            return True
    return False


def _getNodeAddressCandidates(node: "Node"):
    ifaces = node.getInterfaces()
    assert len(ifaces) > 0, "Node {} has no IP address.".format(node.getName())

    local_ipv4 = None
    local_ipv6 = None
    fallback_ipv4 = None
    fallback_ipv6 = None

    for iface in ifaces:
        ipv4_addr = getInterfaceAddress(iface, AddressFamily.IPv4)
        ipv6_addr = getInterfaceAddress(iface, AddressFamily.IPv6)

        if fallback_ipv4 is None and ipv4_addr is not None:
            fallback_ipv4 = ipv4_addr
        if fallback_ipv6 is None and ipv6_addr is not None:
            fallback_ipv6 = ipv6_addr

        if iface.getNet().getType() == NetworkType.Local:
            if local_ipv4 is None and ipv4_addr is not None:
                local_ipv4 = ipv4_addr
            if local_ipv6 is None and ipv6_addr is not None:
                local_ipv6 = ipv6_addr

    return {
        "local": {
            AddressFamily.IPv4: local_ipv4,
            AddressFamily.IPv6: local_ipv6,
        },
        "fallback": {
            AddressFamily.IPv4: fallback_ipv4,
            AddressFamily.IPv6: fallback_ipv6,
        },
    }


def getNodeAddresses(node: "Node", preferLocal: bool = True) -> Tuple[object, object]:
    """Return preferred IPv4 and IPv6 addresses for a node.

    Local-network interfaces are preferred by default. When a requested family
    has no local address, the first address from any interface is returned.
    """

    candidates = _getNodeAddressCandidates(node)
    if not preferLocal:
        return (
            candidates["fallback"][AddressFamily.IPv4],
            candidates["fallback"][AddressFamily.IPv6],
        )

    local_ipv4 = candidates["local"][AddressFamily.IPv4]
    local_ipv6 = candidates["local"][AddressFamily.IPv6]
    fallback_ipv4 = candidates["fallback"][AddressFamily.IPv4]
    fallback_ipv6 = candidates["fallback"][AddressFamily.IPv6]
    return (local_ipv4 or fallback_ipv4, local_ipv6 or fallback_ipv6)


def getNodeAddress(
    node: "Node",
    family: Union[AddressFamily, str, int] = AddressFamily.IPv4,
    preferLocal: bool = True,
):
    """Return the node address for one address family."""

    selected = normalizeAddressFamily(family)
    candidates = _getNodeAddressCandidates(node)
    if not preferLocal:
        return candidates["fallback"][selected]
    return candidates["local"][selected] or candidates["fallback"][selected]


def getNodePreferredAddress(
    node: "Node",
    families: Iterable[Union[AddressFamily, str, int]] = (AddressFamily.IPv4, AddressFamily.IPv6),
    preferLocal: bool = True,
):
    """Return the first available node address in the requested family order."""

    selected_families = [normalizeAddressFamily(family) for family in families]
    candidates = _getNodeAddressCandidates(node)
    scopes = ("local", "fallback") if preferLocal else ("fallback",)
    for scope in scopes:
        for family in selected_families:
            address = candidates[scope][family]
            if address is not None:
                return address
    return None


def formatHost(host: Union[str, object]) -> str:
    """Format a host/address for endpoint strings, bracketing IPv6 literals."""

    value = str(host).strip()
    parsed = _parseHostIpLiteral(value)
    if parsed is None:
        return value

    if parsed.version == 6:
        return "[{}]".format(parsed)
    return str(parsed)


def formatHostPort(host: Union[str, object], port: Union[str, int]) -> str:
    """Format host:port with RFC 3986 brackets for IPv6 literals."""

    return "{}:{}".format(formatHost(host), port)


def formatUrl(
    scheme: str,
    host: Union[str, object],
    port: Optional[Union[str, int]] = None,
    path: str = "",
) -> str:
    """Format a URL from address-family neutral pieces."""

    authority = formatHost(host) if port is None else formatHostPort(host, port)
    if path and not path.startswith("/"):
        path = "/" + path
    return "{}://{}{}".format(scheme, authority, path)


def formatMultiaddr(host: Union[str, object], tcpPort: Union[str, int], peerId: str = None) -> str:
    """Format an IPFS/libp2p style multiaddr for IPv4 or IPv6 literals."""

    parsed = _parseHostIpLiteral(host)
    if parsed is None:
        raise ValueError("multiaddr host must be an IPv4/IPv6 literal: {}".format(host))

    proto = "ip6" if parsed.version == 6 else "ip4"
    out = "/{}/{}/tcp/{}".format(proto, parsed, tcpPort)
    if peerId is not None:
        out += "/p2p/{}".format(peerId)
    return out
