from __future__ import annotations
from .Routing import Router
from seedemu.core import Registry, ScopedRegistry, Network, Interface, Graphable, Emulator, Layer
from seedemu.core.enums import NodeRole
from typing import Tuple, List, Dict
from enum import Enum

from ._bgp_metadata import install_router_bgp_session, record_bgp_session, render_bird_protocol_body, split_bgp_session_families

EbgpFileTemplates: Dict[str, str] = {}

EbgpFileTemplates["bgp_commons"] = """\
define LOCAL_COMM = ({localAsn}, 0, 0);
define CUSTOMER_COMM = ({localAsn}, 1, 0);
define PEER_COMM = ({localAsn}, 2, 0);
define PROVIDER_COMM = ({localAsn}, 3, 0);
"""

EbgpFileTemplates["rs_bird_peer"] =  """
    ipv4 {{
        import all;
        export all;
    }};
    rs client;
    local {localAddress} as {localAsn};
    neighbor {peerAddress} as {peerAsn};
"""

EbgpFileTemplates["rnode_bird_peer"] = """
    ipv4 {{
        table t_bgp;
        import filter {{
            bgp_large_community.add({importCommunity});
            bgp_local_pref = {bgpPref};
            accept;
        }};
        export {exportFilter};
        next hop self;
    }};
    local {localAddress} as {localAsn};
    neighbor {peerAddress} as {peerAsn};
"""

class PeerRelationship(Enum):
    """!
    @brief Relationship between peers.
    """

    ## Provider: a side: export everything, b side: export only customer's and
    ## own prefixes
    Provider = "Provider"

    ## Peer: a side & b side: only export customer's and own prefixes.
    Peer = "Peer"

    ## Unfiltered: no filter on both sides
    Unfiltered = "Unfiltered"

