from __future__ import annotations

import socket
from pathlib import Path

from seedemu.compiler import Docker, Platform
from seedemu.core import (
    Action,
    AddressFamily,
    Binding,
    Emulator,
    Filter,
    Node,
    Server,
    Service,
    formatHostPort,
    formatMultiaddr,
    formatUrl,
    getNodeAddress,
    getNodeAddresses,
    getNodePreferredAddress,
    normalizeAddressFamily,
)
from seedemu.core.enums import NodeRole
from seedemu.layers import Base, EtcHosts
from seedemu.services import (
    BotnetClientService,
    BotnetService,
    CAServer,
    ChainlinkService,
    Blockchain,
    DomainNameCachingService,
    DomainNameService,
    DomainRegistrarServer,
    ConsensusMechanism,
    EthUtilityServer,
    EthereumServer,
    FaucetServer,
    FaucetUtil,
    KuboService,
    MoneroService,
    PoSServer,
    ReverseDomainNameService,
    TorNodeType,
    TorServer,
    TorService,
    TrafficService,
    TrafficServiceType,
    WebServer,
)
from seedemu.services.EthereumService.EthTemplates import (
    FaucetServerFileTemplates,
    format_faucet_fund_url,
    format_faucet_url,
    format_fund_curl,
)
from seedemu.services.KuboService.KuboUtils import getIP
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


class _FakeCAStoreWithDomain(_FakeCAStore):
    def __init__(self, store_path: Path, ca_domain: str):
        super().__init__(store_path)
        self._caDomain = ca_domain


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


class _NoopServer(Server):
    def install(self, node):
        pass


class _NoopService(Service):
    def __init__(self, name: str):
        super().__init__()
        self._name = name

    def _createServer(self) -> Server:
        return _NoopServer()

    def getName(self) -> str:
        return self._name


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

    def isSave(self) -> bool:
        return False


class _FakeAccount:
    address = "0x1111111111111111111111111111111111111111"
    privateKey = bytes.fromhex("22" * 32)
    keystore_filename = "fake-keystore.json"
    keystore_content = "{}"
    password = "admin"
    balance = 32


class _FakeGenesis:
    def getGenesis(self) -> str:
        return "{}"


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


def _render_kubo_service_network_bootstrap_topology(kubo: KuboService):
    emu = Emulator(serviceNetworkIpv6Prefix="fd00:66::/64")
    base = Base(enableIpv6=True)

    as2 = base.createAutonomousSystem(2)
    as2.createHost("boot").joinNetwork(
        "000_svc",
        address="192.168.66.71",
        ipv6Address="fd00:66::71",
    )
    as2.createHost("peer").joinNetwork(
        "000_svc",
        address="192.168.66.72",
        ipv6Address="fd00:66::72",
    )

    kubo.install("boot-vnode").setBootNode(True)
    kubo.install("peer-vnode")
    emu.addBinding(Binding("boot-vnode", filter=Filter(asn=2, nodeName="boot"), action=Action.FIRST))
    emu.addBinding(Binding("peer-vnode", filter=Filter(asn=2, nodeName="peer"), action=Action.FIRST))

    emu.addLayer(base)
    emu.addLayer(kubo)
    emu.getServiceNetwork()
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


def _render_tor_host(name: str, address: str = "10.2.0.80", ipv6Address: str = "2000:0:2::80"):
    emu = Emulator()
    base = Base(enableIpv6=True)

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    as2.createHost(name).joinNetwork("net0", address=address, ipv6Address=ipv6Address)

    emu.addLayer(base)
    emu.render()

    return emu.getRegistry().get("2", "hnode", name)


def _render_tor_hidden_service_vnode_topology(
    family=AddressFamily.IPv4,
    service_network_only=False,
):
    emu = Emulator(serviceNetworkIpv6Prefix="fd00:66::/64") if service_network_only else Emulator()
    base = Base(enableIpv6=True)
    tor = TorService()
    backend_service = _NoopService("NoopService")

    as2 = base.createAutonomousSystem(2)
    if service_network_only:
        as2.createHost("backend").joinNetwork(
            "000_svc",
            address="192.168.66.80",
            ipv6Address="fd00:66::80",
        )
        as2.createHost("hs").joinNetwork(
            "000_svc",
            address="192.168.66.81",
            ipv6Address="fd00:66::81",
        )
    else:
        as2.createNetwork("net0")
        as2.createHost("backend").joinNetwork(
            "net0",
            address="10.2.0.80",
            ipv6Address="2000:0:2::80",
        )
        as2.createHost("hs").joinNetwork(
            "net0",
            address="10.2.0.81",
            ipv6Address="2000:0:2::81",
        )

    backend_service.install("backend-vnode")
    tor.install("hs-vnode").setRole(TorNodeType.HS).linkByVnode("backend-vnode", 8080, family=family)
    emu.addBinding(Binding("backend-vnode", filter=Filter(asn=2, nodeName="backend"), action=Action.FIRST))
    emu.addBinding(Binding("hs-vnode", filter=Filter(asn=2, nodeName="hs"), action=Action.FIRST))

    emu.addLayer(base)
    emu.addLayer(backend_service)
    emu.addLayer(tor)
    if service_network_only:
        emu.getServiceNetwork()
    emu.render()

    return emu.getRegistry().get("2", "hnode", "hs")


def _render_botnet_endpoint_topology(family=AddressFamily.IPv4):
    emu = Emulator(serviceNetworkIpv6Prefix="fd00:66::/64")
    base = Base(enableIpv6=True)
    botnet = BotnetService()
    botnet_client = BotnetClientService()

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    (
        as2.createHost("c2")
        .joinNetwork("000_svc", address="192.168.66.71", ipv6Address="fd00:66::71")
        .joinNetwork("net0", address="10.2.0.71", ipv6Address="2000:0:2::71")
    )
    as2.createHost("client").joinNetwork("net0", address="10.2.0.72", ipv6Address="2000:0:2::72")

    botnet.install("c2-vnode").setEndpointAddressFamily(family)
    botnet_client.install("client-vnode").setServer("c2-vnode")
    emu.addBinding(Binding("c2-vnode", filter=Filter(asn=2, nodeName="c2"), action=Action.FIRST))
    emu.addBinding(Binding("client-vnode", filter=Filter(asn=2, nodeName="client"), action=Action.FIRST))

    emu.addLayer(base)
    emu.addLayer(botnet)
    emu.addLayer(botnet_client)
    emu.getServiceNetwork()
    emu.render()

    return (
        emu.getRegistry().get("2", "hnode", "c2"),
        emu.getRegistry().get("2", "hnode", "client"),
    )


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


