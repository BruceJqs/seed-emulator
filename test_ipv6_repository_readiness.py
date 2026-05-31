from __future__ import annotations

from pathlib import Path

from seedemu.compiler import Docker, Platform
from seedemu.core import (
    Action,
    AddressFamily,
    Binding,
    Emulator,
    Filter,
    Server,
    Service,
    formatHostPort,
    formatMultiaddr,
    formatUrl,
    getNodeAddress,
    getNodeAddresses,
    getNodePreferredAddress,
)
from seedemu.layers import Base, EtcHosts
from seedemu.services import (
    CAServer,
    ChainlinkService,
    DomainNameCachingService,
    DomainNameService,
    KuboService,
    MoneroService,
    TrafficService,
    TrafficServiceType,
)
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


def _start_commands(node) -> str:
    return "\n".join(command for command, _ in node.getStartCommands())


def _imported_paths(node):
    return set(node.getImportedFiles().keys())


class _FakeCAStore:
    def __init__(self, store_path: Path):
        self._store_path = store_path
        self._caDomain = "ca.internal"
        cert_dir = store_path / ".step" / "certs"
        cert_dir.mkdir(parents=True)
        (cert_dir / "root_ca.crt").write_text("fake root ca", encoding="utf-8")

    def initialize(self):
        pass

    def getStorePath(self) -> str:
        return str(self._store_path)


class _FakeEthServer(Server):
    def __init__(self, chain_id: int = 1337, http_port: int = 8545, ws_port: int = 8546):
        super().__init__()
        self._chain_id = chain_id
        self._http_port = http_port
        self._ws_port = ws_port

    def install(self, node):
        pass

    def getChainId(self) -> int:
        return self._chain_id

    def getGethHttpPort(self) -> int:
        return self._http_port

    def getGethWsPort(self) -> int:
        return self._ws_port


class _FakePortServer(Server):
    def __init__(self, port: int):
        super().__init__()
        self._port = port

    def install(self, node):
        pass

    def getPort(self) -> int:
        return self._port


class _FakeUtilityServer(_FakePortServer):
    def __init__(self, port: int):
        super().__init__(port)
        self.deployed_contracts = []

    def deployContractByContent(self, contract_name: str, abi_content: str, bin_content: str):
        self.deployed_contracts.append((contract_name, abi_content, bin_content))


class _FakeEthereumService(Service):
    def __init__(self):
        super().__init__()
        self._pending_targets = {
            "eth-vnode": _FakeEthServer(),
            "faucet-vnode": _FakePortServer(80),
            "utility-vnode": _FakeUtilityServer(5000),
        }

    def _createServer(self) -> Server:
        raise AssertionError("fake Ethereum service does not create servers dynamically")

    def configure(self, emulator: Emulator):
        pass

    def render(self, emulator: Emulator):
        pass

    def getName(self) -> str:
        return "EthereumService"


def _render_kubo_bootstrap_topology(kubo: KuboService):
    emu = Emulator()
    base = Base(enableIpv6=True)

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    as2.createHost("boot").joinNetwork("net0", address="10.2.0.71", ipv6Address="2000:0:2::71")
    as2.createHost("peer").joinNetwork("net0", address="10.2.0.72", ipv6Address="2000:0:2::72")

    kubo.install("boot-vnode").setBootNode(True)
    kubo.install("peer-vnode")
    emu.addBinding(Binding("boot-vnode", filter=Filter(asn=2, nodeName="boot"), action=Action.FIRST))
    emu.addBinding(Binding("peer-vnode", filter=Filter(asn=2, nodeName="peer"), action=Action.FIRST))

    emu.addLayer(base)
    emu.addLayer(kubo)
    emu.render()

    return kubo, emu.getRegistry().get("2", "hnode", "peer")


def _render_ca_filter_topology():
    emu = Emulator()
    base = Base(enableIpv6=True)

    for asn, ipv4, ipv6 in [
        (2, "10.2.0.71", "2000:0:2::71"),
        (3, "10.3.0.72", "2000:0:3::72"),
        (4, "10.4.0.73", "2000:0:4::73"),
        (5, "10.5.0.74", "2000:0:5::74"),
    ]:
        asn_obj = base.createAutonomousSystem(asn)
        asn_obj.createNetwork("net0")
        asn_obj.createHost("client").joinNetwork("net0", address=ipv4, ipv6Address=ipv6)

    emu.addLayer(base)
    emu.render()

    return [
        emu.getRegistry().get(str(asn), "hnode", "client")
        for asn in [2, 3, 4, 5]
    ]


