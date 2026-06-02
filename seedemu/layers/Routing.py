from seedemu.core import (ScopedRegistry, Node, Interface, Network, Emulator,
                          Layer, Router, BaseSystem, DEFAULT_IPV6_INFRA_PREFIX,
                          promote_to_real_world_router)
from seedemu.core.enums import NetworkType
from typing import Dict, List, Set, Tuple
from ipaddress import IPv4Network, IPv6Network, ip_network

from ._bgp_metadata import get_bgp_backend, get_bgp_sessions, get_ospf_interface_intents, has_bgp_connected_export, ensure_bird_bgp_base, render_bird_protocol_body

RoutingFileTemplates: Dict[str, str] = {}

RoutingFileTemplates["rs_bird"] = """\
router id {routerId};
ipv4 table t_direct;
{ipv6DirectTable}
protocol device {{
}}
{kernel6}
"""

RoutingFileTemplates["rnode_bird_direct_interface"] = """
    interface "{interfaceName}";
"""

RoutingFileTemplates["rnode_bird"] = """\
router id {routerId};
ipv4 table t_direct;
{ipv6DirectTable}
protocol device {{
}}
protocol kernel {{
    ipv4 {{
        import all;
        export all;
    }};
    learn;
}}
{kernel6}
"""

RoutingFileTemplates['rnode_bird_direct'] = """
    ipv4 {{
        table t_direct;
        import all;
    }};
{interfaces}
"""

RoutingFileTemplates['rnode_bird_direct6'] = """
    ipv6 {{
        table t_direct6;
        import all;
    }};
{interfaces}
"""

RoutingFileTemplates['bird_ospf_body'] = """
    ipv4 {{
        table t_ospf;
        import all;
        export all;
    }};
    area 0 {{
{interfaces}
    }};
"""

RoutingFileTemplates['bird_ospf6_body'] = """
    ipv6 {{
        table t_ospf6;
        import all;
        export all;
    }};
    area 0 {{
{interfaces}
    }};
"""

RoutingFileTemplates['bird_ospf_interface'] = """\
        interface "{interfaceName}" {{ hello 1; dead count 2; }};
"""

RoutingFileTemplates['bird_ospf_stub_interface'] = """\
        interface "{interfaceName}" {{ stub; }};
"""

FrrFileTemplates: Dict[str, str] = {}

FrrFileTemplates["managed_block"] = """\
! ===== seedemu-routing-frr begin =====
frr defaults traditional
service integrated-vtysh-config
hostname {hostname}
!
{body}
! ===== seedemu-routing-frr end =====
"""

FrrFileTemplates["start_script"] = """\
#!/bin/bash
set -e
sed -i 's/bgpd=no/bgpd=yes/' /etc/frr/daemons
sed -i 's/zebra=no/zebra=yes/' /etc/frr/daemons
sed -i 's/staticd=no/staticd=yes/' /etc/frr/daemons
sed -i 's/ospfd=no/ospfd=yes/' /etc/frr/daemons
{enableOspf6d}
service frr start
"""

FrrFileTemplates["enable_ospf6d"] = """\
sed -i 's/ospf6d=no/ospf6d=yes/' /etc/frr/daemons
"""

FrrFileTemplates["connected_prefix_list4"] = """\
ip prefix-list PL_CONNECTED4_TO_BGP seq {seq} permit {prefix}
"""

FrrFileTemplates["connected_prefix_list6"] = """\
ipv6 prefix-list PL_CONNECTED6_TO_BGP seq {seq} permit {prefix}
"""

FrrFileTemplates["route_map_connected4"] = """\
route-map RM_CONNECTED4_TO_BGP permit 10
 match ip address prefix-list PL_CONNECTED4_TO_BGP
 set large-community {local_comm} additive
 set local-preference 40
!
"""

FrrFileTemplates["route_map_connected6"] = """\
route-map RM_CONNECTED6_TO_BGP permit 10
 match ipv6 address prefix-list PL_CONNECTED6_TO_BGP
 set large-community {local_comm} additive
 set local-preference 40
!
"""

FrrFileTemplates["community_lists"] = """\
bgp large-community-list standard LC_LOCAL permit {local_comm}
bgp large-community-list standard LC_CUSTOMER permit {customer_comm}
bgp large-community-list standard LC_LOCAL_OR_CUSTOMER permit {local_comm}
bgp large-community-list standard LC_LOCAL_OR_CUSTOMER permit {customer_comm}
!
"""

FrrFileTemplates["import_route_map"] = """\
route-map {name} permit 10
 set large-community {community} additive
 set local-preference {local_pref}
!
"""

FrrFileTemplates["export_route_map_local_customer"] = """\
route-map {name} permit 10
 match large-community LC_LOCAL_OR_CUSTOMER
!
route-map {name} deny 100
!
"""

FrrFileTemplates["export_route_map_all"] = """\
route-map {name} permit 10
!
"""

FrrFileTemplates["ospf_interface_active"] = """\
interface {interface}
 ip ospf area 0
 ip ospf hello-interval 1
 ip ospf dead-interval 2
!
"""

FrrFileTemplates["ospf_interface_passive"] = """\
interface {interface}
 ip ospf area 0
 ip ospf passive
!
"""

FrrFileTemplates["ospf_router"] = """\
router ospf
 ospf router-id {router_id}
!
"""