def _render_monero_service_network_endpoint_topology(family=AddressFamily.IPv4):
    emu = Emulator(serviceNetworkIpv6Prefix="fd00:66::/64")
    base = Base(enableIpv6=True)
    monero = MoneroService()
    blockchain = monero.createBlockchain("base-monero")
    blockchain.setEndpointAddressFamily(family)

    as2 = base.createAutonomousSystem(2)
    as2.createHost("seed").joinNetwork(
        "000_svc",
        address="192.168.66.71",
        ipv6Address="fd00:66::71",
    )
    as2.createHost("client").joinNetwork(
        "000_svc",
        address="192.168.66.72",
        ipv6Address="fd00:66::72",
    )
    as2.createHost("light").joinNetwork(
        "000_svc",
        address="192.168.66.73",
        ipv6Address="fd00:66::73",
    )

    blockchain.createSeedNode("seed-vnode")
    blockchain.createClientNode("client-vnode")
    blockchain.createLightWallet("light-vnode")
    emu.addBinding(Binding("seed-vnode", filter=Filter(asn=2, nodeName="seed"), action=Action.FIRST))
    emu.addBinding(Binding("client-vnode", filter=Filter(asn=2, nodeName="client"), action=Action.FIRST))
    emu.addBinding(Binding("light-vnode", filter=Filter(asn=2, nodeName="light"), action=Action.FIRST))

    emu.addLayer(base)
    emu.addLayer(monero)
    emu.getServiceNetwork()
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


def _render_chainlink_service_network_endpoint_topology(family=AddressFamily.IPv4):
    emu = Emulator(serviceNetworkIpv6Prefix="fd00:66::/64")
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
    as2.createHost("eth").joinNetwork(
        "000_svc",
        address="192.168.66.71",
        ipv6Address="fd00:66::71",
    )
    as2.createHost("faucet").joinNetwork(
        "000_svc",
        address="192.168.66.72",
        ipv6Address="fd00:66::72",
    )
    as2.createHost("utility").joinNetwork(
        "000_svc",
        address="192.168.66.73",
        ipv6Address="fd00:66::73",
    )
    as2.createHost("chainlink").joinNetwork(
        "000_svc",
        address="192.168.66.74",
        ipv6Address="fd00:66::74",
    )
    as2.createHost("user").joinNetwork(
        "000_svc",
        address="192.168.66.75",
        ipv6Address="fd00:66::75",
    )

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
    emu.getServiceNetwork()
    emu.render()

    return (
        emu.getRegistry().get("2", "hnode", "chainlink"),
        emu.getRegistry().get("2", "hnode", "user"),
    )


def _new_test_faucet_server(eth_server_address: str):
    server = object.__new__(FaucetServer)
    server._FaucetServer__max_fund_amount = 10
    server._FaucetServer__chain_id = 1337
    server._FaucetServer__eth_server_url = eth_server_address
    server._FaucetServer__eth_server_port = 8545
    server._FaucetServer__consensus = ConsensusMechanism.POA
    server._FaucetServer__account = _FakeAccount()
    server._FaucetServer__port = 80
    server._FaucetServer__fundlist = [("0x3333333333333333333333333333333333333333", 1)]
    server._FaucetServer__max_fund_attempts = 5
    return server


def _new_test_utility_server(eth_server_address: str, faucet_server_address: str):
    server = object.__new__(EthUtilityServer)
    server._EthUtilityServer__contract_to_deploy = {}
    server._EthUtilityServer__contract_to_deploy_container_path = {}
    server._EthUtilityServer__contract_to_deploy_content = {}
    server._EthUtilityServer__eth_node_url = eth_server_address
    server._EthUtilityServer__eth_node_port = 8545
    server._EthUtilityServer__faucet_url = faucet_server_address
    server._EthUtilityServer__faucet_port = 80
    server._EthUtilityServer__chain_id = 1337
    server._EthUtilityServer__port = 5000
    return server


def _render_ethereum_endpoint_topology(family=AddressFamily.IPv4):
    emu = Emulator()
    base = Base(enableIpv6=True)
    ethereum = _FakeEthereumService()

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    as2.createHost("eth").joinNetwork("net0", address="10.2.0.71", ipv6Address="2000:0:2::71")
    as2.createHost("faucet").joinNetwork("net0", address="10.2.0.72", ipv6Address="2000:0:2::72")
    as2.createHost("utility").joinNetwork("net0", address="10.2.0.73", ipv6Address="2000:0:2::73")

    for vnode, node_name in (
        ("eth-vnode", "eth"),
        ("faucet-vnode", "faucet"),
        ("utility-vnode", "utility"),
    ):
        emu.addBinding(Binding(vnode, filter=Filter(asn=2, nodeName=node_name), action=Action.FIRST))

    emu.addLayer(base)
    emu.addLayer(ethereum)
    emu.render()

    blockchain = object.__new__(Blockchain)
    blockchain.setEndpointAddressFamily(family)
    assert blockchain.getEndpointAddressFamily() == family
    eth_address = blockchain._Blockchain__getIpByVnodeName(emu, "eth-vnode")
    faucet_address = blockchain._Blockchain__getIpByVnodeName(emu, "faucet-vnode")

    faucet_node = emu.getRegistry().get("2", "hnode", "faucet")
    FaucetServer._installScriptFiles(_new_test_faucet_server(eth_address), faucet_node)

    utility_node = emu.getRegistry().get("2", "hnode", "utility")
    EthUtilityServer._installScriptFile(
        _new_test_utility_server(eth_address, faucet_address),
        utility_node,
    )

    faucet_util = FaucetUtil(endpointAddressFamily=family)
    faucet_util.setFaucetServerInfo("faucet-vnode", 80)
    faucet_util.configure(emu)

    return faucet_node, utility_node, faucet_util


def _render_ethereum_service_network_endpoint_topology(family=AddressFamily.IPv4):
    emu = Emulator(serviceNetworkIpv6Prefix="fd00:66::/64")
    base = Base(enableIpv6=True)
    ethereum = _FakeEthereumService()

    as2 = base.createAutonomousSystem(2)
    as2.createHost("eth").joinNetwork(
        "000_svc",
        address="192.168.66.71",
        ipv6Address="fd00:66::71",
    )
    as2.createHost("faucet").joinNetwork(
        "000_svc",
        address="192.168.66.72",
        ipv6Address="fd00:66::72",
    )
    as2.createHost("utility").joinNetwork(
        "000_svc",
        address="192.168.66.73",
        ipv6Address="fd00:66::73",
    )

    for vnode, node_name in (
        ("eth-vnode", "eth"),
        ("faucet-vnode", "faucet"),
        ("utility-vnode", "utility"),
    ):
        emu.addBinding(Binding(vnode, filter=Filter(asn=2, nodeName=node_name), action=Action.FIRST))

    emu.addLayer(base)
    emu.addLayer(ethereum)
    emu.getServiceNetwork()
    emu.render()

    blockchain = object.__new__(Blockchain)
    blockchain.setEndpointAddressFamily(family)
    eth_address = blockchain._Blockchain__getIpByVnodeName(emu, "eth-vnode")
    faucet_address = blockchain._Blockchain__getIpByVnodeName(emu, "faucet-vnode")

    faucet_node = emu.getRegistry().get("2", "hnode", "faucet")
    FaucetServer._installScriptFiles(_new_test_faucet_server(eth_address), faucet_node)

    utility_node = emu.getRegistry().get("2", "hnode", "utility")
    EthUtilityServer._installScriptFile(
        _new_test_utility_server(eth_address, faucet_address),
        utility_node,
    )

    faucet_util = FaucetUtil(endpointAddressFamily=family)
    faucet_util.setFaucetServerInfo("faucet-vnode", 80)
    faucet_util.configure(emu)

    return faucet_node, utility_node, faucet_util