def _render_monero_endpoint_topology(family=AddressFamily.IPv4):
    emu = Emulator()
    base = Base(enableIpv6=True)
    monero = MoneroService()
    blockchain = monero.createBlockchain("base-monero")
    blockchain.setEndpointAddressFamily(family)

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    as2.createHost("seed").joinNetwork("net0", address="10.2.0.71", ipv6Address="2000:0:2::71")
    as2.createHost("client").joinNetwork("net0", address="10.2.0.72", ipv6Address="2000:0:2::72")
    as2.createHost("light").joinNetwork("net0", address="10.2.0.73", ipv6Address="2000:0:2::73")

    blockchain.createSeedNode("seed-vnode")
    blockchain.createClientNode("client-vnode")
    blockchain.createLightWallet("light-vnode")
    emu.addBinding(Binding("seed-vnode", filter=Filter(asn=2, nodeName="seed"), action=Action.FIRST))
    emu.addBinding(Binding("client-vnode", filter=Filter(asn=2, nodeName="client"), action=Action.FIRST))
    emu.addBinding(Binding("light-vnode", filter=Filter(asn=2, nodeName="light"), action=Action.FIRST))

    emu.addLayer(base)
    emu.addLayer(monero)
    emu.render()

    return (
        emu.getRegistry().get("2", "hnode", "client"),
        emu.getRegistry().get("2", "hnode", "light"),
    )


def _render_chainlink_endpoint_topology(family=AddressFamily.IPv4):
    emu = Emulator()
    base = Base(enableIpv6=True)
    ethereum = _FakeEthereumService()
    chainlink = ChainlinkService(
        eth_server="eth-vnode",
        faucet_server="faucet-vnode",
        utility_server="utility-vnode",
    )
    if family != AddressFamily.IPv4:
        chainlink.setEndpointAddressFamily(family)

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    as2.createHost("eth").joinNetwork("net0", address="10.2.0.71", ipv6Address="2000:0:2::71")
    as2.createHost("faucet").joinNetwork("net0", address="10.2.0.72", ipv6Address="2000:0:2::72")
    as2.createHost("utility").joinNetwork("net0", address="10.2.0.73", ipv6Address="2000:0:2::73")
    as2.createHost("chainlink").joinNetwork("net0", address="10.2.0.74", ipv6Address="2000:0:2::74")
    as2.createHost("user").joinNetwork("net0", address="10.2.0.75", ipv6Address="2000:0:2::75")

    chainlink.install("chainlink-vnode")
    chainlink.installUserServer("user-vnode").setChainlinkServers(["chainlink-vnode"])

    for vnode, node_name in (
        ("eth-vnode", "eth"),
        ("faucet-vnode", "faucet"),
        ("utility-vnode", "utility"),
        ("chainlink-vnode", "chainlink"),
        ("user-vnode", "user"),
    ):
        emu.addBinding(Binding(vnode, filter=Filter(asn=2, nodeName=node_name), action=Action.FIRST))

    emu.addLayer(base)
    emu.addLayer(ethereum)
    emu.addLayer(chainlink)
    emu.render()

    return (
        emu.getRegistry().get("2", "hnode", "chainlink"),
        emu.getRegistry().get("2", "hnode", "user"),
    )


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


def test_ca_install_cert_filter_matches_ipv4_and_ipv6_targets(tmp_path):
    node_by_asn = {
        node.getAsn(): node
        for node in _render_ca_filter_topology()
    }

    ca_server = CAServer("0.26.1")
    ca_server.setCAStore(_FakeCAStore(tmp_path / "ca-store"))
    ca_server.installCACert(Filter(ip="10.2.0.71"))
    ca_server.installCACert(Filter(ipv6="2000:0:3::72"))
    ca_server.installCACert(Filter(prefix="2000:0:4::/64"))
    ca_server._serverConfigure(9, list(node_by_asn.values()))

    cert_path = "/usr/local/share/ca-certificates/SEEDEMU_Internal_Root_CA_9.crt"

    assert cert_path in _imported_paths(node_by_asn[2])
    assert cert_path in _imported_paths(node_by_asn[3])
    assert cert_path in _imported_paths(node_by_asn[4])
    assert cert_path not in _imported_paths(node_by_asn[5])
    assert "update-ca-certificates" in _start_commands(node_by_asn[2])
    assert "update-ca-certificates" not in _start_commands(node_by_asn[5])


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


