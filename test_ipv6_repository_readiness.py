from __future__ import annotations

from pathlib import Path

from seedemu.compiler import Docker, Platform
from seedemu.core import (
    Action,
    AddressFamily,
    Binding,
    Emulator,
    Filter,
    formatHostPort,
    formatMultiaddr,
    formatUrl,
    getNodeAddress,
    getNodeAddresses,
    getNodePreferredAddress,
)
from seedemu.layers import Base, EtcHosts
from seedemu.services import DomainNameCachingService, DomainNameService
import pytest


def _file_content(node, path: str) -> str:
    for file in node.getFiles():
        file_path, content = file.get()
        if file_path == path:
            return content
    return ""


def _compiled_output_text(output_dir: Path) -> str:
    chunks = []
    for path in output_dir.rglob("*"):
        if path.is_file():
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


def test_endpoint_helpers_format_ipv6_safely():
    assert formatHostPort("10.0.0.1", 80) == "10.0.0.1:80"
    assert formatHostPort("2000::1", 80) == "[2000::1]:80"
    assert formatUrl("http", "2000::1", 8080, "status") == "http://[2000::1]:8080/status"
    assert formatUrl("https", "example.test", path="/health") == "https://example.test/health"
    assert formatMultiaddr("10.0.0.1", 4001) == "/ip4/10.0.0.1/tcp/4001"
    assert formatMultiaddr("2000::1", 4001, "peer") == "/ip6/2000::1/tcp/4001/p2p/peer"


def test_node_address_helpers_prefer_local_then_fallback_by_family():
    emu = Emulator(serviceNetworkIpv6Prefix="fd00:66::/64")
    base = Base(enableIpv6=True)

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    host = (
        as2.createHost("host0")
        .joinNetwork("000_svc", address="192.168.66.10", ipv6Address="fd00:66::10")
        .joinNetwork("net0", address="10.2.0.10", ipv6Address="2000:0:2::10")
    )

    emu.getServiceNetwork()
    emu.addLayer(base)
    emu.render()

    local_ipv4, local_ipv6 = getNodeAddresses(host)
    first_ipv4, first_ipv6 = getNodeAddresses(host, preferLocal=False)

    assert str(local_ipv4) == "10.2.0.10"
    assert str(local_ipv6) == "2000:0:2::10"
    assert str(first_ipv4) == "192.168.66.10"
    assert str(first_ipv6) == "fd00:66::10"
    assert str(getNodeAddress(host, AddressFamily.IPv6)) == "2000:0:2::10"
    assert str(getNodePreferredAddress(host)) == "10.2.0.10"
    assert str(getNodePreferredAddress(host, (AddressFamily.IPv6, AddressFamily.IPv4))) == "2000:0:2::10"


def test_node_preferred_address_uses_local_ipv6_before_fallback_ipv4():
    emu = Emulator(serviceNetworkIpv6Prefix="fd00:66::/64")
    base = Base(enableIpv6=True)

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    host = (
        as2.createHost("host0")
        .joinNetwork("000_svc", address="192.168.66.10", ipv6Address="fd00:66::10")
        .joinNetwork("net0", address="dhcp", ipv6Address="2000:0:2::10")
    )

    emu.getServiceNetwork()
    emu.addLayer(base)
    emu.render()

    assert str(getNodeAddress(host, AddressFamily.IPv4)) == "192.168.66.10"
    assert str(getNodeAddress(host, AddressFamily.IPv6)) == "2000:0:2::10"
    assert str(getNodePreferredAddress(host)) == "2000:0:2::10"
    assert str(getNodePreferredAddress(host, preferLocal=False)) == "192.168.66.10"


def test_binding_filter_matches_ipv6_address_and_prefix():
    emu = Emulator()
    base = Base(enableIpv6=True)

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    as2.createHost("host0").joinNetwork("net0", ipv6Address="2000:0:2::71")

    emu.addLayer(base)
    emu.render()

    by_ip = Binding("svc", action=Action.FIRST, filter=Filter(ip="2000:0:2::71"))
    by_prefix = Binding("svc", action=Action.FIRST, filter=Filter(ipv6Prefix="2000:0:2::/64"))

    assert by_ip.getCandidate("svc", emu, peek=True).getName() == "host0"
    assert by_prefix.getCandidate("svc", emu, peek=True).getName() == "host0"