def _render_ethereum_bootstrap_endpoint_topology(family=AddressFamily.IPv4):
    base = Base(enableIpv6=True)
    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    boot = as2.createHost("boot").joinNetwork("net0", address="10.2.0.71", ipv6Address="2000:0:2::71")
    peer = as2.createHost("peer").joinNetwork("net0", address="10.2.0.72", ipv6Address="2000:0:2::72")
    base.configure(Emulator())

    blockchain = object.__new__(Blockchain)
    blockchain._consensus = ConsensusMechanism.POA
    blockchain._chain_id = 1337
    blockchain._chain_name = "poa-helper"
    blockchain._genesis = _FakeGenesis()
    blockchain._eth_service = _FakeEthereumService()
    blockchain._boot_node_addresses = []
    blockchain._boot_node_enode_urls = []
    blockchain._beacon_node_api_urls = []
    blockchain._joined_accounts = []
    blockchain._joined_signer_accounts = []
    blockchain._validator_ids = []
    blockchain._beacon_setup_node_address = ""
    blockchain._beacon_setup_node_url = ""
    blockchain._miner_node_address = []
    blockchain._emu_mnemonic = "test mnemonic"
    blockchain._emu_account_balance = 0
    blockchain._total_accounts_per_node = 0
    blockchain.setEndpointAddressFamily(family)

    boot_server = object.__new__(EthereumServer)
    EthereumServer.__init__(boot_server, 1, blockchain)
    boot_server.setBootNode(True)
    boot_server._mnemonic_accounts = []
    peer_server = object.__new__(EthereumServer)
    EthereumServer.__init__(peer_server, 2, blockchain)
    peer_server._mnemonic_accounts = []

    blockchain._doConfigure(boot, boot_server)
    blockchain._doConfigure(peer, peer_server)
    boot_server.install(boot, _FakeEthereumService())
    peer_server.install(peer, _FakeEthereumService())

    return boot, peer, blockchain


def _render_ethereum_service_network_bootstrap_endpoint_topology(family=AddressFamily.IPv4):
    base = Base(enableIpv6=True)
    emu = Emulator(serviceNetworkIpv6Prefix="fd00:66::/64")
    as2 = base.createAutonomousSystem(2)
    boot = as2.createHost("boot").joinNetwork(
        "000_svc",
        address="192.168.66.71",
        ipv6Address="fd00:66::71",
    )
    peer = as2.createHost("peer").joinNetwork(
        "000_svc",
        address="192.168.66.72",
        ipv6Address="fd00:66::72",
    )
    emu.getServiceNetwork()
    base.configure(emu)

    blockchain = object.__new__(Blockchain)
    blockchain._consensus = ConsensusMechanism.POA
    blockchain._chain_id = 1337
    blockchain._chain_name = "poa-helper"
    blockchain._genesis = _FakeGenesis()
    blockchain._eth_service = _FakeEthereumService()
    blockchain._boot_node_addresses = []
    blockchain._boot_node_enode_urls = []
    blockchain._beacon_node_api_urls = []
    blockchain._joined_accounts = []
    blockchain._joined_signer_accounts = []
    blockchain._validator_ids = []
    blockchain._beacon_setup_node_address = ""
    blockchain._beacon_setup_node_url = ""
    blockchain._miner_node_address = []
    blockchain._emu_mnemonic = "test mnemonic"
    blockchain._emu_account_balance = 0
    blockchain._total_accounts_per_node = 0
    blockchain.setEndpointAddressFamily(family)

    boot_server = object.__new__(EthereumServer)
    EthereumServer.__init__(boot_server, 1, blockchain)
    boot_server.setBootNode(True)
    boot_server._mnemonic_accounts = []
    peer_server = object.__new__(EthereumServer)
    EthereumServer.__init__(peer_server, 2, blockchain)
    peer_server._mnemonic_accounts = []

    blockchain._doConfigure(boot, boot_server)
    blockchain._doConfigure(peer, peer_server)
    boot_server.install(boot, _FakeEthereumService())
    peer_server.install(peer, _FakeEthereumService())

    return boot, peer, blockchain


def _render_ethereum_pos_helper_endpoint_topology(family=AddressFamily.IPv4):
    base = Base(enableIpv6=True)
    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    setup = as2.createHost("setup").joinNetwork("net0", address="10.2.0.71", ipv6Address="2000:0:2::71")
    boot = as2.createHost("boot").joinNetwork("net0", address="10.2.0.72", ipv6Address="2000:0:2::72")
    validator = as2.createHost("validator").joinNetwork("net0", address="10.2.0.73", ipv6Address="2000:0:2::73")
    base.configure(Emulator())

    blockchain = object.__new__(Blockchain)
    blockchain._consensus = ConsensusMechanism.POS
    blockchain._chain_id = 1337
    blockchain._chain_name = "pos-helper"
    blockchain._genesis = _FakeGenesis()
    blockchain._eth_service = _FakeEthereumService()
    blockchain._boot_node_addresses = []
    blockchain._boot_node_enode_urls = []
    blockchain._beacon_node_api_urls = []
    blockchain._joined_accounts = []
    blockchain._joined_signer_accounts = []
    blockchain._validator_ids = []
    blockchain._beacon_setup_node_address = ""
    blockchain._beacon_setup_node_url = ""
    blockchain._miner_node_address = []
    blockchain._emu_mnemonic = "test mnemonic"
    blockchain._emu_account_balance = 0
    blockchain._total_accounts_per_node = 0
    blockchain.setEndpointAddressFamily(family)

    setup_server = object.__new__(PoSServer)
    PoSServer.__init__(setup_server, 1, blockchain)
    setup_server._mnemonic_accounts = []
    setup_server.setBeaconSetupNode()

    boot_server = object.__new__(PoSServer)
    PoSServer.__init__(boot_server, 2, blockchain)
    boot_server._mnemonic_accounts = []
    boot_server.setBootNode(True)

    validator_server = object.__new__(PoSServer)
    PoSServer.__init__(validator_server, 3, blockchain)
    validator_server._mnemonic_accounts = []
    validator_server._accounts = [_FakeAccount()]
    validator_server.enablePOSValidatorAtGenesis()

    blockchain._doConfigure(setup, setup_server)
    blockchain._doConfigure(boot, boot_server)
    blockchain._doConfigure(validator, validator_server)
    validator_server.install(validator, _FakeEthereumService())

    return setup, boot, validator, blockchain


def test_endpoint_helpers_format_ipv6_safely():
    assert formatHostPort("10.0.0.1", 80) == "10.0.0.1:80"
    assert formatHostPort("2000::1", 80) == "[2000::1]:80"
    assert formatHostPort(" 2000::1 ", 80) == "[2000::1]:80"
    assert formatUrl("http", "2000::1", 8080, "status") == "http://[2000::1]:8080/status"
    assert formatUrl("http", " example.test ", 8080, "status") == "http://example.test:8080/status"
    assert formatUrl("https", "example.test", path="/health") == "https://example.test/health"
    assert formatMultiaddr("10.0.0.1", 4001) == "/ip4/10.0.0.1/tcp/4001"
    assert formatMultiaddr(" 10.0.0.1 ", 4001) == "/ip4/10.0.0.1/tcp/4001"
    assert formatMultiaddr("2000::1", 4001, "peer") == "/ip6/2000::1/tcp/4001/p2p/peer"
    assert formatMultiaddr(" 2000::1 ", 4001, "peer") == "/ip6/2000::1/tcp/4001/p2p/peer"