class Ebgp(Layer, Graphable):
    """!
    @brief The Ebgp (eBGP) layer.

    This layer enable eBGP peering in InternetExchange.
    """

    __peerings: Dict[Tuple[int, int, int], PeerRelationship]
    __rs_peers: List[Tuple[int, int]]
    __xc_peerings: Dict[Tuple[int, int], PeerRelationship]

    def __init__(self):
        """!
        @brief Ebgp layer constructor.
        """
        super().__init__()
        self.__peerings = {}
        self.__xc_peerings = {}
        self.__rs_peers = []
        self.addDependency('Routing', False, False)

    def __createPeer(self, nodeA: Router, nodeB: Router, ifaceA: Interface, ifaceB: Interface, rel: PeerRelationship) -> None:
        rsNode: Router = None
        routerA: Router = None
        routerB: Router = None
        rsIface: Interface = None
        routerAIface: Interface = None
        routerBIface: Interface = None

        for node, iface in [(nodeA, ifaceA), (nodeB, ifaceB)]:
            if node.getRegistryInfo()[1] == 'rs':
                rsNode = node
                rsIface = iface
                continue
            if routerA is None:
                routerA = node
                routerAIface = iface
            elif routerB is None:
                routerB = node
                routerBIface = iface

        assert routerA is not None, 'both nodes are RS node. cannot setup peering.'
        assert routerA != routerB, 'cannot peer with oneself.'

        addrA = str(routerAIface.getAddress() if routerAIface is not None else rsIface.getAddress())
        addrB = str(routerBIface.getAddress() if routerBIface is not None else rsIface.getAddress())
        ipv6A = routerAIface.getIpv6Address() if routerAIface is not None else rsIface.getIpv6Address()
        ipv6B = routerBIface.getIpv6Address() if routerBIface is not None else rsIface.getIpv6Address()
        families = ["ipv4"]
        if ipv6A is not None and ipv6B is not None:
            families.append("ipv6")

        if rsNode is not None:
            assert rsIface is not None and routerAIface is not None, 'route-server peering is missing interface state'
            rs_addr = str(rsIface.getAddress())
            router_addr = str(routerAIface.getAddress())
            rs_ipv6 = rsIface.getIpv6Address()
            router_ipv6 = routerAIface.getIpv6Address()
            rs_families = ["ipv4"]
            if rs_ipv6 is not None and router_ipv6 is not None:
                rs_families.append("ipv6")
            rs_session = record_bgp_session(
                rsNode,
                {
                    "name": 'p_as{}'.format(routerA.getAsn()),
                    "kind": "ebgp",
                    "local_address": rs_addr,
                    "local_ipv6_address": str(rs_ipv6) if rs_ipv6 is not None else "",
                    "local_asn": rsNode.getAsn(),
                    "peer_address": router_addr,
                    "peer_ipv6_address": str(router_ipv6) if router_ipv6 is not None else "",
                    "peer_asn": routerA.getAsn(),
                    "families": rs_families,
                    "import_community": None,
                    "local_pref": None,
                    "export_policy": "all",
                    "next_hop_self": False,
                    "route_server_client": True,
                },
            )
            for rs_family_session in split_bgp_session_families(rs_session):
                rsNode.addProtocol('bgp', rs_family_session["name"], render_bird_protocol_body(rs_family_session))
            install_router_bgp_session(
                routerA,
                {
                    "name": 'p_rs{}'.format(rsNode.getAsn()),
                    "kind": "ebgp",
                    "local_address": router_addr,
                    "local_ipv6_address": str(router_ipv6) if router_ipv6 is not None else "",
                    "local_asn": routerA.getAsn(),
                    "peer_address": rs_addr,
                    "peer_ipv6_address": str(rs_ipv6) if rs_ipv6 is not None else "",
                    "peer_asn": rsNode.getAsn(),
                    "families": rs_families,
                    "import_community": "PEER_COMM",
                    "local_pref": 20,
                    "export_policy": "local_and_customer",
                    "next_hop_self": True,
                    "route_server_client": False,
                },
            )
            return

        if rel == PeerRelationship.Peer:
            install_router_bgp_session(
                routerA,
                {
                    "name": 'p_as{}'.format(routerB.getAsn()),
                    "kind": "ebgp",
                    "local_address": addrA,
                    "local_ipv6_address": str(ipv6A) if ipv6A is not None else "",
                    "local_asn": routerA.getAsn(),
                    "peer_address": addrB,
                    "peer_ipv6_address": str(ipv6B) if ipv6B is not None else "",
                    "peer_asn": routerB.getAsn(),
                    "families": families,
                    "import_community": "PEER_COMM",
                    "local_pref": 20,
                    "export_policy": "local_and_customer",
                    "next_hop_self": True,
                    "route_server_client": False,
                },
            )
            install_router_bgp_session(
                routerB,
                {
                    "name": 'p_as{}'.format(routerA.getAsn()),
                    "kind": "ebgp",
                    "local_address": addrB,
                    "local_ipv6_address": str(ipv6B) if ipv6B is not None else "",
                    "local_asn": routerB.getAsn(),
                    "peer_address": addrA,
                    "peer_ipv6_address": str(ipv6A) if ipv6A is not None else "",
                    "peer_asn": routerA.getAsn(),
                    "families": families,
                    "import_community": "PEER_COMM",
                    "local_pref": 20,
                    "export_policy": "local_and_customer",
                    "next_hop_self": True,
                    "route_server_client": False,
                },
            )

        if rel == PeerRelationship.Provider:
            install_router_bgp_session(
                routerA,
                {
                    "name": 'c_as{}'.format(routerB.getAsn()),
                    "kind": "ebgp",
                    "local_address": addrA,
                    "local_ipv6_address": str(ipv6A) if ipv6A is not None else "",
                    "local_asn": routerA.getAsn(),
                    "peer_address": addrB,
                    "peer_ipv6_address": str(ipv6B) if ipv6B is not None else "",
                    "peer_asn": routerB.getAsn(),
                    "families": families,
                    "import_community": "CUSTOMER_COMM",
                    "local_pref": 30,
                    "export_policy": "all",
                    "next_hop_self": True,
                    "route_server_client": False,
                },
            )
            install_router_bgp_session(
                routerB,
                {
                    "name": 'u_as{}'.format(routerA.getAsn()),
                    "kind": "ebgp",
                    "local_address": addrB,
                    "local_ipv6_address": str(ipv6B) if ipv6B is not None else "",
                    "local_asn": routerB.getAsn(),
                    "peer_address": addrA,
                    "peer_ipv6_address": str(ipv6A) if ipv6A is not None else "",
                    "peer_asn": routerA.getAsn(),
                    "families": families,
                    "import_community": "PROVIDER_COMM",
                    "local_pref": 10,
                    "export_policy": "local_and_customer",
                    "next_hop_self": True,
                    "route_server_client": False,
                },
            )

        if rel == PeerRelationship.Unfiltered:
            install_router_bgp_session(
                routerA,
                {
                    "name": 'x_as{}'.format(routerB.getAsn()),
                    "kind": "ebgp",
                    "local_address": addrA,
                    "local_ipv6_address": str(ipv6A) if ipv6A is not None else "",
                    "local_asn": routerA.getAsn(),
                    "peer_address": addrB,
                    "peer_ipv6_address": str(ipv6B) if ipv6B is not None else "",
                    "peer_asn": routerB.getAsn(),
                    "families": families,
                    "import_community": "CUSTOMER_COMM",
                    "local_pref": 30,
                    "export_policy": "all",
                    "next_hop_self": True,
                    "route_server_client": False,
                },
            )
            install_router_bgp_session(
                routerB,
                {
                    "name": 'x_as{}'.format(routerA.getAsn()),
                    "kind": "ebgp",
                    "local_address": addrB,
                    "local_ipv6_address": str(ipv6B) if ipv6B is not None else "",
                    "local_asn": routerB.getAsn(),
                    "peer_address": addrA,
                    "peer_ipv6_address": str(ipv6A) if ipv6A is not None else "",
                    "peer_asn": routerA.getAsn(),
                    "families": families,
                    "import_community": "PROVIDER_COMM",
                    "local_pref": 10,
                    "export_policy": "all",
                    "next_hop_self": True,
                    "route_server_client": False,
                },
            )

    def getName(self) -> str:
        return "Ebgp"

    def addPrivatePeering(self, ix: int, a: int, b: int, abRelationship: PeerRelationship = PeerRelationship.Peer) -> Ebgp:
        """!
        @brief Setup private peering between two ASes in IX.

        @param ix IXP id.
        @param a First ASN.
        @param b Second ASN.
        @param abRelationship (optional) A and B's relationship. If set to
        PeerRelationship.Provider, A will export everything to B, if set to
        PeerRelationship.Peer, A will only export own and customer prefixes to
        B. Default to Peer.

        @throws AssertionError if peering already exist.

        @returns self, for chaining API calls.
        """
        assert (ix, a, b) not in self.__peerings, '{} <-> {} already peered at IX{}'.format(a, b, ix)
        assert (ix, b, a) not in self.__peerings, '{} <-> {} already peered at IX{}'.format(b, a, ix)
        assert abRelationship == PeerRelationship.Peer or abRelationship == PeerRelationship.Provider or abRelationship == PeerRelationship.Unfiltered, 'unknown peering relationship {}'.format(abRelationship)

        self.__peerings[(ix, a, b)] = abRelationship

        return self

    def addPrivatePeerings(self, ix: int, a_asns: List[int], b_asns: List[int], abRelationship: PeerRelationship = PeerRelationship.Peer) -> Ebgp:
        """!
        @brief Setup private peering between two sets of ASes in IX.

        @param ix IXP id.
        @param a_asns First set of ASNs.
        @param b_asns Second set of ASNs.
        @param abRelationship (optional) A and B's relationship. If set to
        PeerRelationship.Provider, A will export everything to B, if set to
        PeerRelationship.Peer, A will only export own and customer prefixes to
        B. Default to Peer.

        @throws AssertionError if peering already exist.

        @returns self, for chaining API calls.
        """
        for a in a_asns:
            for b in b_asns:
                self.addPrivatePeering(ix, a, b, abRelationship)

        return self

    def getPrivatePeerings(self) -> Dict[Tuple[int, int, int], PeerRelationship]:
        """!
        @brief Get private peerings.

        @returns dict, where key is tuple of (ix, asnA, asnB) and value is peering relationship.
        """
        return self.__peerings

    def addCrossConnectPeering(self, a: int, b: int, abRelationship: PeerRelationship = PeerRelationship.Peer) -> Ebgp:
        """!
        @brief add cross-connect peering.

        @param a First ASN.
        @param b Second ASN.
        @param abRelationship (optional) A and B's relationship. If set to
        PeerRelationship.Provider, A will export everything to B, if set to
        PeerRelationship.Peer, A will only export own and customer prefixes to
        B. Default to Peer.

        @throws AssertionError if peering already exist.

        @returns self, for chaining API calls.
        """
        assert (a, b) not in self.__xc_peerings, '{} <-> {} already configured as XC peer'.format(a, b)
        assert (b, a) not in self.__xc_peerings, '{} <-> {} already configured as XC peer'.format(b, a)
        assert abRelationship == PeerRelationship.Peer or abRelationship == PeerRelationship.Provider or abRelationship == PeerRelationship.Unfiltered, 'unknown peering relationship {}'.format(abRelationship)

        self.__xc_peerings[(a, b)] = abRelationship

        return self

    def getCrossConnectPeerings(self) -> Dict[Tuple[int, int], PeerRelationship]:
        """!
        @brief get cross-connect peerings.

        @returns dict,  where key is tuple of (asnA, asnB) and value is peering relationship.
        """
        return self.__xc_peerings

    def addRsPeer(self, ix: int, peer: int) -> Ebgp:
        """!
        @brief Setup RS peering for an AS.

        @param ix IXP id.
        @param peer Participant ASN.

        @throws AssertionError if peering already exist.

        @returns self, for chaining API calls.
        """
        assert (ix, peer) not in self.__rs_peers, '{} already peered with RS at IX{}'.format(peer, ix)

        self.__rs_peers.append((ix, peer))

        return self

    def addRsPeers(self, ix: int, peers: List[int]):
        """!
        @brief Setup RS peering for list of ASes.

        @param ix IXP id.
        @param peers List of participant ASNs.

        @throws AssertionError if some peering already exist.

        @returns self, for chaining API calls.
        """
        for peer in peers:
            self.addRsPeer(ix, peer)

        return self

    def getRsPeers(self) -> List[Tuple[int, int]]:
        """!
        @brief Get RS peers.

        @returns list of tuple of (ix, peerAsn)
        """
        return self.__rs_peers

    def configure(self, emulator: Emulator) -> None:
        reg = emulator.getRegistry()

        for (ix, peer) in self.__rs_peers:
            ix_reg = ScopedRegistry('ix', reg)
            p_reg = ScopedRegistry(str(peer), reg)

            ix_net: Network = ix_reg.get('net', 'ix{}'.format(ix))
            ix_rs: Router = ix_reg.get('rs', 'ix{}'.format(ix))
            rs_ifs = ix_rs.getInterfaces()
            assert len(rs_ifs) == 1, '??? ix{} rs has {} interfaces.'.format(ix, len(rs_ifs))
            rs_if = rs_ifs[0]

            p_rnodes: List[Router] = p_reg.getByType('brdnode')
            p_ixnode: Router = None
            p_ixif: Interface = None
            for node in p_rnodes:
                if p_ixnode != None: break
                for iface in node.getInterfaces():
                    if iface.getNet() == ix_net:
                        p_ixnode = node
                        p_ixif = iface
                        break

            assert p_ixnode != None, 'cannot resolve peering: as{} not in ix{}'.format(peer, ix)
            self._log("adding peering: {} as {} (RS) <-> {} as {}".format(rs_if.getAddress(), ix, p_ixif.getAddress(), peer))

            self.__createPeer(ix_rs, p_ixnode, rs_if, p_ixif, PeerRelationship.Peer)

        for (a, b), rel in self.__xc_peerings.items():
            a_reg = ScopedRegistry(str(a), reg)
            b_reg = ScopedRegistry(str(b), reg)

            a_router: Router = None
            b_router: Router = None

            a_addr: str = None
            b_addr: str = None

            hit = False

            for node in a_reg.getByType('brdnode'):
                router: Router = node
                for (peername, peerasn), (localaddr, _, _) in router.getCrossConnects().items():
                    if peerasn != b: continue
                    if not b_reg.has('brdnode', peername): continue

                    hit = True
                    a_router = node
                    b_router = b_reg.get('brdnode', peername)

                    a_addr = str(localaddr.ip)
                    (b_ifaddr, _, _) = b_router.getCrossConnect(a, a_router.getName())
                    b_addr = str(b_ifaddr.ip)

                    break
                if hit: break

            assert hit, 'cannot find XC to configure peer AS{} <--> AS{}'.format(a, b)

            self._log("adding XC peering: {} as {} <-({})-> {} as {}".format(a_addr, a, rel, b_addr, b))

            def install_xc_session(router: Router, name: str, local_addr: str, peer_router: Router, peer_addr: str, import_community: str, local_pref: int, export_policy: str) -> None:
                install_router_bgp_session(
                    router,
                    {
                        "name": name,
                        "kind": "ebgp",
                        "local_address": local_addr,
                        "local_asn": router.getAsn(),
                        "peer_address": peer_addr,
                        "peer_asn": peer_router.getAsn(),
                        "families": ["ipv4"],
                        "import_community": import_community,
                        "local_pref": local_pref,
                        "export_policy": export_policy,
                        "next_hop_self": True,
                        "route_server_client": False,
                    },
                )

            if rel == PeerRelationship.Peer:
                install_xc_session(a_router, 'p_as{}'.format(b_router.getAsn()), a_addr, b_router, b_addr, "PEER_COMM", 20, "local_and_customer")
                install_xc_session(b_router, 'p_as{}'.format(a_router.getAsn()), b_addr, a_router, a_addr, "PEER_COMM", 20, "local_and_customer")

            if rel == PeerRelationship.Provider:
                install_xc_session(a_router, 'c_as{}'.format(b_router.getAsn()), a_addr, b_router, b_addr, "CUSTOMER_COMM", 30, "all")
                install_xc_session(b_router, 'u_as{}'.format(a_router.getAsn()), b_addr, a_router, a_addr, "PROVIDER_COMM", 10, "local_and_customer")

            if rel == PeerRelationship.Unfiltered:
                install_xc_session(a_router, 'x_as{}'.format(b_router.getAsn()), a_addr, b_router, b_addr, "CUSTOMER_COMM", 30, "all")
                install_xc_session(b_router, 'x_as{}'.format(a_router.getAsn()), b_addr, a_router, a_addr, "PROVIDER_COMM", 10, "all")

        for (ix, a, b), rel in self.__peerings.items():
            ix_reg = ScopedRegistry('ix', reg)
            a_reg = ScopedRegistry(str(a), reg)
            b_reg = ScopedRegistry(str(b), reg)

            ix_net: Network = ix_reg.get('net', 'ix{}'.format(ix))
            a_rnodes: List[Router] = a_reg.getByType('rnode')
            b_rnodes: List[Router] = b_reg.getByType('rnode')

            a_ixnode: Router = None
            a_ixif: Interface = None
            for node in a_rnodes:
                if a_ixnode != None: break
                for iface in node.getInterfaces():
                    if iface.getNet() == ix_net:
                        a_ixnode = node
                        a_ixif = iface
                        break

            assert a_ixnode != None, 'cannot resolve peering: as{} not in ix{}'.format(a, ix)

            b_ixnode: Router = None
            b_ixif: Interface = None
            for node in b_rnodes:
                if b_ixnode != None: break
                for iface in node.getInterfaces():
                    if iface.getNet() == ix_net:
                        b_ixnode = node
                        b_ixif = iface
                        break

            assert b_ixnode != None, 'cannot resolve peering: as{} not in ix{}'.format(b, ix)

            self._log("adding IX peering: {} as {} <-({})-> {} as {}".format(a_ixif.getAddress(), a, rel, b_ixif.getAddress(), b))

            self.__createPeer(a_ixnode, b_ixnode, a_ixif, b_ixif, rel)

    def render(self, emulator: Emulator) -> None:
        pass

    def _doCreateGraphs(self, emulator: Emulator):
        # creates the following:
        # - ebgp peering, all ASes in one graph
        # - ebgp peering, one for each ix
        # mlpa peer (i.e., via rs): dashed line
        # private peer: solid line

        full_graph = self._addGraph('All Peering Sessions', False)

        ix_list = set()
        for (i, _) in self.__rs_peers: ix_list.add(i)
        for (i, _, _), _ in self.__peerings.items(): ix_list.add(i)
        for ix in ix_list:
            self._log('Creating RS peering sessions graph for IX{}...'.format(ix))
            ix_graph = self._addGraph('IX{} Peering Sessions'.format(ix), False)

            mesh_ases = set()

            for (i, a) in self.__rs_peers:
                if i == ix: mesh_ases.add(a)

            self._log('IX{} RS-mesh: {}'.format(ix, mesh_ases))

            while len(mesh_ases) > 0:
                a = mesh_ases.pop()
                if not full_graph.hasVertex('AS{}'.format(a), 'IX{}'.format(ix)):
                    full_graph.addVertex('AS{}'.format(a), 'IX{}'.format(ix))
                if not ix_graph.hasVertex('AS{}'.format(a), 'IX{}'.format(ix)):
                    ix_graph.addVertex('AS{}'.format(a), 'IX{}'.format(ix))
                for b in mesh_ases:
                    if not full_graph.hasVertex('AS{}'.format(b), 'IX{}'.format(ix)):
                        full_graph.addVertex('AS{}'.format(b), 'IX{}'.format(ix))
                    if not ix_graph.hasVertex('AS{}'.format(b), 'IX{}'.format(ix)):
                        ix_graph.addVertex('AS{}'.format(b), 'IX{}'.format(ix))

                    full_graph.addEdge('AS{}'.format(a), 'AS{}'.format(b), 'IX{}'.format(ix), 'IX{}'.format(ix), style = 'dashed', alabel = 'R', blabel= 'R')
                    ix_graph.addEdge('AS{}'.format(a), 'AS{}'.format(b), 'IX{}'.format(ix), 'IX{}'.format(ix), style = 'dashed', alabel = 'R', blabel= 'R')

        for (i, a, b), rel in self.__peerings.items():
            self._log('Creating private peering sessions graph for IX{} AS{} <-> AS{}...'.format(i, a, b))

            ix_graph = self._addGraph('IX{} Peering Sessions'.format(i), False)

            if not full_graph.hasVertex('AS{}'.format(a), 'IX{}'.format(i)):
                full_graph.addVertex('AS{}'.format(a), 'IX{}'.format(i))
            if not ix_graph.hasVertex('AS{}'.format(a), 'IX{}'.format(i)):
                ix_graph.addVertex('AS{}'.format(a), 'IX{}'.format(i))

            if not full_graph.hasVertex('AS{}'.format(b), 'IX{}'.format(i)):
                full_graph.addVertex('AS{}'.format(b), 'IX{}'.format(i))
            if not ix_graph.hasVertex('AS{}'.format(b), 'IX{}'.format(i)):
                ix_graph.addVertex('AS{}'.format(b), 'IX{}'.format(i))

            if rel == PeerRelationship.Peer:
                full_graph.addEdge('AS{}'.format(a), 'AS{}'.format(b), 'IX{}'.format(i), 'IX{}'.format(i), alabel = 'P', blabel= 'P')
                ix_graph.addEdge('AS{}'.format(a), 'AS{}'.format(b), 'IX{}'.format(i), 'IX{}'.format(i), alabel = 'P', blabel= 'P')

            if rel == PeerRelationship.Provider:
                full_graph.addEdge('AS{}'.format(a), 'AS{}'.format(b), 'IX{}'.format(i), 'IX{}'.format(i), alabel = 'U', blabel = 'C')
                ix_graph.addEdge('AS{}'.format(a), 'AS{}'.format(b), 'IX{}'.format(i), 'IX{}'.format(i), alabel = 'U', blabel = 'C')

            if rel == PeerRelationship.Unfiltered:
                full_graph.addEdge('AS{}'.format(a), 'AS{}'.format(b), 'IX{}'.format(i), 'IX{}'.format(i), alabel = 'X', blabel= 'X')
                ix_graph.addEdge('AS{}'.format(a), 'AS{}'.format(b), 'IX{}'.format(i), 'IX{}'.format(i), alabel = 'X', blabel= 'X')

        # todo: XC peering graphs

        es = list(full_graph.vertices.values())
        while len(es) > 0:
            a = es.pop()
            for b in es:
                if a.name == b.name:
                    full_graph.addEdge(a.name, b.name, a.group, b.group, style = 'dotted', alabel = 'I', blabel= 'I')


    def print(self, indent: int) -> str:
        out = ' ' * indent
        out += 'EbgpLayer:\n'

        indent += 4
        for (i, a) in self.__rs_peers:
            out += ' ' * indent
            out += 'IX{}: RS <-> AS{}\n'.format(i, a)

        for (i, a, b), rel in self.__peerings.items():
            out += ' ' * indent
            out += 'IX{}: AS{} <--({})--> AS{}\n'.format(i, a, rel, b)


        return out