def test_service_network_dual_stack_emits_node_ipv6_address_only_when_interface_has_ipv6(tmp_path):
    emu = Emulator(serviceNetworkIpv6Prefix="fd00:66::/64")
    base = Base()

    as2 = base.createAutonomousSystem(2)
    as2.createHost("svc-host").joinNetwork(
        "000_svc",
        address="192.168.66.10",
        ipv6Address="fd00:66::10",
    )

    emu.getServiceNetwork()
    emu.addLayer(base)
    emu.render()

    output_dir = tmp_path / "service-net-node-ipv6"
    emu.compile(Docker(platform=Platform.AMD64), str(output_dir), override=True)
    compose = (output_dir / "docker-compose.yml").read_text(encoding="utf-8")

    assert "enable_ipv6: true" in compose
    assert "ipv4_address: 192.168.66.10" in compose
    assert "ipv6_address: fd00:66::10" in compose


def test_service_network_dual_stack_respects_interface_ipv6_opt_out(tmp_path):
    emu = Emulator(serviceNetworkIpv6Prefix="fd00:66::/64")
    base = Base()

    as2 = base.createAutonomousSystem(2)
    as2.createHost("svc-host").joinNetwork(
        "000_svc",
        address="192.168.66.10",
        ipv6Address=None,
    )

    emu.getServiceNetwork()
    emu.addLayer(base)
    emu.render()

    output_dir = tmp_path / "service-net-node-v4-only"
    emu.compile(Docker(platform=Platform.AMD64), str(output_dir), override=True)
    compose = (output_dir / "docker-compose.yml").read_text(encoding="utf-8")

    assert "enable_ipv6: true" in compose
    assert "fd00:66::/64" in compose
    assert "ipv4_address: 192.168.66.10" in compose
    assert "ipv6_address:" not in compose


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


def test_internet_map_attachment_ipv4_only_does_not_emit_ipv6_fields(tmp_path):
    emu = Emulator()
    base = Base()

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    emu.addLayer(base)
    emu.render()

    output_dir = tmp_path / "internet-map-ipv4"
    docker = Docker(platform=Platform.AMD64)
    docker.attachInternetMap(
        asn=2,
        net="net0",
        ip_address="10.2.0.81",
        show_on_map=True,
        node_name="internet-map",
    )
    emu.compile(docker, str(output_dir), override=True)

    output_text = _compiled_output_text(output_dir)
    assert "container_name: internet-map" in output_text
    assert "ipv4_address: 10.2.0.81" in output_text
    assert "enable_ipv6" not in output_text
    assert "ipv6_address" not in output_text
    assert "ipv6_prefix" not in output_text


def test_internet_map_attachment_on_dual_stack_network_requires_explicit_ipv6_address(tmp_path):
    emu = Emulator()
    base = Base(enableIpv6=True)

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    emu.addLayer(base)
    emu.render()

    output_dir = tmp_path / "internet-map-dual-stack-no-node-ipv6"
    docker = Docker(platform=Platform.AMD64)
    docker.attachInternetMap(
        asn=2,
        net="net0",
        ip_address="10.2.0.81",
        show_on_map=True,
        node_name="internet-map",
    )
    emu.compile(docker, str(output_dir), override=True)

    output_text = _compiled_output_text(output_dir)
    assert "enable_ipv6: true" in output_text
    assert "2000:0:2::/64" in output_text
    assert "ipv4_address: 10.2.0.81" in output_text
    assert "ipv6_address" not in output_text


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


def test_custom_container_on_dual_stack_network_requires_explicit_ipv6_address(tmp_path):
    emu = Emulator()
    base = Base(enableIpv6=True)

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    emu.addLayer(base)
    emu.render()

    output_dir = tmp_path / "custom-dual-stack-no-node-ipv6"
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
    assert "enable_ipv6: true" in output_text
    assert "2000:0:2::/64" in output_text
    assert "ipv4_address: 10.2.0.80" in output_text
    assert "ipv6_address" not in output_text


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


def test_traffic_service_raw_receiver_targets_remain_unchanged():
    emu = Emulator()
    base = Base(enableIpv6=True)
    traffic = TrafficService()

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    as2.createHost("receiver").joinNetwork("net0", address="10.2.0.71", ipv6Address="2000:0:2::71")
    as2.createHost("generator").joinNetwork("net0", address="10.2.0.72", ipv6Address="2000:0:2::72")

    traffic.install("receiver-vnode", TrafficServiceType.IPERF_RECEIVER)
    traffic.install("generator-vnode", TrafficServiceType.IPERF_GENERATOR).addReceivers(hosts=["receiver-vnode"])
    emu.addBinding(Binding("receiver-vnode", filter=Filter(asn=2, nodeName="receiver"), action=Action.FIRST))
    emu.addBinding(Binding("generator-vnode", filter=Filter(asn=2, nodeName="generator"), action=Action.FIRST))

    emu.addLayer(base)
    emu.addLayer(traffic)
    emu.render()

    generator = emu.getRegistry().get("2", "hnode", "generator")
    assert _file_content(generator, "/root/traffic-targets").strip() == "receiver-vnode"