FrrFileTemplates["ospf6_interface_active"] = """\
interface {interface}
 ipv6 ospf6 hello-interval 1
 ipv6 ospf6 dead-interval 2
!
"""

FrrFileTemplates["ospf6_interface_passive"] = """\
interface {interface}
 ipv6 ospf6 passive
!
"""

FrrFileTemplates["ospf6_area_interface"] = """\
 interface {interface} area 0.0.0.0
"""

FrrFileTemplates["ospf6_router"] = """\
router ospf6
 ospf6 router-id {router_id}
{interfaces}!
"""

ExaBgpRouterTemplates: Dict[str, str] = {}

ExaBgpRouterTemplates["event_sink"] = """\
#!/usr/bin/env python3
import json
import os
import sys
import time

out_path = os.environ.get("EXABGP_EVENT_LOG", "/var/log/exabgp/events.jsonl")
os.makedirs(os.path.dirname(out_path), exist_ok=True)
open(out_path, "a", encoding="utf-8").close()

for raw in sys.stdin:
    line = raw.strip()
    if not line:
        continue
    try:
        payload = json.loads(line)
    except Exception:
        payload = {"raw": line}
    payload["_ts"] = int(time.time())
    with open(out_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\\n")
"""

ExaBgpRouterTemplates["live_control"] = """\
#!/usr/bin/env python3
import json
import os
import stat
import time

fifo_path = os.environ.get("EXABGP_LIVE_FIFO", "/run/exabgp/live.in")
log_path = os.environ.get("EXABGP_LIVE_LOG", "/var/log/exabgp/live-control.log")
event_log_path = os.environ.get("EXABGP_EVENT_LOG", "/var/log/exabgp/events.jsonl")
os.makedirs(os.path.dirname(fifo_path), exist_ok=True)
os.makedirs(os.path.dirname(log_path), exist_ok=True)
os.makedirs(os.path.dirname(event_log_path), exist_ok=True)

try:
    if os.path.exists(fifo_path) and not stat.S_ISFIFO(os.stat(fifo_path).st_mode):
        os.unlink(fifo_path)
    if not os.path.exists(fifo_path):
        os.mkfifo(fifo_path, 0o666)
    os.chmod(fifo_path, 0o666)
except FileExistsError:
    pass

def log(message: str) -> None:
    ts = int(time.time())
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(f"{ts} {message}\\n")
    with open(event_log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"type": "live-control", "_ts": ts, "command": message}) + "\\n")

log(f"ready fifo={fifo_path}")

while True:
    with open(fifo_path, "r", encoding="utf-8", errors="replace") as fifo:
        for raw in fifo:
            command = raw.strip()
            if not command or command.startswith("#"):
                continue
            print(command, flush=True)
            log(command)
"""

ExaBgpRouterTemplates["dashboard"] = """\
#!/usr/bin/env python3
import json
import os
from pathlib import Path

from flask import Flask, jsonify, Response

app = Flask(__name__)
event_log = Path(os.environ.get("EXABGP_EVENT_LOG", "/var/log/exabgp/events.jsonl"))
live_log = Path(os.environ.get("EXABGP_LIVE_LOG", "/var/log/exabgp/live-control.log"))
title = os.environ.get("EXABGP_DASHBOARD_TITLE", "ExaBGP Event Viewer")

def _tail_events(limit: int = 200):
    out = []
    seen = set()
    def add_event(item):
        key = (item.get("_ts", 0), item.get("type", ""), item.get("command", ""), json.dumps(item, sort_keys=True))
        if key in seen:
            return
        seen.add(key)
        out.append(item)
    if event_log.exists():
        for line in event_log.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
            try:
                add_event(json.loads(line))
            except Exception:
                add_event({"type": "exabgp-log", "raw": line})
    if live_log.exists():
        for line in live_log.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
            if not line.strip():
                continue
            ts, _, command = line.partition(" ")
            add_event({"type": "live-control", "_ts": int(ts) if ts.isdigit() else 0, "command": command or line})
    return sorted(out, key=lambda item: item.get("_ts", 0))[-limit:]

@app.route("/")
def index():
    html = f\"\"\"<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    body {{ font-family: monospace; margin: 0; background: #0d1321; color: #eef2ff; }}
    header {{ padding: 16px 20px; background: #111827; position: sticky; top: 0; }}
    main {{ padding: 20px; display: grid; gap: 12px; }}
    .card {{ background: #172033; border: 1px solid #2b3a55; border-radius: 10px; padding: 12px; }}
    .meta {{ color: #93c5fd; }}
    .kind {{ color: #fbbf24; }}
    pre {{ white-space: pre-wrap; word-break: break-word; margin: 0; }}
  </style>
</head>
<body>
  <header>
    <h1>{title}</h1>
    <div>Live BGP event stream rendered from ExaBGP JSON output and live-control commands.</div>
  </header>
  <main id="events"></main>
  <script>
    async function refresh() {{
      const res = await fetch('/api/events');
      const payload = await res.json();
      const root = document.getElementById('events');
      root.innerHTML = '';
      for (const evt of payload.events.reverse()) {{
        const card = document.createElement('section');
        card.className = 'card';
        const meta = document.createElement('div');
        meta.className = 'meta';
        meta.textContent = new Date((evt._ts || 0) * 1000).toISOString();
        const kind = document.createElement('div');
        kind.className = 'kind';
        kind.textContent = evt.type || (evt.neighbor?.message?.update ? 'bgp-update' : 'event');
        const pre = document.createElement('pre');
        pre.textContent = JSON.stringify(evt, null, 2);
        card.appendChild(meta);
        card.appendChild(kind);
        card.appendChild(pre);
        root.appendChild(card);
      }}
    }}
    refresh();
    setInterval(refresh, 2000);
  </script>
</body>
</html>\"\"\"
    return Response(html, mimetype="text/html")

@app.route("/api/events")
def events():
    return jsonify({"events": _tail_events()})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("EXABGP_DASHBOARD_PORT", "5000")))
"""