def test_address_family_normalizer_accepts_common_padded_values():
    assert normalizeAddressFamily(" ipv4 ") == AddressFamily.IPv4
    assert normalizeAddressFamily(" IP6 ") == AddressFamily.IPv6
    assert normalizeAddressFamily("inet") == AddressFamily.IPv4
    assert normalizeAddressFamily("AF_INET6") == AddressFamily.IPv6
    assert normalizeAddressFamily(4) == AddressFamily.IPv4
    assert normalizeAddressFamily(socket.AF_INET) == AddressFamily.IPv4
    assert normalizeAddressFamily(socket.AF_INET6) == AddressFamily.IPv6
    assert normalizeAddressFamily(AddressFamily.IPv6) == AddressFamily.IPv6


def test_ethereum_faucet_template_legacy_keys_remain_ipv4_compatible():
    assert FaucetServerFileTemplates["faucet_url"].format(address="10.2.0.72", port=80) == "http://10.2.0.72:80/"
    assert FaucetServerFileTemplates["faucet_fund_url"].format(address="10.2.0.72", port=80) == "http://10.2.0.72:80/fundme"
    assert FaucetServerFileTemplates["fund_curl"].format(
        recipient="0x4444444444444444444444444444444444444444",
        amount=2,
        address="10.2.0.72",
        port=80,
    ) == "curl -X POST -d 'address=0x4444444444444444444444444444444444444444&amount=2' http://10.2.0.72:80/fundme"
    fund_accounts = FaucetServerFileTemplates["fund_accounts"].format(
        address="10.2.0.72",
        port=80,
        max_attempts=3,
        fund_command="true",
    )
    assert 'SERVER_URL="http://10.2.0.72:80"' in fund_accounts

    assert format_faucet_url("2000:0:2::72", 80) == "http://[2000:0:2::72]:80/"
    assert format_faucet_fund_url("2000:0:2::72", 80) == "http://[2000:0:2::72]:80/fundme"
    assert format_fund_curl(
        "0x4444444444444444444444444444444444444444",
        2,
        "2000:0:2::72",
        80,
    ) == "curl -X POST -d 'address=0x4444444444444444444444444444444444444444&amount=2' http://[2000:0:2::72]:80/fundme"


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


def test_binding_filter_matches_mixed_legacy_and_explicit_address_family_fields():
    emu = Emulator()
    base = Base(enableIpv6=True)

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    as2.createHost("dual").joinNetwork("net0", address="10.2.0.71", ipv6Address="2000:0:2::71")
    as2.createHost("ipv4-only").joinNetwork("net0", address="10.2.0.72", ipv6Address=None)

    emu.addLayer(base)
    emu.render()

    legacy_ipv4_with_ipv6_prefix = Binding(
        "svc",
        action=Action.FIRST,
        filter=Filter(ip="10.2.0.71", ipv6Prefix="2000:0:2::/64"),
    )
    legacy_ipv6_with_ipv4_prefix = Binding(
        "svc",
        action=Action.FIRST,
        filter=Filter(ip="2000:0:2::71", ipv4Prefix="10.2.0.0/24"),
    )
    missing_ipv6 = Binding(
        "svc",
        action=Action.FIRST,
        filter=Filter(ip="10.2.0.72", ipv6Prefix="2000:0:2::/64"),
    )

    assert legacy_ipv4_with_ipv6_prefix.getCandidate("svc", emu, peek=True).getName() == "dual"
    assert legacy_ipv6_with_ipv4_prefix.getCandidate("svc", emu, peek=True).getName() == "dual"
    assert missing_ipv6.getCandidate("svc", emu, peek=True) is None


def test_binding_filters_trim_padded_ip_and_prefix_selectors():
    emu = Emulator()
    base = Base(enableIpv6=True)

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    as2.createHost("dual").joinNetwork("net0", address="10.2.0.71", ipv6Address="2000:0:2::71")

    emu.addLayer(base)
    emu.render()

    for filter in [
        Filter(ip=" 10.2.0.71 "),
        Filter(ip=" 2000:0:2::71 "),
        Filter(ipv4=" 10.2.0.71 "),
        Filter(ipv6=" 2000:0:2::71 "),
        Filter(prefix=" 10.2.0.0/24 "),
        Filter(prefix=" 2000:0:2::/64 "),
        Filter(ipv4Prefix=" 10.2.0.0/24 "),
        Filter(ipv6Prefix=" 2000:0:2::/64 "),
    ]:
        assert Binding("svc", action=Action.FIRST, filter=filter).getCandidate("svc", emu, peek=True).getName() == "dual"


def test_binding_new_can_create_ipv6_selected_host():
    emu = Emulator()
    base = Base(enableIpv6=True)
    dns = DomainNameService()

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    dns.install("dns").addZone("example.")
    emu.addBinding(Binding("dns", filter=Filter(asn=2, ip=" 2000:0:2::53 "), action=Action.NEW))

    emu.addLayer(base)
    emu.addLayer(dns)
    emu.render()

    node = emu.getBindingFor("dns")
    assert str(node.getInterfaces()[0].getIpv6Address()) == "2000:0:2::53"


def test_binding_new_trims_padded_prefix_selector():
    emu = Emulator()
    base = Base(enableIpv6=True)
    dns = DomainNameService()

    as2 = base.createAutonomousSystem(2)
    net0 = as2.createNetwork("net0")
    dns.install("dns").addZone("example.")
    emu.addBinding(Binding("dns", filter=Filter(asn=2, prefix=" 2000:0:2::/64 "), action=Action.NEW))

    emu.addLayer(base)
    emu.addLayer(dns)
    emu.render()

    node = emu.getBindingFor("dns")
    assert node.getInterfaces()[0].getIpv6Address() in net0.getIpv6Prefix()


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


def test_ca_https_acme_urls_preserve_domain_default_and_format_ipv6_literals(tmp_path):
    web = WebServer()
    web.setServerNames(["web.example"])

    default_ca = CAServer("0.26.1")
    default_ca.setCAStore(_FakeCAStoreWithDomain(tmp_path / "default-ca", "ca.internal"))
    default_node = Node("web-default", NodeRole.Host, 2)
    default_ca.enableHTTPSFunc(default_node, web)
    default_commands = _start_commands(default_node)

    assert "https://ca.internal/acme/acme/directory" in default_commands
    assert "https://[ca.internal]" not in default_commands

    ipv6_ca = CAServer("0.26.1")
    ipv6_ca.setCAStore(_FakeCAStoreWithDomain(tmp_path / "ipv6-ca", "2000:0:2::53"))
    ipv6_node = Node("web-ipv6", NodeRole.Host, 2)
    ipv6_ca.enableHTTPSFunc(ipv6_node, web)
    ipv6_commands = _start_commands(ipv6_node)

    assert "https://[2000:0:2::53]/acme/acme/directory" in ipv6_commands
    assert "https://2000:0:2::53/acme/acme/directory" not in ipv6_commands