def test_traffic_service_receiver_vnodes_default_to_ipv4_targets():
    emu = Emulator()
    base = Base(enableIpv6=True)
    traffic = TrafficService()

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    as2.createHost("receiver").joinNetwork("net0", address="10.2.0.71", ipv6Address="2000:0:2::71")
    as2.createHost("generator").joinNetwork("net0", address="10.2.0.72", ipv6Address="2000:0:2::72")

    traffic.install("receiver-vnode", TrafficServiceType.IPERF_RECEIVER)
    traffic.install("generator-vnode", TrafficServiceType.IPERF_GENERATOR).addReceiverVnodes(["receiver-vnode"])
    emu.addBinding(Binding("receiver-vnode", filter=Filter(asn=2, nodeName="receiver"), action=Action.FIRST))
    emu.addBinding(Binding("generator-vnode", filter=Filter(asn=2, nodeName="generator"), action=Action.FIRST))

    emu.addLayer(base)
    emu.addLayer(traffic)
    emu.render()

    generator = emu.getRegistry().get("2", "hnode", "generator")
    assert _file_content(generator, "/root/traffic-targets").strip() == "10.2.0.71"


def test_traffic_service_receiver_vnodes_can_select_ipv6_targets():
    emu = Emulator()
    base = Base(enableIpv6=True)
    traffic = TrafficService()

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    as2.createHost("receiver").joinNetwork("net0", address="10.2.0.71", ipv6Address="2000:0:2::71")
    as2.createHost("generator").joinNetwork("net0", address="10.2.0.72", ipv6Address="2000:0:2::72")

    traffic.install("receiver-vnode", TrafficServiceType.IPERF_RECEIVER)
    traffic.install("generator-vnode", TrafficServiceType.IPERF_GENERATOR).addReceiverVnodes(
        ["receiver-vnode"],
        family=AddressFamily.IPv6,
    )
    emu.addBinding(Binding("receiver-vnode", filter=Filter(asn=2, nodeName="receiver"), action=Action.FIRST))
    emu.addBinding(Binding("generator-vnode", filter=Filter(asn=2, nodeName="generator"), action=Action.FIRST))

    emu.addLayer(base)
    emu.addLayer(traffic)
    emu.render()

    generator = emu.getRegistry().get("2", "hnode", "generator")
    assert _file_content(generator, "/root/traffic-targets").strip() == "2000:0:2::71"


def test_kubo_bootstrap_endpoints_default_to_ipv4_on_dual_stack_nodes():
    kubo, peer = _render_kubo_bootstrap_topology(KuboService())

    commands = _start_commands(peer)
    script = _file_content(peer, "/tmp/kubo/bootstrap.sh")

    assert kubo.getBootstrapList() == ["10.2.0.71"]
    assert "ipfs config Addresses.API /ip4/0.0.0.0/tcp/5001" in commands
    assert "ipfs config Addresses.Gateway /ip4/0.0.0.0/tcp/8080" in commands
    assert "http://10.2.0.71:5001/api/v0/config?arg=Identity.PeerID" in script
    assert "/ip4/10.2.0.71/tcp/4001" in script
    assert "2000:0:2::71" not in script


def test_kubo_bootstrap_endpoints_can_select_ipv6_helpers():
    kubo, peer = _render_kubo_bootstrap_topology(
        KuboService(bootstrapAddressFamily=AddressFamily.IPv6)
    )

    commands = _start_commands(peer)
    script = _file_content(peer, "/tmp/kubo/bootstrap.sh")

    assert kubo.getBootstrapList() == ["2000:0:2::71"]
    assert "ipfs config Addresses.API /ip6/::/tcp/5001" in commands
    assert "ipfs config Addresses.Gateway /ip6/::/tcp/8080" in commands
    assert "http://[2000:0:2::71]:5001/api/v0/config?arg=Identity.PeerID" in script
    assert "/ip6/2000:0:2::71/tcp/4001" in script
    assert "/ip4/10.2.0.71/tcp/4001" not in script