ExaBgpRouterTemplates["config"] = """\
process exabgp_json_sink {{
  run /usr/bin/env python3 /opt/exabgp/event_sink.py;
  encoder json;
}}

process exabgp_live_control {{
  run /usr/bin/env python3 /opt/exabgp/live_control.py;
  encoder text;
  respawn false;
}}

{neighbor_blocks}
"""

ExaBgpRouterTemplates["static_block"] = """\
  static {{
{routes}
  }}
"""


def _session_route_map_name(prefix: str, session_name: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in str(session_name or "session"))
    return f"{prefix}_{safe}"[:64]


def _render_frr_session_route_maps(local_asn: int, sessions: List[Dict]) -> Tuple[str, Dict[str, Dict[str, str]]]:
    body: List[str] = []
    map_names: Dict[str, Dict[str, str]] = {}
    community_map = {
        "LOCAL_COMM": f"{local_asn}:0:0",
        "CUSTOMER_COMM": f"{local_asn}:1:0",
        "PEER_COMM": f"{local_asn}:2:0",
        "PROVIDER_COMM": f"{local_asn}:3:0",
    }

    for session in sessions:
        name = str(session.get("name") or "session")
        import_name = ""
        import_community = str(session.get("import_community") or "").strip()
        local_pref = session.get("local_pref")
        export_policy = str(session.get("export_policy") or "all").strip()

        if import_community and local_pref is not None:
            import_name = _session_route_map_name("RM_IMPORT", name)
            body.append(
                FrrFileTemplates["import_route_map"].format(
                    name=import_name,
                    community=community_map.get(import_community, import_community),
                    local_pref=int(local_pref),
                )
            )

        export_name = _session_route_map_name("RM_EXPORT", name)
        if export_policy == "local_and_customer":
            body.append(FrrFileTemplates["export_route_map_local_customer"].format(name=export_name))
        else:
            body.append(FrrFileTemplates["export_route_map_all"].format(name=export_name))

        map_names[name] = {"import": import_name, "export": export_name}

    return "".join(body), map_names


def _render_frr_connected_export(local_asn: int, router: Router) -> Tuple[str, bool, bool]:
    prefixes4: List[str] = []
    prefixes6: List[str] = []
    seen4: Set[str] = set()
    seen6: Set[str] = set()

    for iface in router.getInterfaces():
        net = iface.getNet()
        if net.getType() == NetworkType.Bridge:
            continue

        prefix4 = str(net.getPrefix())
        if iface.getAddress() is not None and prefix4 not in seen4:
            seen4.add(prefix4)
            prefixes4.append(prefix4)

        if iface.hasIpv6Address() and net.hasIpv6Prefix():
            prefix6 = str(net.getIpv6Prefix())
            if prefix6 not in seen6:
                seen6.add(prefix6)
                prefixes6.append(prefix6)

    body: List[str] = []
    for index, prefix in enumerate(prefixes4, start=1):
        body.append(FrrFileTemplates["connected_prefix_list4"].format(seq=index * 10, prefix=prefix))
    if prefixes4:
        body.append(FrrFileTemplates["route_map_connected4"].format(local_comm=f"{local_asn}:0:0"))

    for index, prefix in enumerate(prefixes6, start=1):
        body.append(FrrFileTemplates["connected_prefix_list6"].format(seq=index * 10, prefix=prefix))
    if prefixes6:
        body.append(FrrFileTemplates["route_map_connected6"].format(local_comm=f"{local_asn}:0:0"))

    return "".join(body), bool(prefixes4), bool(prefixes6)