def test_tor_da_downloader_urls_use_shared_endpoint_helpers():
    node = _render_tor_host("tor-relay")

    tor = TorService()
    tor.addDirAuthority("10.2.0.71")
    tor.addDirAuthority("2000:0:2::71")
    TorServer().install(node, tor)
    entrypoint = _file_content(node, "/usr/local/bin/tor-entrypoint")

    assert "http://10.2.0.71:8888" in entrypoint
    assert "http://10.2.0.71:8888/torrc.da" in entrypoint
    assert "http://[2000:0:2::71]:8888" in entrypoint
    assert "http://[2000:0:2::71]:8888/torrc.da" in entrypoint
    assert "http://2000:0:2::71:8888" not in entrypoint
    assert 'TOR_HS_TARGET="${TOR_HS_ADDR}:${TOR_HS_PORT}"' in entrypoint
    assert "HiddenServicePort ${TOR_HS_PORT} ${TOR_HS_TARGET}" in entrypoint


def test_tor_hidden_service_backend_targets_use_shared_endpoint_helpers():
    node = _render_tor_host("tor-hs")

    ipv4_server = TorServer().setRole(TorNodeType.HS).setLink("10.2.0.80", 8080)
    ipv4_server.configure(node, TorService())
    assert "export TOR_HS_ADDR=10.2.0.80" in _start_commands(node)
    assert "export TOR_HS_PORT=8080" in _start_commands(node)
    assert "export TOR_HS_TARGET=10.2.0.80:8080" in _start_commands(node)

    ipv6_node = _render_tor_host("tor-hs6")
    ipv6_server = TorServer().setRole(TorNodeType.HS).setLink("2000:0:2::80", 8080)
    ipv6_server.configure(ipv6_node, TorService())
    ipv6_commands = _start_commands(ipv6_node)

    assert "export TOR_HS_ADDR=2000:0:2::80" in ipv6_commands
    assert "export TOR_HS_PORT=8080" in ipv6_commands
    assert "export TOR_HS_TARGET=[2000:0:2::80]:8080" in ipv6_commands
    assert "export TOR_HS_TARGET=2000:0:2::80:8080" not in ipv6_commands


def test_tor_hidden_service_vnode_targets_default_to_ipv4():
    node = _render_tor_hidden_service_vnode_topology()
    commands = _start_commands(node)

    assert "export TOR_HS_ADDR=10.2.0.80" in commands
    assert "export TOR_HS_PORT=8080" in commands
    assert "export TOR_HS_TARGET=10.2.0.80:8080" in commands
    assert "2000:0:2::80" not in commands


def test_tor_hidden_service_vnode_targets_can_select_ipv6():
    node = _render_tor_hidden_service_vnode_topology(AddressFamily.IPv6)
    commands = _start_commands(node)

    assert "export TOR_HS_ADDR=2000:0:2::80" in commands
    assert "export TOR_HS_PORT=8080" in commands
    assert "export TOR_HS_TARGET=[2000:0:2::80]:8080" in commands
    assert "export TOR_HS_TARGET=2000:0:2::80:8080" not in commands
    assert "export TOR_HS_TARGET=10.2.0.80:8080" not in commands


def test_tor_hidden_service_vnode_targets_fall_back_to_service_network_ipv4():
    node = _render_tor_hidden_service_vnode_topology(service_network_only=True)
    commands = _start_commands(node)

    assert "export TOR_HS_ADDR=192.168.66.80" in commands
    assert "export TOR_HS_PORT=8080" in commands
    assert "export TOR_HS_TARGET=192.168.66.80:8080" in commands
    assert "fd00:66::80" not in commands


def test_tor_hidden_service_vnode_targets_fall_back_to_service_network_ipv6():
    node = _render_tor_hidden_service_vnode_topology(
        AddressFamily.IPv6,
        service_network_only=True,
    )
    commands = _start_commands(node)

    assert "export TOR_HS_ADDR=fd00:66::80" in commands
    assert "export TOR_HS_PORT=8080" in commands
    assert "export TOR_HS_TARGET=[fd00:66::80]:8080" in commands
    assert "export TOR_HS_TARGET=fd00:66::80:8080" not in commands
    assert "export TOR_HS_TARGET=192.168.66.80:8080" not in commands


def test_botnet_dropper_endpoint_defaults_to_ipv4_url_helper():
    c2, client = _render_botnet_endpoint_topology()

    client_commands = _start_commands(client)
    runner = _file_content(client, "/tmp/byob_client_dropper_runner")

    assert c2.getAttribute("botnet_addr") == "192.168.66.71"
    assert c2.getAttribute("botnet_port") == 446
    assert (
        c2.getAttribute("botnet_dropper_url")
        == "http://192.168.66.71:446/clients/droppers/client.py"
    )
    assert 'url="$3"' in runner
    assert "http://192.168.66.71:446/clients/droppers/client.py" in client_commands
    assert "http://10.2.0.71:446/clients/droppers/client.py" not in client_commands
    assert "2000:0:2::71" not in client_commands


def test_botnet_dropper_endpoint_can_select_ipv6_url_helper():
    c2, client = _render_botnet_endpoint_topology(AddressFamily.IPv6)

    c2_commands = _start_commands(c2)
    client_commands = _start_commands(client)

    assert c2.getAttribute("botnet_addr") == "fd00:66::71"
    assert (
        c2.getAttribute("botnet_dropper_url")
        == "http://[fd00:66::71]:446/clients/droppers/client.py"
    )
    assert '/tmp/byob_server_init_script "fd00:66::71" "445"' in c2_commands
    assert "http://[fd00:66::71]:446/clients/droppers/client.py" in client_commands
    assert "http://fd00:66::71:446/clients/droppers/client.py" not in client_commands


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


def test_dns_glue_records_use_parsed_address_family():
    zone = DomainNameService().getZone("example.")

    zone.addGuleRecord("ns1.example.", "10.2.0.53")
    zone.addGuleRecord("ns2.example.", "2000:0:2::53")

    glue_records = zone.getGuleRecords()
    assert "ns1.example. A 10.2.0.53" in glue_records
    assert "ns2.example. AAAA 2000:0:2::53" in glue_records
    assert "ns1.example. NS ns1.example." not in glue_records
    assert "example. NS ns1.example." in glue_records
    assert "example. NS ns2.example." in glue_records


def test_reverse_dns_keeps_ipv4_only_default():
    emu = Emulator()
    base = Base()
    dns = DomainNameService()
    rdns = ReverseDomainNameService()

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    as2.createHost("web").joinNetwork("net0", address="10.2.0.71")

    emu.addLayer(base)
    emu.addLayer(dns)
    emu.addLayer(rdns)
    emu.render()

    arpa_subzones = dns.getRootZone().getSubZones()["arpa"].getSubZones()
    ipv4_records = dns.getZone("in-addr.arpa.").getRecords()

    assert "ip6" not in arpa_subzones
    assert "71.0.2.10 PTR web-net0.hnode.as2.net." in ipv4_records