def test_monero_endpoints_default_to_ipv4_on_dual_stack_nodes():
    client, light = _render_monero_endpoint_topology()

    client_script = _file_content(client, "/usr/local/bin/seedemu-monero-node.sh")
    light_script = _file_content(light, "/usr/local/bin/seedemu-monero-light.sh")

    assert 'DAEMON_ARGS+=("--add-exclusive-node=10.2.0.71:28080")' in client_script
    assert 'UPSTREAMS=("10.2.0.71:28081" "10.2.0.72:28081")' in light_script
    assert "2000:0:2::71" not in client_script
    assert "2000:0:2::71" not in light_script


def test_monero_endpoints_can_select_ipv6_helpers():
    client, light = _render_monero_endpoint_topology(AddressFamily.IPv6)

    client_script = _file_content(client, "/usr/local/bin/seedemu-monero-node.sh")
    light_script = _file_content(light, "/usr/local/bin/seedemu-monero-light.sh")

    assert 'DAEMON_ARGS+=("--add-exclusive-node=[2000:0:2::71]:28080")' in client_script
    assert 'UPSTREAMS=("[2000:0:2::71]:28081" "[2000:0:2::72]:28081")' in light_script
    assert 'if [[ "$endpoint" =~ ^\\[(.*)\\]:([0-9]+)$ ]]; then' in client_script
    assert "--add-exclusive-node=10.2.0.71:28080" not in client_script


def test_chainlink_generated_urls_default_to_ipv4_on_dual_stack_nodes():
    chainlink, user = _render_chainlink_endpoint_topology()

    config = _file_content(chainlink, "/chainlink/config.toml")
    oracle_script = _file_content(chainlink, "/chainlink/deploy_oracle_contract.py")
    register_script = _file_content(chainlink, "/chainlink/register_contract.py")
    auth_sender_script = _file_content(chainlink, "/chainlink/fund_auth_sender.py")
    user_deploy_script = _file_content(user, "/chainlink_user/deploy_user_contract.py")
    user_oracle_script = _file_content(user, "/chainlink_user/get_oracle_addresses.py")
    combined = "\n".join(
        [
            config,
            oracle_script,
            register_script,
            auth_sender_script,
            user_deploy_script,
            user_oracle_script,
        ]
    )

    assert "WSURL = 'ws://10.2.0.71:8546'" in config
    assert "HTTPURL = 'http://10.2.0.71:8545'" in config
    assert 'eth_url    = "http://10.2.0.71:8545"' in oracle_script
    assert 'faucet_url = "http://10.2.0.72:80"' in auth_sender_script
    assert 'util_server_url    = "http://10.2.0.73:5000"' in oracle_script
    assert 'util_server_url = "http://10.2.0.73:5000"' in register_script
    assert 'eth_url    = "http://10.2.0.71:8545"' in user_deploy_script
    assert 'faucet_url = "http://10.2.0.72:80"' in user_deploy_script
    assert 'util_server_url = "http://10.2.0.73:5000"' in user_oracle_script
    assert "2000:0:2::" not in combined


def test_chainlink_generated_urls_can_select_ipv6_helpers():
    chainlink, user = _render_chainlink_endpoint_topology(AddressFamily.IPv6)

    config = _file_content(chainlink, "/chainlink/config.toml")
    oracle_script = _file_content(chainlink, "/chainlink/deploy_oracle_contract.py")
    register_script = _file_content(chainlink, "/chainlink/register_contract.py")
    auth_sender_script = _file_content(chainlink, "/chainlink/fund_auth_sender.py")
    user_deploy_script = _file_content(user, "/chainlink_user/deploy_user_contract.py")
    user_oracle_script = _file_content(user, "/chainlink_user/get_oracle_addresses.py")
    combined = "\n".join(
        [
            config,
            oracle_script,
            register_script,
            auth_sender_script,
            user_deploy_script,
            user_oracle_script,
        ]
    )

    assert "WSURL = 'ws://[2000:0:2::71]:8546'" in config
    assert "HTTPURL = 'http://[2000:0:2::71]:8545'" in config
    assert 'eth_url    = "http://[2000:0:2::71]:8545"' in oracle_script
    assert 'faucet_url = "http://[2000:0:2::72]:80"' in auth_sender_script
    assert 'util_server_url    = "http://[2000:0:2::73]:5000"' in oracle_script
    assert 'util_server_url = "http://[2000:0:2::73]:5000"' in register_script
    assert 'eth_url    = "http://[2000:0:2::71]:8545"' in user_deploy_script
    assert 'faucet_url = "http://[2000:0:2::72]:80"' in user_deploy_script
    assert 'util_server_url = "http://[2000:0:2::73]:5000"' in user_oracle_script
    assert "http://10.2.0.71:8545" not in combined
    assert "http://10.2.0.72:80" not in combined
    assert "http://10.2.0.73:5000" not in combined
