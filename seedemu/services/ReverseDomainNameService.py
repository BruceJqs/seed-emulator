from ipaddress import IPv6Address

from .DomainNameService import DomainNameService, DomainNameServer
from seedemu.core import (
    AddressFamily,
    Node,
    Emulator,
    Service,
    Server,
    getInterfaceAddress,
)


def _reverseIpv4Address(address) -> str:
    return '.'.join(reversed(str(address).split('.')))


def _reverseIpv6Address(address) -> str:
    return '.'.join(reversed(IPv6Address(str(address)).exploded.replace(':', '')))


class ReverseDomainNameServer(Server):
    """!
    @brief Reverse DNS server.
    """

    def install(self, node: Node):
        pass

class ReverseDomainNameService(Service):
    """!
    @brief Reverse DNS. This service populates the in-addr.arpa. and ip6.arpa.
    zones and resolves IP addresses to nodename-netname.nodetype.asn.net
    """

    __dns: DomainNameService

    def __init__(self):
        """!
        @brief ReverseDomainNameService constructor
        """
        super().__init__()
        self.addDependency('DomainNameService', True, False)
        self.addDependency('Base', False, False)

    def getName(self) -> str:
        return 'ReverseDomainNameService'

    def _createServer(self) -> Server:
        return ReverseDomainNameServer()

    def install(self, vnode: str) -> Server:
        assert False, 'ReverseDomainNameService is not a real service and should not be installed this way. Please install a DomainNameService on the node and host the zones "in-addr.arpa." and "ip6.arpa." yourself.'

    def configure(self, emulator: Emulator):
        reg = emulator.getRegistry()

        self._log('Creating "in-addr.arpa." zone...')
        self.__dns = reg.get('seedemu', 'layer', 'DomainNameService')
        ipv4_zone = self.__dns.getZone('in-addr.arpa.')
        ipv6_zone = None

        self._log('Collecting IP addresses...')
        for ([scope, type, name], obj) in reg.getAll().items():
            if type != 'rnode' and type != 'hnode': continue
            self._log('Collecting {}/{}/{}...'.format(scope, type, name))

            if scope == 'ix':
                scope = name
                name = 'rs'
            else: scope = 'as' + scope

            node: Node = obj
            for iface in node.getInterfaces():
                netname = iface.getNet().getName()
                ptr_name = '{}-{}.{}.{}.net.'.format(name, netname, type, scope).replace('_', '-')

                ipv4_addr = getInterfaceAddress(iface, AddressFamily.IPv4)
                if ipv4_addr is not None:
                    record = '{} PTR {}'.format(_reverseIpv4Address(ipv4_addr), ptr_name)
                    ipv4_zone.addRecord(record)

                ipv6_addr = getInterfaceAddress(iface, AddressFamily.IPv6)
                if ipv6_addr is not None:
                    if ipv6_zone is None:
                        self._log('Creating "ip6.arpa." zone...')
                        ipv6_zone = self.__dns.getZone('ip6.arpa.')
                    record = '{} PTR {}'.format(_reverseIpv6Address(ipv6_addr), ptr_name)
                    ipv6_zone.addRecord(record)

        return super().configure(emulator)

    def print(self, indent: int) -> str:
        out = ' ' * indent
        out += 'ReverseDomainNameService\n'

        return out