def test_binding_filter_legacy_prefix_accepts_ipv4_and_ipv6_cidr():
    emu = Emulator()
    base = Base(enableIpv6=True)

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    as2.createHost("host0").joinNetwork("net0", address="10.2.0.71", ipv6Address="2000:0:2::71")

    emu.addLayer(base)
    emu.render()

    by_ipv4_prefix = Binding("svc", action=Action.FIRST, filter=Filter(prefix="10.2.0.0/24"))
    by_ipv6_prefix = Binding("svc", action=Action.FIRST, filter=Filter(prefix="2000:0:2::/64"))

    assert by_ipv4_prefix.getCandidate("svc", emu, peek=True).getName() == "host0"
    assert by_ipv6_prefix.getCandidate("svc", emu, peek=True).getName() == "host0"


def test_binding_filter_requires_all_explicit_ipv4_and_ipv6_matches():
    emu = Emulator()
    base = Base(enableIpv6=True)

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    as2.createHost("dual").joinNetwork("net0", address="10.2.0.71", ipv6Address="2000:0:2::71")
    as2.createHost("ipv4-only").joinNetwork("net0", address="10.2.0.72", ipv6Address=None)
    as2.createHost("ipv6-other").joinNetwork("net0", address="10.2.0.73", ipv6Address="2000:0:2::73")

    emu.addLayer(base)
    emu.render()

    by_exact_pair = Binding(
        "svc",
        action=Action.FIRST,
        filter=Filter(ipv4="10.2.0.71", ipv6="2000:0:2::71"),
    )
    by_prefix_pair = Binding(
        "svc",
        action=Action.FIRST,
        filter=Filter(ipv4Prefix="10.2.0.0/24", ipv6Prefix="2000:0:2::/64"),
    )
    by_mismatched_pair = Binding(
        "svc",
        action=Action.FIRST,
        filter=Filter(ipv4="10.2.0.72", ipv6="2000:0:2::73"),
    )

    assert by_exact_pair.getCandidate("svc", emu, peek=True).getName() == "dual"
    assert by_prefix_pair.getCandidate("svc", emu, peek=True).getName() == "dual"
    assert by_mismatched_pair.getCandidate("svc", emu, peek=True) is None


def test_binding_new_can_create_ipv6_selected_host():
    emu = Emulator()
    base = Base(enableIpv6=True)
    dns = DomainNameService()

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    dns.install("dns").addZone("example.")
    emu.addBinding(Binding("dns", filter=Filter(asn=2, ip="2000:0:2::53"), action=Action.NEW))

    emu.addLayer(base)
    emu.addLayer(dns)
    emu.render()

    node = emu.getBindingFor("dns")
    assert str(node.getInterfaces()[0].getIpv6Address()) == "2000:0:2::53"


def test_explicit_ipv6_prefixes_are_claimed_and_auto_allocation_skips_them():
    base = Base(enableIpv6=True)
    as2 = base.createAutonomousSystem(2)

    explicit = as2.createNetwork("explicit", ipv6Prefix="2000:0:2::/64")
    auto = as2.createNetwork("auto")

    assert str(explicit.getIpv6Prefix()) == "2000:0:2::/64"
    assert str(auto.getIpv6Prefix()) == "2000:0:2:1::/64"

    with pytest.raises(AssertionError, match="overlaps an allocated /64"):
        as2.createNetwork("duplicate", ipv6Prefix="2000:0:2::/64")


def test_reserved_ipv6_infrastructure_prefix_cannot_be_assigned_to_user_networks():
    base = Base(enableIpv6=True)
    as2 = base.createAutonomousSystem(2)

    with pytest.raises(AssertionError, match="overlaps an allocated prefix"):
        as2.createNetwork("infra", ipv6Prefix="2000:ffff::/64")

    with pytest.raises(AssertionError, match="overlaps an allocated prefix"):
        base.createInternetExchange(200, ipv6Prefix="2000:ffff:0:1::/64")


def test_explicit_ix_ipv6_prefix_blocks_later_automatic_as_prefix_collision():
    base = Base(enableIpv6=True)

    base.createInternetExchange(100, ipv6Prefix="2000:0:2::/64")
    as2 = base.createAutonomousSystem(2)
    auto = as2.createNetwork("auto")

    assert str(auto.getIpv6Prefix()) == "2000:0:3::/64"


def test_late_ipv6_enablement_claims_existing_explicit_prefixes():
    base = Base()
    as2 = base.createAutonomousSystem(2)
    explicit = as2.createNetwork("explicit", ipv6Prefix="2000:0:2::/64")

    base.enableIpv6()
    auto = as2.createNetwork("auto")

    assert str(explicit.getIpv6Prefix()) == "2000:0:2::/64"
    assert str(auto.getIpv6Prefix()) == "2000:0:2:1::/64"


