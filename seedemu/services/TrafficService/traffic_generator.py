from __future__ import annotations
from seedemu.core import AddressFamily, Node, Server, getNodeAddress, normalizeAddressFamily
from typing import TYPE_CHECKING, List, Tuple, Union

if TYPE_CHECKING:
    from seedemu.core import Emulator


class TrafficGenerator(Server):
    startup_script = """
echo "Check if targets are reachable";
ping_target () {{
    target="$1"
    case "$target" in
    *:*)
        ping -6 -c1 "$target" > /dev/null
        ;;
    *)
        ping -c1 "$target" > /dev/null
        ;;
    esac
}}
while read client; do
    while true; do ping_target "$client" && break; done;
done < /root/traffic-targets
echo "Starting traffic generator"
while read client; do
    {cmdline} &
done < /root/traffic-targets
"""

    def __init__(
        self,
        name: str = None,
        log_file: str = "/root/traffic_generator.log",
        duration: int = 300,
        rate: int = 5000,
        protocol: str = "TCP",
        auto_start: bool = True,
        extra_options: str = ""
    ):
        """!
        @brief TrafficGenerator constructor.
        @param name name of the generator.
        @param log_file log file.
        @param duration duration of traffic generation process.
        @param rate rate in bits/sec (0 for unlimited).
        @param protocol protocol.
        @param auto_start start the traffic generator script automatically.
        @param extra_options extra options.
        """
        super().__init__()
        self.name = name or self.__class__.__name__
        self.log_file = log_file
        self.duration = duration
        self.rate = rate
        self.protocol = protocol
        self.extra_options = extra_options
        self.auto_start = auto_start
        self.receiver_hosts = []
        self.receiver_vnodes: List[Tuple[str, AddressFamily, bool]] = []
        self.start_scripts = []
        self.traffic_generators = []

    def addReceivers(self, hosts: List[str] = []):
        """!
        @brief Add traffic receiver hosts.
        @param hosts list of receiver hosts.
        """
        self.receiver_hosts.extend(hosts)

    def addReceiverVnodes(
        self,
        vnodes: List[str] = None,
        family: Union[AddressFamily, str, int] = AddressFamily.IPv4,
        preferLocal: bool = True,
    ) -> TrafficGenerator:
        """!
        @brief Add receiver virtual nodes and resolve them by address family during render.
        @param vnodes list of receiver virtual node names.
        @param family address family to use for receiver targets.
        @param preferLocal prefer local-network addresses before service-network fallback.
        """
        selected = normalizeAddressFamily(family)
        for vnode in vnodes or []:
            self.receiver_vnodes.append((vnode, selected, preferLocal))
        return self

    def resolveReceiverVnodes(self, emulator: "Emulator"):
        """!
        @brief Resolve receiver virtual node targets into concrete addresses.
        """
        for vnode, family, preferLocal in self.receiver_vnodes:
            receiver = emulator.getBindingFor(vnode)
            address = getNodeAddress(receiver, family, preferLocal=preferLocal)
            assert address is not None, "Traffic receiver vnode {} has no {} address.".format(
                vnode,
                family.value,
            )
            self.receiver_hosts.append(str(address))
        self.receiver_vnodes = []

    def install_softwares(self, node: Node):
        """!
        @brief Install necessary softwares.
        """
        raise NotImplementedError

    def install(self, node: Node):
        """!
        @brief Install the service.
        """
        node.addHostName(self.name)
        node.appendClassName("TrafficGenerator")
        node.setFile("/root/traffic-targets", "\n".join(list(set(self.receiver_hosts))))
        
        for server in self.traffic_generators:
            server.install_softwares(node)

        if self.auto_start:
            self.start(node)

    def start(self, node: Node):
        """!
        @brief Start the scripts automatically on boot up.
        """
        for server in self.traffic_generators:
            for script in server.start_scripts:
                node.appendStartCommand(script)

    def print(self, indent: int) -> str:
        out = " " * indent
        out += "TrafficGenerator object.\n"

        return out

    def extend(self, server: TrafficGenerator):
        """!
        @brief Extend the traffic generator.
        """
        self.traffic_generators.append(server)
        return self
