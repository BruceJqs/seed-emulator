from __future__ import annotations

import importlib.util
import socket
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent
CORE = ROOT / "seedemu" / "core"


def _load_core_module(name: str, filename: str):
    """Load a core module without importing top-level seedemu optional deps."""

    package_name = "seedemu"
    core_name = "seedemu.core"
    if package_name not in sys.modules:
        package_spec = importlib.util.spec_from_loader(package_name, loader=None, is_package=True)
        package = importlib.util.module_from_spec(package_spec)
        package.__path__ = [str(ROOT / "seedemu")]
        sys.modules[package_name] = package

    if core_name not in sys.modules:
        core_spec = importlib.util.spec_from_loader(core_name, loader=None, is_package=True)
        core = importlib.util.module_from_spec(core_spec)
        core.__path__ = [str(CORE)]
        sys.modules[core_name] = core

    module_name = "{}.{}".format(core_name, name)
    if module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, CORE / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


Addressing = _load_core_module("Addressing", "Addressing.py")
Ipv6AddressingModule = _load_core_module("Ipv6Addressing", "Ipv6Addressing.py")

AddressFamily = Addressing.AddressFamily
Ipv6Addressing = Ipv6AddressingModule.Ipv6Addressing


def test_endpoint_helpers_preserve_ipv4_and_bracket_ipv6():
    assert Addressing.formatHost(" 10.0.0.1 ") == "10.0.0.1"
    assert Addressing.formatHost(" example.test ") == "example.test"
    assert Addressing.formatHost(" 2000:0:0::1 ") == "[2000::1]"
    assert Addressing.formatHost(" [2000:0:0::1]:8443 ") == "[2000::1]:8443"

    assert Addressing.formatHostPort("10.0.0.1", 80) == "10.0.0.1:80"
    assert Addressing.formatHostPort("2000::1", " 80 ") == "[2000::1]:80"
    assert Addressing.formatHostPort("[2000:0:0::1]:8443", 9443) == "[2000::1]:9443"

    assert Addressing.formatUrl("http", "10.0.0.1", 8080, "api") == "http://10.0.0.1:8080/api"
    assert Addressing.formatUrl("http", "2000::1", 8080, "?ready=1") == "http://[2000::1]:8080?ready=1"

    assert Addressing.formatMultiaddr("10.0.0.1", 4001) == "/ip4/10.0.0.1/tcp/4001"
    assert Addressing.formatMultiaddr("2000::1", " 4001 ", "peer") == "/ip6/2000::1/tcp/4001/p2p/peer"


def test_endpoint_helpers_reject_ambiguous_ports_and_authorities():
    with pytest.raises(ValueError):
        Addressing.formatHost("[2000::1]:bad")
    with pytest.raises(ValueError):
        Addressing.formatHostPort("2000::1", "")
    with pytest.raises(ValueError):
        Addressing.formatHostPort("2000::1", "http")
    with pytest.raises(ValueError):
        Addressing.formatMultiaddr("example.test", 4001)


def test_address_normalization_contracts():
    assert Addressing.normalizeAddressFamily(" ipv4 ") == AddressFamily.IPv4
    assert Addressing.normalizeAddressFamily(" IP6 ") == AddressFamily.IPv6
    assert Addressing.normalizeAddressFamily("inet") == AddressFamily.IPv4
    assert Addressing.normalizeAddressFamily("AF_INET6") == AddressFamily.IPv6
    assert Addressing.normalizeAddressFamily(socket.AF_INET) == AddressFamily.IPv4
    assert Addressing.normalizeAddressFamily(socket.AF_INET6) == AddressFamily.IPv6

    assert Addressing.normalizeAddressList([" 10.2.0.71 ", " [2000:0:2:0:0:0:0:71] "]) == [
        "10.2.0.71",
        "2000:0:2::71",
    ]
    assert Addressing.normalizePrefix(" [2000:0:2:0:0:0:0:0] / 64 ") == "2000:0:2::/64"
    assert Addressing.normalizePrefix(" 10.2.0.71/24 ", strict=False) == "10.2.0.0/24"

    assert Addressing.normalizeAddressRecord(" web a 10.2.0.71 ") == "web A 10.2.0.71"
    assert Addressing.normalizeAddressRecord(" web6 aaaa [2000:0:2:0:0:0:0:71] ") == "web6 AAAA 2000:0:2::71"
    assert Addressing.normalizeAddressRecord(" ns1. NS a.root.example. ", trimNonAddressRecord=True) == "ns1. NS a.root.example."
    with pytest.raises(ValueError):
        Addressing.normalizeAddressRecord("web A 2000:0:2::71")
    with pytest.raises(ValueError):
        Addressing.normalizeAddressRecord("web AAAA 10.2.0.71")


def test_ipv6_allocator_is_deterministic_and_avoids_claimed_prefixes():
    allocator = Ipv6Addressing(rootPrefix="2000::/12")

    assert str(allocator.getRootPrefix()) == "2000::/12"
    assert "2000:ffff::/48" in [str(prefix) for prefix in allocator.getReservedPrefixes()]
    assert str(allocator.assignAsPrefix(150)) == "2000:0:96::/48"
    assert str(allocator.nextAsNetworkPrefix(150)) == "2000:0:96::/64"
    assert str(allocator.assignIxPrefix(100)) == "2000:8:0:64::/64"

    claimed = Ipv6Addressing(rootPrefix="2000::/12")
    claimed.claimPrefix("2000:0:97::/48")
    assert str(claimed.assignAsPrefix(151)) != "2000:0:97::/48"


def test_ipv6_allocator_rejects_root_overlap_but_allows_disjoint_user_prefixes():
    allocator = Ipv6Addressing(rootPrefix="2000::/12")
    allocator.claimPrefix("fd00:1::/64")

    with pytest.raises(AssertionError):
        allocator.claimPrefix("2000::/11")

    with pytest.raises(AssertionError):
        allocator.claimPrefix("2000:ffff::/64")