def test_late_ipv6_enablement_rejects_overlapping_explicit_as_and_ix_prefixes():
    base = Base()
    as2 = base.createAutonomousSystem(2)

    as2.createNetwork("net0", ipv6Prefix="2000:0:2::/64")
    base.createInternetExchange(100, ipv6Prefix="2000:0:2::/64")

    with pytest.raises(AssertionError, match="overlaps an allocated prefix"):
        base.enableIpv6()


def test_service_network_stays_ipv4_only_without_explicit_ipv6_prefix(tmp_path):
    emu = Emulator()
    base = Base()
    emu.addLayer(base)
    svc_net = emu.getServiceNetwork()

    assert str(svc_net.getPrefix()) == "192.168.66.0/24"
    assert not svc_net.hasIpv6Prefix()

    emu.render()
    output_dir = tmp_path / "service-net-ipv4"
    emu.compile(Docker(platform=Platform.AMD64), str(output_dir), override=True)
    compose = (output_dir / "docker-compose.yml").read_text(encoding="utf-8")
    assert "000_svc" in compose
    assert "enable_ipv6" not in compose
    assert "ipv6_address" not in compose


def test_service_network_can_be_dual_stack(tmp_path):
    emu = Emulator(serviceNetworkIpv6Prefix="fd00:66::/64")
    base = Base()
    emu.addLayer(base)
    svc_net = emu.getServiceNetwork()

    assert str(svc_net.getPrefix()) == "192.168.66.0/24"
    assert str(svc_net.getIpv6Prefix()) == "fd00:66::/64"

    emu.render()
    output_dir = tmp_path / "service-net"
    emu.compile(Docker(platform=Platform.AMD64), str(output_dir), override=True)
    compose = (output_dir / "docker-compose.yml").read_text(encoding="utf-8")
    assert "enable_ipv6: true" in compose
    assert "fd00:66::/64" in compose


def test_custom_container_accepts_ipv6_address(tmp_path):
    emu = Emulator()
    base = Base(enableIpv6=True)
    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    emu.addLayer(base)
    emu.render()

    output_dir = tmp_path / "custom-ipv6"
    docker = Docker(platform=Platform.AMD64)
    docker.attachCustomContainer(
        "    custom:\n        image: alpine\n",
        asn=2,
        net="net0",
        ip_address="10.2.0.80",
        ipv6_address="2000:0:2::80",
        show_on_map=True,
        node_name="custom",
    )
    emu.compile(docker, str(output_dir), override=True)

    output_text = _compiled_output_text(output_dir)
    assert "ipv4_address: 10.2.0.80" in output_text
    assert "ipv6_address: 2000:0:2::80" in output_text
    assert 'org.seedsecuritylabs.seedemu.meta.net.0.ipv6_address: "2000:0:2::80"' in output_text


def test_internet_map_attachment_accepts_ipv6_address(tmp_path):
    emu = Emulator()
    base = Base(enableIpv6=True)
    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    emu.addLayer(base)
    emu.render()

    output_dir = tmp_path / "internet-map-ipv6"
    docker = Docker(platform=Platform.AMD64)
    docker.attachInternetMap(
        asn=2,
        net="net0",
        ip_address="10.2.0.81",
        ipv6_address="2000:0:2::81",
        show_on_map=True,
        node_name="internet-map",
    )
    emu.compile(docker, str(output_dir), override=True)

    output_text = _compiled_output_text(output_dir)
    assert "container_name: internet-map" in output_text
    assert "ipv4_address: 10.2.0.81" in output_text
    assert "ipv6_address: 2000:0:2::81" in output_text
    assert 'org.seedsecuritylabs.seedemu.meta.net.0.ipv6_address: "2000:0:2::81"' in output_text


def test_default_ipv4_compile_does_not_emit_ipv6_fields(tmp_path):
    emu = Emulator()
    base = Base()

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    as2.createRouter("router0").joinNetwork("net0")
    as2.createHost("host0").joinNetwork("net0")

    emu.addLayer(base)
    emu.render()

    output_dir = tmp_path / "ipv4-default"
    emu.compile(Docker(platform=Platform.AMD64), str(output_dir), override=True)

    output_text = _compiled_output_text(output_dir)
    assert "enable_ipv6" not in output_text
    assert "ipv6_address" not in output_text
    assert "ipv6_prefix" not in output_text