def test_reverse_dns_emits_ipv6_ptr_records_when_available():
    emu = Emulator()
    base = Base(enableIpv6=True)
    dns = DomainNameService()
    rdns = ReverseDomainNameService()

    as2 = base.createAutonomousSystem(2)
    as2.createNetwork("net0")
    as2.createHost("ns").joinNetwork("net0", address="10.2.0.53", ipv6Address="2000:0:2::53")
    as2.createHost("web").joinNetwork("net0", address="10.2.0.71", ipv6Address="2000:0:2::71")

    dns.install("ns-rev").addZone("in-addr.arpa.").addZone("ip6.arpa.")
    emu.addBinding(Binding("ns-rev", filter=Filter(asn=2, nodeName="ns"), action=Action.FIRST))
    emu.addLayer(base)
    emu.addLayer(dns)
    emu.addLayer(rdns)
    emu.render()

    ns = emu.getRegistry().get("2", "hnode", "ns")
    ipv4_records = dns.getZone("in-addr.arpa.").getRecords()
    ipv6_records = dns.getZone("ip6.arpa.").getRecords()
    ipv6_zone_file = _file_content(ns, "/etc/bind/zones/ip6.arpa.")
    expected_ipv6_ptr = (
        "1.7.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.2.0.0.0.0.0.0.0.0.0.0.2 "
        "PTR web-net0.hnode.as2.net."
    )

    assert "71.0.2.10 PTR web-net0.hnode.as2.net." in ipv4_records
    assert expected_ipv6_ptr in ipv6_records
    assert expected_ipv6_ptr in ipv6_zone_file


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


def test_domain_registrar_dynamic_updates_allow_explicit_aaaa_records():
    node = Node("registrar", NodeRole.Host, 2)
    DomainRegistrarServer().install(node)
    domain_page = _file_content(node, "/var/www/html/domain.php")

    assert '<option value="A" selected>A</option>' in domain_page
    assert '<option value="AAAA">AAAA</option>' in domain_page
    assert "$record_type = $_POST['rtype'] ?? 'A';" in domain_page
    assert "array('A', 'AAAA')" in domain_page
    assert '.$record_type.' in domain_page
    assert '60 A ".$ip_address' not in domain_page
    assert "printf %s " in domain_page
    assert "escapeshellarg($update)" in domain_page


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


def test_kubo_getip_utility_defaults_to_ipv4_on_dual_stack_nodes():
    _, peer = _render_kubo_bootstrap_topology(KuboService())

    assert str(getIP(peer)) == "10.2.0.72"
    assert str(getIP(peer, AddressFamily.IPv6)) == "2000:0:2::72"


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


def test_kubo_getip_utility_falls_back_to_service_network():
    _, peer = _render_kubo_service_network_bootstrap_topology(KuboService())

    assert str(getIP(peer)) == "192.168.66.72"
    assert str(getIP(peer, AddressFamily.IPv6)) == "fd00:66::72"


def test_kubo_bootstrap_endpoints_fall_back_to_service_network_ipv4():
    kubo, peer = _render_kubo_service_network_bootstrap_topology(KuboService())

    script = _file_content(peer, "/tmp/kubo/bootstrap.sh")

    assert kubo.getBootstrapList() == ["192.168.66.71"]
    assert "http://192.168.66.71:5001/api/v0/config?arg=Identity.PeerID" in script
    assert "/ip4/192.168.66.71/tcp/4001" in script
    assert "fd00:66::71" not in script


def test_kubo_bootstrap_endpoints_fall_back_to_service_network_ipv6():
    kubo, peer = _render_kubo_service_network_bootstrap_topology(
        KuboService(bootstrapAddressFamily=AddressFamily.IPv6)
    )

    commands = _start_commands(peer)
    script = _file_content(peer, "/tmp/kubo/bootstrap.sh")

    assert kubo.getBootstrapList() == ["fd00:66::71"]
    assert "ipfs config Addresses.API /ip6/::/tcp/5001" in commands
    assert "http://[fd00:66::71]:5001/api/v0/config?arg=Identity.PeerID" in script
    assert "/ip6/fd00:66::71/tcp/4001" in script
    assert "http://fd00:66::71:5001" not in script


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


def test_monero_endpoints_fall_back_to_service_network_ipv4():
    client, light = _render_monero_service_network_endpoint_topology()

    client_script = _file_content(client, "/usr/local/bin/seedemu-monero-node.sh")
    light_script = _file_content(light, "/usr/local/bin/seedemu-monero-light.sh")

    assert 'DAEMON_ARGS+=("--add-exclusive-node=192.168.66.71:28080")' in client_script
    assert 'UPSTREAMS=("192.168.66.71:28081" "192.168.66.72:28081")' in light_script
    assert "fd00:66::71" not in client_script
    assert "fd00:66::71" not in light_script


def test_monero_endpoints_fall_back_to_service_network_ipv6():
    client, light = _render_monero_service_network_endpoint_topology(AddressFamily.IPv6)

    client_script = _file_content(client, "/usr/local/bin/seedemu-monero-node.sh")
    light_script = _file_content(light, "/usr/local/bin/seedemu-monero-light.sh")

    assert 'DAEMON_ARGS+=("--add-exclusive-node=[fd00:66::71]:28080")' in client_script
    assert 'UPSTREAMS=("[fd00:66::71]:28081" "[fd00:66::72]:28081")' in light_script
    assert "fd00:66::71:28080" not in client_script
    assert "192.168.66.71:28080" not in client_script
    assert "192.168.66.71:28081" not in light_script


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


def test_chainlink_generated_urls_fall_back_to_service_network_ipv4():
    chainlink, user = _render_chainlink_service_network_endpoint_topology()

    config = _file_content(chainlink, "/chainlink/config.toml")
    oracle_script = _file_content(chainlink, "/chainlink/deploy_oracle_contract.py")
    auth_sender_script = _file_content(chainlink, "/chainlink/fund_auth_sender.py")
    user_deploy_script = _file_content(user, "/chainlink_user/deploy_user_contract.py")
    user_oracle_script = _file_content(user, "/chainlink_user/get_oracle_addresses.py")
    combined = "\n".join(
        [config, oracle_script, auth_sender_script, user_deploy_script, user_oracle_script]
    )

    assert "WSURL = 'ws://192.168.66.71:8546'" in config
    assert 'eth_url    = "http://192.168.66.71:8545"' in oracle_script
    assert 'faucet_url = "http://192.168.66.72:80"' in auth_sender_script
    assert 'eth_url    = "http://192.168.66.71:8545"' in user_deploy_script
    assert 'util_server_url = "http://192.168.66.73:5000"' in user_oracle_script
    assert "fd00:66::" not in combined


