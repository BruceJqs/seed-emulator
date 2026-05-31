from __future__ import annotations

from enum import Enum
from ipaddress import ip_address
from typing import Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .Node import Interface


class AddressFamily(Enum):
    """Address-family selector used by dual-stack aware services."""

    IPv4 = "ipv4"
    IPv6 = "ipv6"


def normalizeAddressFamily(family: Union[AddressFamily, str, int]) -> AddressFamily:
    """Normalize common address-family spellings to AddressFamily."""

    if isinstance(family, AddressFamily):
        return family

    value = str(family).lower()
    if value in ("4", "ip4", "ipv4", "v4"):
        return AddressFamily.IPv4
    if value in ("6", "ip6", "ipv6", "v6"):
        return AddressFamily.IPv6

    raise ValueError("unsupported address family {}".format(family))


def getInterfaceAddress(iface: "Interface", family: Union[AddressFamily, str, int] = AddressFamily.IPv4):
    """Return an interface address for the requested address family."""

    selected = normalizeAddressFamily(family)
    if selected == AddressFamily.IPv4:
        return iface.getAddress()
    return iface.getIpv6Address() if iface.hasIpv6Address() else None


def hasInterfaceAddress(iface: "Interface", family: Union[AddressFamily, str, int] = AddressFamily.IPv4) -> bool:
    """Check if an interface has an address for the requested address family."""

    return getInterfaceAddress(iface, family) is not None


def formatHost(host: Union[str, object]) -> str:
    """Format a host/address for endpoint strings, bracketing IPv6 literals."""

    value = str(host)
    try:
        parsed = ip_address(value)
    except ValueError:
        return value

    if parsed.version == 6:
        return "[{}]".format(value)
    return value


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

    parsed = ip_address(str(host))
    proto = "ip6" if parsed.version == 6 else "ip4"
    out = "/{}/{}/tcp/{}".format(proto, parsed, tcpPort)
    if peerId is not None:
        out += "/p2p/{}".format(peerId)
    return out