def test_custom_container_ipv4_only_does_not_emit_ipv6_fields(tmp_path):
    emu = Emulator()
    base = Base()

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    emu.addLayer(base)
    emu.render()

    output_dir = tmp_path / "custom-ipv4"
    docker = Docker(platform=Platform.AMD64)
    docker.attachCustomContainer(
        "    custom:\n        image: alpine\n",
        asn=2,
        net="net0",
        ip_address="10.2.0.80",
        show_on_map=True,
        node_name="custom",
    )
    emu.compile(docker, str(output_dir), override=True)

    output_text = _compiled_output_text(output_dir)
    assert "ipv4_address: 10.2.0.80" in output_text
    assert "ipv6_address" not in output_text
    assert "enable_ipv6" not in output_text


def test_custom_container_without_static_addresses_keeps_compose_network_valid(tmp_path):
    emu = Emulator()
    base = Base()

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    emu.addLayer(base)
    emu.render()

    output_dir = tmp_path / "custom-no-static-address"
    docker = Docker(platform=Platform.AMD64)
    docker.attachCustomContainer(
        "    custom:\n        image: alpine\n",
        asn=2,
        net="net0",
    )
    emu.compile(docker, str(output_dir), override=True)

    output_text = _compiled_output_text(output_dir)
    assert "custom:\n        image: alpine\n        networks:\n             net_2_net0:\n" in output_text
    assert "{}" not in output_text
    assert "ipv6_address" not in output_text


def test_dns_and_etc_hosts_emit_ipv6_records_when_available():
    emu = Emulator()
    base = Base(enableIpv6=True)
    dns = DomainNameService()
    hosts = EtcHosts()

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    web = as2.createHost("web").joinNetwork("net0", address="10.2.0.71", ipv6Address="2000:0:2::71")
    web.addHostName("web.example")

    dns.getZone("example.").resolveToVnode("web", "ns-example")
    dns.install("ns-example").addZone("example.").setMaster()
    emu.addBinding(Binding("ns-example", filter=Filter(asn=2, nodeName="web"), action=Action.FIRST))

    emu.addLayer(base)
    emu.addLayer(dns)
    emu.addLayer(hosts)
    emu.render()

    node = emu.getRegistry().get("2", "hnode", "web")
    zone = dns.getZone("example.").getRecords()
    assert "web A 10.2.0.71" in zone
    assert "web AAAA 2000:0:2::71" in zone

    hosts_file = _file_content(node, "/tmp/etc-hosts")
    assert any(line.startswith("10.2.0.71 ") and "web.example" in line for line in hosts_file.splitlines())
    assert any(line.startswith("2000:0:2::71 ") and "web.example" in line for line in hosts_file.splitlines())


def test_dns_resolve_to_node_emits_dual_stack_records_when_available():
    emu = Emulator()
    base = Base(enableIpv6=True)
    dns = DomainNameService()

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    web = as2.createHost("web").joinNetwork("net0", address="10.2.0.72", ipv6Address="2000:0:2::72")

    emu.addLayer(base)
    emu.render()

    dns.getZone("example.").resolveTo("web", web)
    records = dns.getZone("example.").getRecords()

    assert "web A 10.2.0.72" in records
    assert "web AAAA 2000:0:2::72" in records


def test_dns_resolve_to_node_keeps_first_interface_fallback_for_non_local_networks():
    emu = Emulator(serviceNetworkIpv6Prefix="fd00:100::/64")
    base = Base()
    dns = DomainNameService()

    as2 = base.createAutonomousSystem(2)
    host = as2.createHost("web").joinNetwork("000_svc", address="192.168.66.10", ipv6Address="fd00:100::10")

    emu.getServiceNetwork()
    emu.addLayer(base)
    emu.render()

    dns.getZone("example.").resolveTo("web", host)
    records = dns.getZone("example.").getRecords()

    assert "web A 192.168.66.10" in records
    assert "web AAAA fd00:100::10" in records


def test_dns_and_etc_hosts_keep_ipv4_only_default():
    emu = Emulator()
    base = Base()
    dns = DomainNameService()
    hosts = EtcHosts()

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    web = as2.createHost("web").joinNetwork("net0", address="10.2.0.71")
    web.addHostName("web.example")

    dns.getZone("example.").resolveToVnode("web", "ns-example")
    dns.install("ns-example").addZone("example.").setMaster()
    emu.addBinding(Binding("ns-example", filter=Filter(asn=2, nodeName="web"), action=Action.FIRST))

    emu.addLayer(base)
    emu.addLayer(dns)
    emu.addLayer(hosts)
    emu.render()

    node = emu.getRegistry().get("2", "hnode", "web")
    zone = "\n".join(dns.getZone("example.").getRecords())
    hosts_file = _file_content(node, "/tmp/etc-hosts")

    assert "web A 10.2.0.71" in zone
    assert "AAAA" not in zone
    assert any(line.startswith("10.2.0.71 ") and "web.example" in line for line in hosts_file.splitlines())
    assert "2000:" not in hosts_file