def test_chainlink_generated_urls_fall_back_to_service_network_ipv6():
    chainlink, user = _render_chainlink_service_network_endpoint_topology(
        AddressFamily.IPv6
    )

    config = _file_content(chainlink, "/chainlink/config.toml")
    oracle_script = _file_content(chainlink, "/chainlink/deploy_oracle_contract.py")
    auth_sender_script = _file_content(chainlink, "/chainlink/fund_auth_sender.py")
    user_deploy_script = _file_content(user, "/chainlink_user/deploy_user_contract.py")
    user_oracle_script = _file_content(user, "/chainlink_user/get_oracle_addresses.py")
    combined = "\n".join(
        [config, oracle_script, auth_sender_script, user_deploy_script, user_oracle_script]
    )

    assert "WSURL = 'ws://[fd00:66::71]:8546'" in config
    assert 'eth_url    = "http://[fd00:66::71]:8545"' in oracle_script
    assert 'faucet_url = "http://[fd00:66::72]:80"' in auth_sender_script
    assert 'eth_url    = "http://[fd00:66::71]:8545"' in user_deploy_script
    assert 'util_server_url = "http://[fd00:66::73]:5000"' in user_oracle_script
    assert "http://fd00:66::71:8545" not in combined
    assert "ws://fd00:66::71:8546" not in combined
    assert "http://192.168.66.71:8545" not in combined


def test_ethereum_http_utility_urls_default_to_ipv4_on_dual_stack_nodes():
    faucet, utility, faucet_util = _render_ethereum_endpoint_topology()

    faucet_app = _file_content(faucet, "/faucet/app.py")
    fund_script = _file_content(faucet, "/faucet/fund_accounts.sh")
    utility_fund = _file_content(utility, "/utility_server/fund_account.py")
    utility_deploy = _file_content(utility, "/utility_server/deploy_contract.py")
    combined = "\n".join([faucet_app, fund_script, utility_fund, utility_deploy])

    assert "connect_to_geth('http://10.2.0.71:8545', 'POA')" in faucet_app
    assert 'SERVER_URL="http://localhost:80"' in fund_script
    assert "curl -X POST -d 'address=0x3333333333333333333333333333333333333333&amount=1' http://localhost:80/fundme" in fund_script
    assert 'RPC_URL    = "http://10.2.0.71:8545"' in utility_fund
    assert 'FAUCET_URL = "http://10.2.0.72:80"' in utility_fund
    assert 'request_url = "http://10.2.0.72:80/fundme"' in utility_fund
    assert 'RPC_URL    = "http://10.2.0.71:8545"' in utility_deploy
    assert faucet_util.getFacuetUrl() == "http://10.2.0.72:80/"
    assert faucet_util.getFaucetFundUrl() == "http://10.2.0.72:80/fundme"
    assert "curl -X POST -d 'address=0x4444444444444444444444444444444444444444&amount=2' http://10.2.0.72:80/fundme" == faucet_util.getFundApi(
        "0x4444444444444444444444444444444444444444",
        2,
    )
    assert "2000:0:2::" not in combined


def test_ethereum_http_utility_urls_can_select_ipv6_helpers():
    faucet, utility, faucet_util = _render_ethereum_endpoint_topology(AddressFamily.IPv6)

    faucet_app = _file_content(faucet, "/faucet/app.py")
    fund_script = _file_content(faucet, "/faucet/fund_accounts.sh")
    utility_fund = _file_content(utility, "/utility_server/fund_account.py")
    utility_deploy = _file_content(utility, "/utility_server/deploy_contract.py")
    combined = "\n".join([faucet_app, fund_script, utility_fund, utility_deploy])

    assert "connect_to_geth('http://[2000:0:2::71]:8545', 'POA')" in faucet_app
    assert 'SERVER_URL="http://localhost:80"' in fund_script
    assert 'RPC_URL    = "http://[2000:0:2::71]:8545"' in utility_fund
    assert 'FAUCET_URL = "http://[2000:0:2::72]:80"' in utility_fund
    assert 'request_url = "http://[2000:0:2::72]:80/fundme"' in utility_fund
    assert 'RPC_URL    = "http://[2000:0:2::71]:8545"' in utility_deploy
    assert faucet_util.getFacuetUrl() == "http://[2000:0:2::72]:80/"
    assert faucet_util.getFaucetFundUrl() == "http://[2000:0:2::72]:80/fundme"
    assert "curl -X POST -d 'address=0x4444444444444444444444444444444444444444&amount=2' http://[2000:0:2::72]:80/fundme" == faucet_util.getFundApi(
        "0x4444444444444444444444444444444444444444",
        2,
    )
    faucet_util.addFund("0x5555555555555555555555555555555555555555", 3)
    util_fund_script = faucet_util.getFundScript()
    assert 'SERVER_URL="http://[2000:0:2::72]:80"' in util_fund_script
    assert "curl -X POST -d 'address=0x5555555555555555555555555555555555555555&amount=3' http://[2000:0:2::72]:80/fundme" in util_fund_script
    assert "http://10.2.0.71:8545" not in combined
    assert "http://10.2.0.72:80" not in combined


def test_ethereum_http_utility_urls_fall_back_to_service_network_ipv4():
    faucet, utility, faucet_util = _render_ethereum_service_network_endpoint_topology()

    faucet_app = _file_content(faucet, "/faucet/app.py")
    utility_fund = _file_content(utility, "/utility_server/fund_account.py")
    utility_deploy = _file_content(utility, "/utility_server/deploy_contract.py")
    combined = "\n".join([faucet_app, utility_fund, utility_deploy])

    assert "connect_to_geth('http://192.168.66.71:8545', 'POA')" in faucet_app
    assert 'RPC_URL    = "http://192.168.66.71:8545"' in utility_fund
    assert 'FAUCET_URL = "http://192.168.66.72:80"' in utility_fund
    assert 'request_url = "http://192.168.66.72:80/fundme"' in utility_fund
    assert 'RPC_URL    = "http://192.168.66.71:8545"' in utility_deploy
    assert faucet_util.getFacuetUrl() == "http://192.168.66.72:80/"
    assert faucet_util.getFaucetFundUrl() == "http://192.168.66.72:80/fundme"
    assert "fd00:66::" not in combined


def test_ethereum_http_utility_urls_fall_back_to_service_network_ipv6():
    faucet, utility, faucet_util = _render_ethereum_service_network_endpoint_topology(
        AddressFamily.IPv6
    )

    faucet_app = _file_content(faucet, "/faucet/app.py")
    utility_fund = _file_content(utility, "/utility_server/fund_account.py")
    utility_deploy = _file_content(utility, "/utility_server/deploy_contract.py")
    combined = "\n".join([faucet_app, utility_fund, utility_deploy])

    assert "connect_to_geth('http://[fd00:66::71]:8545', 'POA')" in faucet_app
    assert 'RPC_URL    = "http://[fd00:66::71]:8545"' in utility_fund
    assert 'FAUCET_URL = "http://[fd00:66::72]:80"' in utility_fund
    assert 'request_url = "http://[fd00:66::72]:80/fundme"' in utility_fund
    assert 'RPC_URL    = "http://[fd00:66::71]:8545"' in utility_deploy
    assert faucet_util.getFacuetUrl() == "http://[fd00:66::72]:80/"
    assert faucet_util.getFaucetFundUrl() == "http://[fd00:66::72]:80/fundme"
    assert "http://fd00:66::71:8545" not in combined
    assert "http://192.168.66.71:8545" not in combined