class Routing(Layer):
    """!
    @brief The Routing layer.

    This layer provides routing support for routers and hosts. i.e., (1) install
    BIRD on router nodes and allow BGP/OSPF to work, (2) setup kernel and device
    protocols, and (3) setup default routes for host nodes.

    When this layer is rendered, two new methods will be added to the router
    node and can be used by other layers: (1) addProtocol: add new protocol
    block to BIRD, and (2) addTable: add new routing table to BIRD.

    This layer also assign loopback address for iBGP/LDP, etc., for other
    protocols to use later and as router id.
    """

    _loopback_assigner: IPv4Network
    _loopback_ipv6_assigner: IPv6Network
    _loopback_pos: int
    _loopback_ipv6_pos: int

    def __init__(self, loopback_range: str = '10.0.0.0/16', loopback_ipv6_range: str = DEFAULT_IPV6_INFRA_PREFIX):
        """!
        @brief Routing layer constructor.

        @param loopback_range (optional) network range for assigning loopback
        IP addresses.
        """
        super().__init__()
        self._loopback_assigner = IPv4Network(loopback_range)
        self._loopback_ipv6_assigner = IPv6Network(loopback_ipv6_range)
        self._loopback_pos = 1
        self._loopback_ipv6_pos = 1
        self.addDependency('Base', False, False)
        self.addDependency('Ospf', True, True)
        self.addDependency('Ibgp', True, True)
        self.addDependency('Ebgp', True, True)

    def getName(self) -> str:
        return "Routing"

    def _installBird(self, node: Node):
        """!
        @brief Install bird on node, and handle the bug.
        """
        # addBuildCommand and addSoftware lines are needed when user wants to use custom image.
        node.addBuildCommand('mkdir -p /usr/share/doc/bird2/examples/')
        node.addBuildCommand('touch /usr/share/doc/bird2/examples/bird.conf')
        node.addSoftware('bird2')

        self._ensureRouterBaseSystem(node)

    def _ensureRouterBaseSystem(self, node: Node):
        """!
        @brief Ensure the node uses the router base system even when BIRD is not installed.
        """

        base = node.getBaseSystem()
        if not BaseSystem.doesAContainB(base,BaseSystem.SEEDEMU_ROUTER) and base !=BaseSystem.SEEDEMU_ROUTER:
            node.setBaseSystem(BaseSystem.SEEDEMU_ROUTER)

    def _configure_rs(self, rs_node: Node):
        if get_bgp_backend(rs_node) != "bird":
            return
        rs_node.appendStartCommand('[ ! -d /run/bird ] && mkdir /run/bird')
        rs_node.appendStartCommand('bird -d', True)
        self._log("Bootstrapping bird.conf for RS {}...".format(rs_node.getName()))

        rs_ifaces = rs_node.getInterfaces()
        assert len(rs_ifaces) == 1, "rs node {} has != 1 interfaces".format(rs_node.getName())

        rs_iface = rs_ifaces[0]

        assert issubclass(rs_node.__class__, Router)
        rs_node.setBorderRouter(True)
        has_ipv6 = rs_iface.hasIpv6Address()
        rs_node.setFile("/etc/bird/bird.conf", RoutingFileTemplates["rs_bird"].format(
            routerId=rs_iface.getAddress(),
            ipv6DirectTable="ipv6 table t_direct6;" if has_ipv6 else "",
            kernel6=(
                "protocol kernel kernel6 {\n"
                "    ipv6 {\n"
                "        import all;\n"
                "        export all;\n"
                "    };\n"
                "    learn;\n"
                "}\n"
            ) if has_ipv6 else "",
        ))

    def _configure_bird_router(self, rnode: Router):
        ifaces = ''
        ifaces6 = ''
        has_localnet = False
        has_ipv6_localnet = False
        for iface in rnode.getInterfaces():
            net = iface.getNet()
            if net.isDirect():
                has_localnet = True
                ifaces += RoutingFileTemplates["rnode_bird_direct_interface"].format(
                    interfaceName = net.getName()
                )
                if iface.hasIpv6Address():
                    has_ipv6_localnet = True
                    ifaces6 += RoutingFileTemplates["rnode_bird_direct_interface"].format(
                        interfaceName=net.getName()
                    )
        rnode.setFile("/etc/bird/bird.conf",
            RoutingFileTemplates["rnode_bird"].format(
              routerId=rnode.getLoopbackAddress(),
              ipv6DirectTable="ipv6 table t_direct6;" if has_ipv6_localnet else "",
              kernel6=(
                  "protocol kernel kernel6 {\n"
                  "    ipv6 {\n"
                  "        import all;\n"
                  "        export all;\n"
                  "    };\n"
                  "    learn;\n"
                  "}\n"
              ) if has_ipv6_localnet else ""))
        if get_bgp_backend(rnode) == "bird":
            rnode.appendStartCommand('[ ! -d /run/bird ] && mkdir /run/bird')
            rnode.appendStartCommand('bird -d', True)
        if has_localnet:
            rnode.addProtocol('direct', 'local_nets',
                              RoutingFileTemplates['rnode_bird_direct'].format(interfaces = ifaces))
        if has_ipv6_localnet:
            rnode.addProtocol('direct', 'local_nets6',
                              RoutingFileTemplates['rnode_bird_direct6'].format(interfaces=ifaces6))

    def _render_bird_sessions(self, router: Router):
        if router.getAttribute("__routing_bird_sessions_rendered", False):
            return
        sessions = get_bgp_sessions(router)
        if not sessions:
            return
        ensure_bird_bgp_base(router)
        for session in sessions:
            router.addProtocol("bgp", session["name"], render_bird_protocol_body(session))
        router.setAttribute("__routing_bird_sessions_rendered", True)

    def _render_bird_ospf(self, router: Router):
        if router.getAttribute("__routing_bird_ospf_rendered", False):
            return
        intents = get_ospf_interface_intents(router)
        active = list(intents.get("active", []) or [])
        passive = list(intents.get("passive", []) or [])
        families = list(intents.get("families", ["ipv4"]) or ["ipv4"])
        if not active and not passive:
            return
        ospf_interfaces = ""
        ospf6_interfaces = ""
        ipv6_ifaces = {"dummy0"} if router.getLoopbackIpv6Address() else set()
        for iface in router.getInterfaces():
            if iface.hasIpv6Address():
                ipv6_ifaces.add(str(iface.getNet().getName()))
        for iface_name in passive:
            ospf_interfaces += RoutingFileTemplates['bird_ospf_stub_interface'].format(interfaceName=iface_name)
            if iface_name in ipv6_ifaces:
                ospf6_interfaces += RoutingFileTemplates['bird_ospf_stub_interface'].format(interfaceName=iface_name)
        for iface_name in active:
            ospf_interfaces += RoutingFileTemplates['bird_ospf_interface'].format(interfaceName=iface_name)
            if iface_name in ipv6_ifaces:
                ospf6_interfaces += RoutingFileTemplates['bird_ospf_interface'].format(interfaceName=iface_name)
        if "ipv4" in families:
            router.addTable('t_ospf')
            router.addProtocol('ospf', 'ospf1', RoutingFileTemplates['bird_ospf_body'].format(interfaces=ospf_interfaces))
            router.addTablePipe('t_ospf')
        if "ipv6" in families and ospf6_interfaces:
            router.addTable('t_ospf6', family="ipv6")
            router.addProtocol('ospf v3', 'ospf6', RoutingFileTemplates['bird_ospf6_body'].format(interfaces=ospf6_interfaces))
            router.addTablePipe('t_ospf6', 'master6')
        router.setAttribute("__routing_bird_ospf_rendered", True)

    def _render_frr_ospf_block(self, router: Router) -> str:
        body: List[str] = []
        intents = get_ospf_interface_intents(router)
        active_ifaces: List[str] = list(intents.get("active", []) or [])
        passive_ifaces: List[str] = list(intents.get("passive", []) or ["dummy0"])
        families: List[str] = list(intents.get("families", ["ipv4"]) or ["ipv4"])
        if not active_ifaces and not passive_ifaces:
            for iface in router.getInterfaces():
                net = iface.getNet()
                name = str(net.getName())
                if net.getType() == NetworkType.Local:
                    active_ifaces.append(name)
                else:
                    passive_ifaces.append(name)

        if "ipv4" in families:
            seen: Set[str] = set()
            for name in active_ifaces:
                if name in seen:
                    continue
                seen.add(name)
                body.append(FrrFileTemplates["ospf_interface_active"].format(interface=name))
            for name in passive_ifaces:
                if name in seen:
                    continue
                seen.add(name)
                body.append(FrrFileTemplates["ospf_interface_passive"].format(interface=name))
            body.append(FrrFileTemplates["ospf_router"].format(router_id=str(router.getLoopbackAddress() or "")))

        if "ipv6" in families:
            ipv6_ifaces = {"dummy0"} if router.getLoopbackIpv6Address() else set()
            for iface in router.getInterfaces():
                if iface.hasIpv6Address():
                    ipv6_ifaces.add(str(iface.getNet().getName()))
            seen6: Set[str] = set()
            area_interfaces = ""
            for name in active_ifaces:
                if name in seen6 or name not in ipv6_ifaces:
                    continue
                seen6.add(name)
                body.append(FrrFileTemplates["ospf6_interface_active"].format(interface=name))
                area_interfaces += FrrFileTemplates["ospf6_area_interface"].format(interface=name)
            for name in passive_ifaces:
                if name in seen6 or name not in ipv6_ifaces:
                    continue
                seen6.add(name)
                body.append(FrrFileTemplates["ospf6_interface_passive"].format(interface=name))
                area_interfaces += FrrFileTemplates["ospf6_area_interface"].format(interface=name)
            if seen6:
                body.append(FrrFileTemplates["ospf6_router"].format(
                    router_id=str(router.getLoopbackAddress() or ""),
                    interfaces=area_interfaces,
                ))
        return "".join(body)

    def _render_frr_bgp_block(self, router: Router, sessions: List[Dict]) -> str:
        local_asn = int(router.getAsn())
        loopback = str(router.getLoopbackAddress() or "")
        route_maps, map_names = _render_frr_session_route_maps(local_asn, sessions)
        connected_policy, export_connected4, export_connected6 = ("", False, False)
        if has_bgp_connected_export(router):
            connected_policy, export_connected4, export_connected6 = _render_frr_connected_export(local_asn, router)
        ipv4_sessions = [s for s in sessions if "ipv4" in list(s.get("families", ["ipv4"]))]
        ipv6_sessions = [s for s in sessions if "ipv6" in list(s.get("families", []))]
        body: List[str] = [
            FrrFileTemplates["community_lists"].format(
                local_comm=f"{local_asn}:0:0",
                customer_comm=f"{local_asn}:1:0",
            ),
            connected_policy,
            route_maps,
            f"router bgp {local_asn}\n",
            f" bgp router-id {loopback}\n",
            " no bgp default ipv4-unicast\n",
            " no bgp ebgp-requires-policy\n",
        ]

        seen_neighbors: Set[str] = set()
        for session in sessions:
            family = list(session.get("families", ["ipv4"]) or ["ipv4"])[0]
            peer_address = str((session.get("peer_ipv6_address") if family == "ipv6" else session.get("peer_address")) or "").strip()
            peer_asn = int(session.get("peer_asn") or 0)
            if not peer_address or peer_asn <= 0 or peer_address in seen_neighbors:
                continue
            seen_neighbors.add(peer_address)
            session_name = str(session.get("name") or f"peer_{peer_asn}")
            body.append(f" neighbor {peer_address} remote-as {peer_asn}\n")
            body.append(f" neighbor {peer_address} description {session_name}\n")

        body.append(" !\n")

        body.append(" address-family ipv4 unicast\n")
        if export_connected4:
            body.append("  redistribute connected route-map RM_CONNECTED4_TO_BGP\n")
        for session in ipv4_sessions:
            peer_address = str(session.get("peer_address") or "").strip()
            if not peer_address:
                continue
            session_name = str(session.get("name") or "")
            names = map_names.get(session_name, {})
            body.append(f"  neighbor {peer_address} activate\n")
            if bool(session.get("next_hop_self")):
                body.append(f"  neighbor {peer_address} next-hop-self\n")
            import_name = str(names.get("import") or "")
            export_name = str(names.get("export") or "")
            if import_name:
                body.append(f"  neighbor {peer_address} route-map {import_name} in\n")
            if export_name:
                body.append(f"  neighbor {peer_address} route-map {export_name} out\n")
        body.append(" exit-address-family\n!\n")
        if ipv6_sessions:
            body.append(" address-family ipv6 unicast\n")
            if export_connected6:
                body.append("  redistribute connected route-map RM_CONNECTED6_TO_BGP\n")
            for session in ipv6_sessions:
                peer_address = str(session.get("peer_ipv6_address") or "").strip()
                if not peer_address:
                    continue
                session_name = str(session.get("name") or "")
                names = map_names.get(session_name, {})
                body.append(f"  neighbor {peer_address} activate\n")
                if bool(session.get("next_hop_self")):
                    body.append(f"  neighbor {peer_address} next-hop-self\n")
                import_name = str(names.get("import") or "")
                export_name = str(names.get("export") or "")
                if import_name:
                    body.append(f"  neighbor {peer_address} route-map {import_name} in\n")
                if export_name:
                    body.append(f"  neighbor {peer_address} route-map {export_name} out\n")
            body.append(" exit-address-family\n!\n")
        return "".join(body)

    def _configure_frr_router(self, router: Router):
        ospf_intents = get_ospf_interface_intents(router)
        wants_ospf6 = "ipv6" in list(ospf_intents.get("families", []) or [])
        router.addSoftware("frr")
        router.setFile(
            "/etc/frr/frr.conf",
            FrrFileTemplates["managed_block"].format(
                hostname=f"as{router.getAsn()}-{router.getName()}",
                body=self._render_frr_ospf_block(router) + self._render_frr_bgp_block(router, get_bgp_sessions(router)),
            ),
        )
        router.setFile(
            "/frr_start",
            FrrFileTemplates["start_script"].format(
                enableOspf6d=FrrFileTemplates["enable_ospf6d"] if wants_ospf6 else ""
            ),
        )
        router.appendStartCommand("chmod +x /frr_start")
        router.appendStartCommand("/frr_start")

    def _configure_exabgp_router(self, router: Router):
        sessions = get_bgp_sessions(router)
        for session in sessions:
            assert session.get("kind") == "ebgp", (
                "ExaBGP control-plane speaker currently supports eBGP sessions only; "
                f"as{router.getAsn()}/{router.getName()} has {session.get('kind')}"
            )
            assert not session.get("route_server_client"), (
                "ExaBGP control-plane speaker cannot act as an IX route server client endpoint yet; "
                f"as{router.getAsn()}/{router.getName()} session {session.get('name')}"
            )
        assert not get_ospf_interface_intents(router).get("active"), (
            "ExaBGP control-plane speaker currently does not support OSPF transit; "
            f"mask OSPF or use bird/frr for as{router.getAsn()}/{router.getName()}"
        )

        router.addBuildCommand(
            "apt-get update && "
            "apt-get install -y --no-install-recommends "
            "-o Dpkg::Options::=--force-unsafe-io "
            "exabgp python3-flask && "
            "rm -rf /var/lib/apt/lists/*"
        )
        router.setFile("/opt/exabgp/event_sink.py", ExaBgpRouterTemplates["event_sink"])
        router.setFile("/opt/exabgp/live_control.py", ExaBgpRouterTemplates["live_control"])
        router.setFile("/opt/exabgp/dashboard.py", ExaBgpRouterTemplates["dashboard"])

        routes_by_family = {"ipv4": [], "ipv6": []}
        for prefix in router.getBgpAnnouncements():
            family = "ipv6" if ip_network(prefix, strict=False).version == 6 else "ipv4"
            routes_by_family[family].append(f"    route {prefix} next-hop self;")
        neighbor_blocks: List[str] = []
        for session in sessions:
            family = list(session.get("families", ["ipv4"]) or ["ipv4"])[0]
            local_address = str(session.get("local_ipv6_address") if family == "ipv6" else session.get("local_address"))
            peer_address = str(session.get("peer_ipv6_address") if family == "ipv6" else session.get("peer_address"))
            routes = "\n".join(routes_by_family[family])
            static_block = ExaBgpRouterTemplates["static_block"].format(routes=routes) if routes else ""
            neighbor_blocks.append(
                (
                    "neighbor {peer_address} {{\n"
                    "  router-id {router_id};\n"
                    "  local-address {local_address};\n"
                    "  local-as {local_asn};\n"
                    "  peer-as {peer_asn};\n"
                    "  family {{\n"
                    "    {family} unicast;\n"
                    "  }}\n"
                    "  api {{\n"
                    "    processes [ exabgp_json_sink exabgp_live_control ];\n"
                    "  }}\n"
                    "{static_block}"
                    "}}\n"
                ).format(
                    peer_address=peer_address,
                    router_id=str(session.get("local_address") or router.getLoopbackAddress() or "0.0.0.0"),
                    local_address=local_address,
                    local_asn=session["local_asn"],
                    peer_asn=session["peer_asn"],
                    family=family,
                    static_block=static_block,
                )
            )
        router.setFile(
            "/etc/exabgp/exabgp.conf",
            ExaBgpRouterTemplates["config"].format(neighbor_blocks="\n".join(neighbor_blocks)),
        )
        router.appendStartCommand(
            "mkdir -p /var/log/exabgp /opt/exabgp && "
            "touch /var/log/exabgp/events.jsonl /var/log/exabgp/exabgp.log "
            "/var/log/exabgp/live-control.log && "
            "chmod 755 /var/log/exabgp && "
            "chmod 666 /var/log/exabgp/events.jsonl /var/log/exabgp/exabgp.log "
            "/var/log/exabgp/live-control.log"
        )
        router.appendStartCommand(
            "mkdir -p /run/exabgp /var/run/exabgp && "
            "rm -f /run/exabgp/live.in /run/exabgp.in /run/exabgp.out "
            "/var/run/exabgp.in /var/run/exabgp.out && "
            "mkfifo /run/exabgp.in /run/exabgp.out && "
            "touch /var/log/exabgp/events.jsonl /var/log/exabgp/live-control.log && "
            "chmod 666 /run/exabgp.in /run/exabgp.out && "
            "chmod 777 /run/exabgp /var/run/exabgp"
        )
        router.appendStartCommand("chmod +x /opt/exabgp/event_sink.py /opt/exabgp/live_control.py /opt/exabgp/dashboard.py")
        router.appendStartCommand(
            f"EXABGP_EVENT_LOG=/var/log/exabgp/events.jsonl EXABGP_DASHBOARD_PORT={int(router.getAttribute('__exabgp_dashboard_port', 5000))} "
            f"EXABGP_DASHBOARD_TITLE=\"ExaBGP Event Viewer as{router.getAsn()}/{router.getName()}\" "
            "python3 /opt/exabgp/dashboard.py",
            True,
        )
        router.appendStartCommand(
            "EXABGP_EVENT_LOG=/var/log/exabgp/events.jsonl "
            "env exabgp.api.cli=true exabgp.api.pipename=exabgp "
            "exabgp.daemon.drop=false exabgp.daemon.user=root "
            "exabgp /etc/exabgp/exabgp.conf >/var/log/exabgp/exabgp.log 2>&1",
            True,
        )

    def configure(self, emulator: Emulator):
        super().configure(emulator)
        reg = emulator.getRegistry()
        for ((scope, type, name), obj) in reg.getAll().items():
            if type == 'rs':
                rs_node: Node = obj
                self._ensureRouterBaseSystem(rs_node)
                if get_bgp_backend(rs_node) == "bird":
                    self._installBird(rs_node)
                self._configure_rs(rs_node)
            if type == 'rnode':
                rnode: Router = obj
                assert issubclass(rnode.__class__, Router)

                self._log("Setting up loopback interface for AS{} Router {}...".format(scope, name))

                if rnode.getLoopbackAddress() == None:
                    lbaddr = self._loopback_assigner[self._loopback_pos]
                    self._loopback_pos += 1
                else:
                    lbaddr = rnode.getLoopbackAddress()
                has_ipv6 = any(iface.hasIpv6Address() for iface in rnode.getInterfaces())
                lbaddr6 = None
                if has_ipv6:
                    if rnode.getLoopbackIpv6Address() == None:
                        lbaddr6 = self._loopback_ipv6_assigner[self._loopback_ipv6_pos]
                        self._loopback_ipv6_pos += 1
                    else:
                        lbaddr6 = rnode.getLoopbackIpv6Address()

                rnode.appendStartCommand('ip li add dummy0 type dummy')
                rnode.appendStartCommand('ip li set dummy0 up')
                rnode.appendStartCommand('ip addr add {}/32 dev dummy0'.format(lbaddr))
                if lbaddr6 is not None:
                    rnode.appendStartCommand('ip -6 addr add {}/128 dev dummy0'.format(lbaddr6))
                    rnode.setLabel('loopback_ipv6_addr', lbaddr6)
                    rnode.setLoopbackIpv6Address(str(lbaddr6))
                rnode.setLabel('loopback_addr', lbaddr)
                rnode.setLoopbackAddress(lbaddr)

                self._log("Preparing routing backend for AS{} Router {}...".format(scope, name))

                r_ifaces = rnode.getInterfaces()
                assert len(r_ifaces) > 0, "router node {}/{} has no interfaces".format(rnode.getAsn(), rnode.getName())

                self._ensureRouterBaseSystem(rnode)
                if get_bgp_backend(rnode) == "bird":
                    self._installBird(rnode)
                    self._configure_bird_router(rnode)
                else:
                    self._log("Deferring routing daemon setup for AS{} Router {} (backend={})...".format(
                        scope, name, get_bgp_backend(rnode)
                    ))

    def render(self, emulator: Emulator):
        reg = emulator.getRegistry()

        gateway_constraints = {}
        hit: bool = False
        for ((scope, type, name), obj) in reg.getAll().items():
            # make sure that on each externaly connected net (those with at least one host who requested it)
            #  (I):  there is at least one RealWorldRouter
            #  (II): the RWR is the default gateway of the requesters on this net
            if type == 'net' and obj.getType() == NetworkType.Local:
                if (p := obj.getExternalConnectivityProvider() ):
                   hit |= True
                   rwr_candidates, new_gateway_constraints = p.resolveRWA( emulator, obj)
                   for r in rwr_candidates:
                       r = promote_to_real_world_router(r, False)
                       route = obj.getPrefix()
                       # only for hosts on THIS network ('route') the RWA is provided
                       r.addRealWorldRoute('0.0.0.0/1', str(route))
                       r.addRealWorldRoute('128.0.0.0/1', str(route))
                   for h, gw in new_gateway_constraints.items():
                       assert h not in gateway_constraints, 'multihomed host ?!'
                       gateway_constraints[h] = gw
                   pass
        # don't create it unnecessary
        svc_net = emulator.getServiceNetwork() if hit or (reg.has('seedemu', 'net', '000_svc')) else None

        for ((scope, type, name), obj) in reg.getAll().items():
            if type == 'rs' or type == 'rnode':
                assert issubclass(obj.__class__, Router), 'routing: render: adding new RS/Router after routing layer configured is not currently supported.'

            if type == 'rnode':
                rnode: Router = obj
                if rnode.hasExtension('RealWorldRouter'): # could also be ScionRouter which needs RealWorldAccess

                    # this is an exception - Only for service net (not part of simulation)
                    rnode._Node__joinNetwork(svc_net)
                    [l, b, d] = svc_net.getDefaultLinkProperties()
                    svc_iface = None
                    for iface in rnode.getInterfaces():
                        if iface.getNet() == svc_net:
                            svc_iface = iface
                            break
                    if svc_iface is not None and svc_iface.getAddress() is not None:
                        rnode.appendFile('/ifinfo.txt',
                                         '{}|{}/{}|{}|{}|{}\n'.format(svc_net.getName(), svc_iface.getAddress(), svc_net.getPrefix().prefixlen, l, b, d))
                    rnode.appendFile('/ifinfo.txt',
                                     '{}|{}|{}|{}|{}\n'.format(svc_net.getName(), svc_net.getPrefix(), l, b, d))
                    if svc_iface is not None and svc_iface.hasIpv6Address():
                        rnode.appendFile('/ifinfo.txt',
                                         '{}|{}/{}|{}|{}|{}\n'.format(svc_net.getName(), svc_iface.getIpv6Address(), svc_net.getIpv6Prefix().prefixlen, l, b, d))

                    self._log("Sealing real-world router as{}/{}...".format(rnode.getAsn(), rnode.getName()))
                    rnode.seal(svc_net)

                backend = get_bgp_backend(rnode)
                if backend == "bird":
                    self._render_bird_ospf(rnode)
                    self._render_bird_sessions(rnode)
                if backend == "frr" and not rnode.getAttribute("__routing_backend_rendered", False):
                    self._log("Rendering FRR backend for AS{} Router {}...".format(scope, name))
                    self._configure_frr_router(rnode)
                    rnode.setAttribute("__routing_backend_rendered", True)
                if backend == "exabgp" and not rnode.getAttribute("__routing_backend_rendered", False):
                    self._log("Rendering transitional ExaBGP speaker for AS{} Node {}...".format(scope, name))
                    self._configure_exabgp_router(rnode)
                    rnode.setAttribute("__routing_backend_rendered", True)

            if type in ['hnode', 'csnode']:
                hnode: Node = obj
                hifaces: List[Interface] = hnode.getInterfaces()
                assert len(hifaces) == 1, 'Host {} in as{} has != 1 interfaces'.format(name, scope)
                hif = hifaces[0]
                hnet: Network = hif.getNet()
                rif: Interface = None
                candidates = []
                if hnode in gateway_constraints:
                    candidates.append(gateway_constraints[hnode])
                else:
                    cur_scope = ScopedRegistry(scope, reg)
                    candidates = cur_scope.getByType('rnode')


                for router in candidates:
                    if rif != None: break
                    for riface in router.getInterfaces():
                        if riface.getNet() == hnet:
                            rif = riface
                            break

                if rif == None and hnet.getType() == NetworkType.InternetExchange:
                    self._log(
                        "Host {} in as{} is directly attached to IX {}; skipping default route.".format(
                            name, scope, hnet.getName()
                        )
                    )
                    continue
                assert rif != None, 'Host {} in as{} in network {}: no router'.format(name, scope, hnet.getName())
                self._log("Setting default route for host {} ({}) to router {}".format(name, hif.getAddress(), rif.getAddress()))
                hnode.appendStartCommand('ip rou del default 2> /dev/null')
                hnode.appendStartCommand('ip route add default via {} dev {}'.format(rif.getAddress(), rif.getNet().getName()))
                if hif.hasIpv6Address() and rif.hasIpv6Address():
                    hnode.appendStartCommand('ip -6 route del default 2> /dev/null')
                    hnode.appendStartCommand('ip -6 route add default via {} dev {}'.format(rif.getIpv6Address(), rif.getNet().getName()))

    def print(self, indent: int) -> str:
        out = ' ' * indent
        out += 'RoutingLayer: BIRD 2.0.x\n'

        return out