def test_dns_cache_auto_root_hints_include_dual_stack_root_server():
    emu = Emulator()
    base = Base(enableIpv6=True)
    dns = DomainNameService()
    cache = DomainNameCachingService()

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    as2.createHost("rootns").joinNetwork("net0", address="10.2.0.53", ipv6Address="2000:0:2::53")
    as2.createHost("cache").joinNetwork("net0", address="10.2.0.54", ipv6Address="2000:0:2::54")

    dns.install("rootns").addZone(".").setMaster()
    cache.install("cache")
    emu.addBinding(Binding("rootns", filter=Filter(asn=2, nodeName="rootns"), action=Action.FIRST))
    emu.addBinding(Binding("cache", filter=Filter(asn=2, nodeName="cache"), action=Action.FIRST))

    emu.addLayer(base)
    emu.addLayer(dns)
    emu.addLayer(cache)
    emu.render()

    cache_node = emu.getRegistry().get("2", "hnode", "cache")
    root_hints = _file_content(cache_node, "/usr/share/dns/root.hints")

    assert "ns1. A 10.2.0.53" in root_hints
    assert "ns1. AAAA 2000:0:2::53" in root_hints


def test_dns_cache_forward_zone_uses_dual_stack_authoritative_masters():
    emu = Emulator()
    base = Base(enableIpv6=True)
    dns = DomainNameService()
    cache = DomainNameCachingService(autoRoot=False)

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    as2.createHost("ns").joinNetwork("net0", address="10.2.0.53", ipv6Address="2000:0:2::53")
    as2.createHost("cache").joinNetwork("net0", address="10.2.0.54", ipv6Address="2000:0:2::54")

    dns.install("ns-example").addZone("example.").setMaster()
    cache.install("cache").addForwardZone("example.", "ns-example")
    emu.addBinding(Binding("ns-example", filter=Filter(asn=2, nodeName="ns"), action=Action.FIRST))
    emu.addBinding(Binding("cache", filter=Filter(asn=2, nodeName="cache"), action=Action.FIRST))

    emu.addLayer(base)
    emu.addLayer(dns)
    emu.addLayer(cache)
    emu.render()

    cache_node = emu.getRegistry().get("2", "hnode", "cache")
    named_local = _file_content(cache_node, "/etc/bind/named.conf.local")

    assert 'zone "example." { type forward; forwarders { 10.2.0.53; 2000:0:2::53; }; };' in named_local


def test_dns_cache_on_service_network_keeps_first_interface_fallback():
    emu = Emulator()
    base = Base()
    cache = DomainNameCachingService(autoRoot=False)

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    as2.createHost("cache").joinNetwork("000_svc", address="192.168.66.10")
    as2.createHost("client").joinNetwork("net0", address="10.2.0.71")

    emu.getServiceNetwork()
    cache.install("cache")
    emu.addBinding(Binding("cache", filter=Filter(asn=2, nodeName="cache"), action=Action.FIRST))

    emu.addLayer(base)
    emu.addLayer(cache)
    emu.render()

    client = emu.getRegistry().get("2", "hnode", "client")
    commands = [command for command, _ in client.getStartCommands()]

    assert 'echo "nameserver 192.168.66.10" >> /etc/resolv.conf' in commands


def test_dns_cache_resolvconf_prefers_local_ipv6_before_service_ipv4_fallback():
    emu = Emulator(serviceNetworkIpv6Prefix="fd00:66::/64")
    base = Base(enableIpv6=True)
    cache = DomainNameCachingService(autoRoot=False)

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    (
        as2.createHost("cache")
        .joinNetwork("000_svc", address="192.168.66.10", ipv6Address="fd00:66::10")
        .joinNetwork("net0", address="dhcp", ipv6Address="2000:0:2::10")
    )
    as2.createHost("client").joinNetwork("net0", address="10.2.0.71", ipv6Address="2000:0:2::71")

    emu.getServiceNetwork()
    cache.install("cache")
    emu.addBinding(Binding("cache", filter=Filter(asn=2, nodeName="cache"), action=Action.FIRST))

    emu.addLayer(base)
    emu.addLayer(cache)
    emu.render()

    client = emu.getRegistry().get("2", "hnode", "client")
    commands = [command for command, _ in client.getStartCommands()]

    assert 'echo "nameserver 2000:0:2::10" >> /etc/resolv.conf' in commands
    assert 'echo "nameserver 192.168.66.10" >> /etc/resolv.conf' not in commands