def test_ethereum_bootstrap_helper_urls_default_to_ipv4_on_dual_stack_nodes():
    boot, peer, blockchain = _render_ethereum_bootstrap_endpoint_topology()

    peer_nodes = _file_content(peer, "/tmp/eth-nodes")
    bootstrapper = _file_content(peer, "/tmp/eth-bootstrapper")

    assert blockchain.getBootNodes() == ["10.2.0.71"]
    assert blockchain.getBootNodeEnodeUrls() == ["http://10.2.0.71:8088/eth-enode-url"]
    assert _file_content(boot, "/tmp/eth-nodes") == "http://10.2.0.71:8088/eth-enode-url"
    assert peer_nodes == "http://10.2.0.71:8088/eth-enode-url"
    assert 'curl -sHf "$node"' in bootstrapper
    assert '$(curl -s "$node")' in bootstrapper
    assert "http://$node:8088/eth-enode-url" not in bootstrapper
    assert "2000:0:2::" not in peer_nodes


def test_ethereum_bootstrap_helper_urls_can_select_ipv6_helpers():
    boot, peer, blockchain = _render_ethereum_bootstrap_endpoint_topology(AddressFamily.IPv6)

    peer_nodes = _file_content(peer, "/tmp/eth-nodes")
    bootstrapper = _file_content(peer, "/tmp/eth-bootstrapper")

    assert blockchain.getBootNodes() == ["10.2.0.71"]
    assert blockchain.getBootNodeEnodeUrls() == ["http://[2000:0:2::71]:8088/eth-enode-url"]
    assert _file_content(boot, "/tmp/eth-nodes") == "http://[2000:0:2::71]:8088/eth-enode-url"
    assert peer_nodes == "http://[2000:0:2::71]:8088/eth-enode-url"
    assert 'curl -sHf "$node"' in bootstrapper
    assert '$(curl -s "$node")' in bootstrapper
    assert "http://2000:0:2::71:8088/eth-enode-url" not in peer_nodes
    assert "http://10.2.0.71:8088/eth-enode-url" not in peer_nodes


def test_ethereum_bootstrap_helper_urls_fall_back_to_service_network_ipv4():
    boot, peer, blockchain = _render_ethereum_service_network_bootstrap_endpoint_topology()

    peer_nodes = _file_content(peer, "/tmp/eth-nodes")

    assert blockchain.getBootNodes() == ["192.168.66.71"]
    assert blockchain.getBootNodeEnodeUrls() == ["http://192.168.66.71:8088/eth-enode-url"]
    assert _file_content(boot, "/tmp/eth-nodes") == "http://192.168.66.71:8088/eth-enode-url"
    assert peer_nodes == "http://192.168.66.71:8088/eth-enode-url"
    assert "fd00:66::" not in peer_nodes


def test_ethereum_bootstrap_helper_urls_fall_back_to_service_network_ipv6():
    boot, peer, blockchain = _render_ethereum_service_network_bootstrap_endpoint_topology(
        AddressFamily.IPv6
    )

    peer_nodes = _file_content(peer, "/tmp/eth-nodes")

    assert blockchain.getBootNodes() == ["192.168.66.71"]
    assert blockchain.getBootNodeEnodeUrls() == ["http://[fd00:66::71]:8088/eth-enode-url"]
    assert _file_content(boot, "/tmp/eth-nodes") == "http://[fd00:66::71]:8088/eth-enode-url"
    assert peer_nodes == "http://[fd00:66::71]:8088/eth-enode-url"
    assert "http://fd00:66::71:8088/eth-enode-url" not in peer_nodes
    assert "http://192.168.66.71:8088/eth-enode-url" not in peer_nodes


def test_ethereum_pos_helper_urls_default_to_ipv4_on_dual_stack_nodes():
    _setup, _boot, validator, blockchain = _render_ethereum_pos_helper_endpoint_topology()

    beacon_setup_node = _file_content(validator, "/tmp/beacon-setup-node")
    enode_nodes = _file_content(validator, "/tmp/eth-nodes")
    beacon_nodes = _file_content(validator, "/tmp/beacon-nodes")
    fetch_bn_enr = _file_content(validator, "/tmp/fetch_bn_enr")
    beacon_bootstrapper = _file_content(validator, "/tmp/beacon-bootstrapper")

    assert blockchain.getBeaconSetupNodeIp() == "10.2.0.71:8090"
    assert blockchain.getBeaconSetupNodeUrl() == "http://10.2.0.71:8090/testnet"
    assert blockchain.getBeaconNodeApiUrls() == ["http://10.2.0.72:8000/eth/v1/node/identity"]
    assert beacon_setup_node == "http://10.2.0.71:8090/testnet"
    assert enode_nodes == "http://10.2.0.72:8088/eth-enode-url"
    assert beacon_nodes == "http://10.2.0.72:8000/eth/v1/node/identity"
    assert 'curl -s "$url"' in fetch_bn_enr
    assert "http://$ip:8000/eth/v1/node/identity" not in fetch_bn_enr
    assert 'curl --http0.9 -sHf "$node"' in beacon_bootstrapper
    assert 'curl --http0.9 -s "$node"' in beacon_bootstrapper
    assert "http://$node/testnet" not in beacon_bootstrapper
    assert "2000:0:2::" not in "\n".join([beacon_setup_node, beacon_nodes])


def test_ethereum_pos_helper_urls_can_select_ipv6_helpers():
    _setup, _boot, validator, blockchain = _render_ethereum_pos_helper_endpoint_topology(AddressFamily.IPv6)

    beacon_setup_node = _file_content(validator, "/tmp/beacon-setup-node")
    enode_nodes = _file_content(validator, "/tmp/eth-nodes")
    beacon_nodes = _file_content(validator, "/tmp/beacon-nodes")
    fetch_bn_enr = _file_content(validator, "/tmp/fetch_bn_enr")
    beacon_bootstrapper = _file_content(validator, "/tmp/beacon-bootstrapper")

    assert blockchain.getBeaconSetupNodeIp() == "10.2.0.71:8090"
    assert blockchain.getBeaconSetupNodeUrl() == "http://[2000:0:2::71]:8090/testnet"
    assert blockchain.getBeaconNodeApiUrls() == ["http://[2000:0:2::72]:8000/eth/v1/node/identity"]
    assert beacon_setup_node == "http://[2000:0:2::71]:8090/testnet"
    assert enode_nodes == "http://[2000:0:2::72]:8088/eth-enode-url"
    assert beacon_nodes == "http://[2000:0:2::72]:8000/eth/v1/node/identity"
    assert 'curl -s "$url"' in fetch_bn_enr
    assert 'curl --http0.9 -sHf "$node"' in beacon_bootstrapper
    assert 'curl --http0.9 -s "$node"' in beacon_bootstrapper
    assert "http://2000:0:2::71:8090/testnet" not in beacon_setup_node
    assert "http://2000:0:2::72:8000/eth/v1/node/identity" not in beacon_nodes
    assert "http://10.2.0.71:8090/testnet" not in beacon_setup_node
    assert "http://10.2.0.72:8000/eth/v1/node/identity" not in beacon_nodes
