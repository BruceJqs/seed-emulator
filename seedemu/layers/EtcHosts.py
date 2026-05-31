from seedemu.core import Emulator, Layer, Node
from seedemu.core.enums import NetworkType
from typing import List
from ipaddress import ip_address

class EtcHosts(Layer):
    """!
    @brief The EtcHosts layer.

    This layer setups host names for all nodes.
    """

    def __init__(self, only_hosts: bool = True):
        """!
        @brief EtcHosts Layer constructor
        @param only_hosts whether or not to create entries
               for all nodes inluding routers etc. or just hosts
        """
        self._only_hosts = only_hosts
        super().__init__()
        self.addDependency('Base', False, False)

    def getName(self) -> str:
        return "EtcHosts"

    def __getAllIpAddress(self, node: Node) -> list:
        """!
        @brief Get local IPv4 and IPv6 addresses for this node.
        """
        addresses = []
        for iface in node.getInterfaces():
            if iface.getNet().getType() == NetworkType.Bridge:
                pass
            if iface.getNet().getType() == NetworkType.InternetExchange:
                pass
            else:
                if iface.getAddress() is not None:
                    addresses.append(str(iface.getAddress()))
                if iface.hasIpv6Address():
                    addresses.append(str(iface.getIpv6Address()))

        return addresses

    def __addressSortKey(self, entry: str):
        address = entry.split()[0]
        parsed = ip_address(address)
        return (parsed.version, int(parsed))

    def _getSupportedNodeTypes(self) -> List[str]:
        if self._only_hosts:
            return ['hnode']
        else:
            return ['hnode', 'snode', 'rnode', 'rs']

    def render(self, emulator: Emulator):
        hosts_file_content = []
        nodes = []
        reg = emulator.getRegistry()
        for ((scope, type, name), node) in reg.getAll().items():
            if type in self._getSupportedNodeTypes():
                addresses = self.__getAllIpAddress(node)
                for address in addresses:
                    hosts_file_content.append(f"{address} {' '.join(node.getHostNames())}")
                nodes.append(node)

        sorted_hosts_file_content = sorted(hosts_file_content, key=self.__addressSortKey)

        for node in nodes:
            node.setFile("/tmp/etc-hosts", '\n'.join(sorted_hosts_file_content))
            node.insertStartCommand(0, "cat /tmp/etc-hosts >> /etc/hosts")
