from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from seedemu.core import AddressFamily, Router, normalizeAddressFamily, normalizeAddressList
from seedemu.core.enums import NetworkType


BGP_BACKEND_ATTR = "__bgp_backend"
BGP_SESSION_INTENTS_ATTR = "__bgp_session_intents"
BGP_CONNECTED_EXPORT_ATTR = "__bgp_connected_export"
BGP_CONNECTED_EXPORT_RENDERED_ATTR = "__bgp_connected_export_rendered"
BGP_BOOTSTRAPPED_ATTR = "__bgp_bootstrapped"
OSPF_INTERFACE_INTENTS_ATTR = "__ospf_interface_intents"

BGP_BACKEND_BIRD = "bird"
BGP_BACKEND_FRR = "frr"
BGP_BACKEND_EXABGP = "exabgp"
BGP_BACKEND_EXTERNAL = BGP_BACKEND_EXABGP
BGP_BACKEND_LABEL = "seedemu_bgp_backend"

BGP_KIND_EBGP = "ebgp"
BGP_KIND_IBGP = "ibgp"
BGP_EXPORT_ALL = "all"
BGP_EXPORT_LOCAL_AND_CUSTOMER = "local_and_customer"
BGP_FAMILY_IPV4 = "ipv4"
BGP_FAMILY_IPV6 = "ipv6"

COMMUNITY_ALIAS_BY_NAME = {
    "LOCAL_COMM": lambda asn: f"{asn}:0:0",
    "CUSTOMER_COMM": lambda asn: f"{asn}:1:0",
    "PEER_COMM": lambda asn: f"{asn}:2:0",
    "PROVIDER_COMM": lambda asn: f"{asn}:3:0",
}

BIRD_BGP_COMMONS_TEMPLATE = """\
define LOCAL_COMM = ({localAsn}, 0, 0);
define CUSTOMER_COMM = ({localAsn}, 1, 0);
define PEER_COMM = ({localAsn}, 2, 0);
define PROVIDER_COMM = ({localAsn}, 3, 0);
"""

BIRD_RS_PEER_TEMPLATE = """\
{familyBlocks}
    rs client;
    local {localAddress} as {localAsn};
    neighbor {peerAddress} as {peerAsn};
"""

BIRD_ROUTER_PEER_TEMPLATE = """\
{familyBlocks}
    local {localAddress} as {localAsn};
    neighbor {peerAddress} as {peerAsn};
"""

BIRD_IBGP_PEER_TEMPLATE = """\
{familyBlocks}
    local {localAddress} as {localAsn};
    neighbor {peerAddress} as {peerAsn};
"""

CONNECTED_EXPORT_FILTER = "filter { bgp_large_community.add(LOCAL_COMM); bgp_local_pref = 40; accept; }"
CONNECTED_EXPORT_FILTER_V6 = "filter { bgp_large_community.add(LOCAL_COMM); bgp_local_pref = 40; accept; }"


def get_bgp_backend(node: Router) -> str:
    backend = None
    try:
        backend = node.getRoutingBackend()
    except AttributeError:
        try:
            backend = node.getAttribute(BGP_BACKEND_ATTR)
        except AttributeError:
            backend = None
    if backend in {None, ""}:
        backend = node.getLabel().get(BGP_BACKEND_LABEL, BGP_BACKEND_BIRD)
    backend = str(backend or BGP_BACKEND_BIRD).strip().lower()
    if backend == "external":
        backend = BGP_BACKEND_EXABGP
    return backend if backend in {BGP_BACKEND_BIRD, BGP_BACKEND_FRR, BGP_BACKEND_EXABGP} else BGP_BACKEND_BIRD


def set_bgp_backend(node: Router, backend: str) -> None:
    value = str(backend or BGP_BACKEND_BIRD).strip().lower() or BGP_BACKEND_BIRD
    if value == "external":
        value = BGP_BACKEND_EXABGP
    if value not in {BGP_BACKEND_BIRD, BGP_BACKEND_FRR, BGP_BACKEND_EXABGP}:
        raise ValueError(f"unsupported BGP backend: {backend}")
    node.setLabel(BGP_BACKEND_LABEL, value)
    try:
        node.setRoutingBackend(value)
    except AttributeError:
        pass
    try:
        node.setAttribute(BGP_BACKEND_ATTR, value)
    except AttributeError:
        pass


def claim_external_bgp_backend(node: Router) -> Router:
    set_bgp_backend(node, BGP_BACKEND_EXTERNAL)
    return node


def _normalize_export_policy(policy: Any) -> str:
    value = str(policy or BGP_EXPORT_ALL).strip().lower()
    if value not in {BGP_EXPORT_ALL, BGP_EXPORT_LOCAL_AND_CUSTOMER}:
        raise ValueError(f"unsupported export policy: {policy}")
    return value


def _infer_family(address: str) -> str:
    return BGP_FAMILY_IPV6 if ":" in _normalize_bgp_address(address) else BGP_FAMILY_IPV4


def _normalize_bgp_address(address: Any) -> str:
    value = str(address or "").strip()
    if not value:
        return ""
    return normalizeAddressList([value])[0]


def normalize_bgp_families(session: Dict[str, Any]) -> List[str]:
    raw = session.get("families", session.get("family"))
    if raw is None or raw == "":
        if session.get("local_ipv6_address") or session.get("peer_ipv6_address"):
            raw = [BGP_FAMILY_IPV4, BGP_FAMILY_IPV6]
        else:
            local = str(session.get("local_address") or "").strip()
            peer = str(session.get("peer_address") or "").strip()
            raw = [_infer_family(local)] if local and peer else [BGP_FAMILY_IPV4]
    if isinstance(raw, (AddressFamily, int, str)):
        raw = [raw]
    families: List[str] = []
    for family in raw:
        try:
            selected = normalizeAddressFamily(family)
        except ValueError:
            raise ValueError(f"unsupported BGP address family: {family}")
        value = BGP_FAMILY_IPV6 if selected == AddressFamily.IPv6 else BGP_FAMILY_IPV4
        if value not in families:
            families.append(value)
    if not families:
        families.append(BGP_FAMILY_IPV4)
    return families


def normalize_bgp_session(session: Dict[str, Any]) -> Dict[str, Any]:
    name = str(session.get("name") or "session").strip() or "session"
    kind = str(session.get("kind") or BGP_KIND_EBGP).strip().lower() or BGP_KIND_EBGP
    if kind not in {BGP_KIND_EBGP, BGP_KIND_IBGP}:
        raise ValueError(f"unsupported BGP session kind: {kind}")

    local_address = _normalize_bgp_address(session.get("local_address"))
    peer_address = _normalize_bgp_address(session.get("peer_address"))
    local_ipv6_address = _normalize_bgp_address(session.get("local_ipv6_address"))
    peer_ipv6_address = _normalize_bgp_address(session.get("peer_ipv6_address"))
    local_asn = int(session.get("local_asn") or 0)
    peer_asn = int(session.get("peer_asn") or 0)
    families = normalize_bgp_families(session)
    if BGP_FAMILY_IPV4 in families and (not local_address or not peer_address):
        raise ValueError("IPv4 BGP session must include local_address and peer_address")
    if BGP_FAMILY_IPV6 in families and (not local_ipv6_address or not peer_ipv6_address):
        if local_address and peer_address and _infer_family(local_address) == BGP_FAMILY_IPV6 and _infer_family(peer_address) == BGP_FAMILY_IPV6:
            local_ipv6_address = local_address
            peer_ipv6_address = peer_address
            local_address = ""
            peer_address = ""
        else:
            raise ValueError("IPv6 BGP session must include local_ipv6_address and peer_ipv6_address")
    if local_asn <= 0 or peer_asn <= 0:
        raise ValueError("BGP session must include positive local_asn and peer_asn")

    route_server_client = bool(session.get("route_server_client", False))
    import_community = session.get("import_community")
    import_community = str(import_community).strip() if import_community not in {None, ""} else None
    local_pref_value = session.get("local_pref")
    local_pref = int(local_pref_value) if local_pref_value not in {None, ""} else None

    normalized = {
        "name": name,
        "kind": kind,
        "local_address": local_address,
        "local_ipv6_address": local_ipv6_address,
        "local_asn": local_asn,
        "peer_address": peer_address,
        "peer_ipv6_address": peer_ipv6_address,
        "peer_asn": peer_asn,
        "families": families,
        "import_community": import_community,
        "local_pref": local_pref,
        "export_policy": _normalize_export_policy(session.get("export_policy")),
        "next_hop_self": bool(session.get("next_hop_self", False)),
        "route_server_client": route_server_client,
        "igp_table": str(session.get("igp_table") or "t_ospf").strip() or "t_ospf",
        "igp_table_v6": str(session.get("igp_table_v6") or "t_ospf6").strip() or "t_ospf6",
    }

    if kind == BGP_KIND_IBGP and normalized["local_asn"] != normalized["peer_asn"]:
        raise ValueError("iBGP session must use the same local_asn and peer_asn")
    if route_server_client and kind != BGP_KIND_EBGP:
        raise ValueError("route_server_client is only valid for eBGP sessions")

    return normalized


def record_bgp_session(node: Router, session: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_bgp_session(session)
    sessions = [dict(item) for item in list(node.getAttribute(BGP_SESSION_INTENTS_ATTR, []) or []) if isinstance(item, dict)]
    sessions = [item for item in sessions if str(item.get("name") or "") != normalized["name"]]
    sessions.append(normalized)
    node.setAttribute(BGP_SESSION_INTENTS_ATTR, sessions)
    return dict(normalized)


def split_bgp_session_families(session: Dict[str, Any]) -> List[Dict[str, Any]]:
    normalized = normalize_bgp_session(session)
    out: List[Dict[str, Any]] = []
    for family in normalized["families"]:
        item = dict(normalized)
        item["families"] = [family]
        if family == BGP_FAMILY_IPV6:
            item["name"] = f"{normalized['name']}_v6"
        out.append(item)
    return out


def get_bgp_sessions(node: Router) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for item in list(node.getAttribute(BGP_SESSION_INTENTS_ATTR, []) or []):
        if not isinstance(item, dict):
            continue
        out.extend(split_bgp_session_families(item))
    return out


def mark_bgp_connected_export(node: Router) -> None:
    node.setAttribute(BGP_CONNECTED_EXPORT_ATTR, True)


def has_bgp_connected_export(node: Router) -> bool:
    return bool(node.getAttribute(BGP_CONNECTED_EXPORT_ATTR, False))


def ensure_bird_bgp_base(node: Router) -> None:
    if get_bgp_backend(node) != "bird":
        return
    if not node.getAttribute(BGP_BOOTSTRAPPED_ATTR, False):
        node.setAttribute(BGP_BOOTSTRAPPED_ATTR, True)
        node.appendFile("/etc/bird/bird.conf", BIRD_BGP_COMMONS_TEMPLATE.format(localAsn=node.getAsn()))
    node.addTable("t_bgp")
    node.addTablePipe("t_bgp")
    wants_ipv6 = any(BGP_FAMILY_IPV6 in session["families"] for session in get_bgp_sessions(node))
    if wants_ipv6:
        node.addTable("t_bgp6", family="ipv6")
        node.addTablePipe("t_bgp6", "master6")
    if has_bgp_connected_export(node) and not node.getAttribute(BGP_CONNECTED_EXPORT_RENDERED_ATTR, False):
        node.addTablePipe("t_direct", "t_bgp", exportFilter=CONNECTED_EXPORT_FILTER)
        if wants_ipv6:
            node.addTablePipe("t_direct6", "t_bgp6", exportFilter=CONNECTED_EXPORT_FILTER_V6)
        node.setAttribute(BGP_CONNECTED_EXPORT_RENDERED_ATTR, True)


def _bird_import_clause(session: Dict[str, Any]) -> str:
    if session["import_community"] and session["local_pref"] is not None:
        return (
            "filter {\n"
            f"            bgp_large_community.add({session['import_community']});\n"
            f"            bgp_local_pref = {int(session['local_pref'])};\n"
            "            accept;\n"
            "        }"
        )
    return "all"


def _bird_export_clause(session: Dict[str, Any]) -> str:
    if session["export_policy"] == BGP_EXPORT_LOCAL_AND_CUSTOMER:
        return "where bgp_large_community ~ [LOCAL_COMM, CUSTOMER_COMM]"
    return "all"


def _bird_family_block(session: Dict[str, Any], family: str, *, ibgp: bool = False, rs_client: bool = False) -> str:
    table = "t_bgp6" if family == BGP_FAMILY_IPV6 else "t_bgp"
    if rs_client:
        return (
            f"    {family} {{\n"
            "        import all;\n"
            "        export all;\n"
            "    };\n"
        )
    if ibgp:
        igp_table = session["igp_table_v6"] if family == BGP_FAMILY_IPV6 else session["igp_table"]
        return (
            f"    {family} {{\n"
            f"        table {table};\n"
            "        import all;\n"
            "        export all;\n"
            f"        igp table {igp_table};\n"
            "    };\n"
        )
    next_hop_self_clause = "        next hop self;\n" if session["next_hop_self"] else ""
    return (
        f"    {family} {{\n"
        f"        table {table};\n"
        f"        import {_bird_import_clause(session)};\n"
        f"        export {_bird_export_clause(session)};\n"
        f"{next_hop_self_clause}"
        "    };\n"
    )


def render_bird_protocol_body(session: Dict[str, Any]) -> str:
    normalized = normalize_bgp_session(session)
    if normalized["route_server_client"]:
        local_address = normalized["local_ipv6_address"] if normalized["families"] == [BGP_FAMILY_IPV6] else normalized["local_address"]
        peer_address = normalized["peer_ipv6_address"] if normalized["families"] == [BGP_FAMILY_IPV6] else normalized["peer_address"]
        return BIRD_RS_PEER_TEMPLATE.format(
            familyBlocks="".join(_bird_family_block(normalized, family, rs_client=True) for family in normalized["families"]),
            localAddress=local_address,
            localAsn=normalized["local_asn"],
            peerAddress=peer_address,
            peerAsn=normalized["peer_asn"],
        )
    if normalized["kind"] == BGP_KIND_IBGP:
        local_address = normalized["local_ipv6_address"] if normalized["families"] == [BGP_FAMILY_IPV6] else normalized["local_address"]
        peer_address = normalized["peer_ipv6_address"] if normalized["families"] == [BGP_FAMILY_IPV6] else normalized["peer_address"]
        return BIRD_IBGP_PEER_TEMPLATE.format(
            familyBlocks="".join(_bird_family_block(normalized, family, ibgp=True) for family in normalized["families"]),
            localAddress=local_address,
            localAsn=normalized["local_asn"],
            peerAddress=peer_address,
            peerAsn=normalized["peer_asn"],
        )
    local_address = normalized["local_ipv6_address"] if normalized["families"] == [BGP_FAMILY_IPV6] else normalized["local_address"]
    peer_address = normalized["peer_ipv6_address"] if normalized["families"] == [BGP_FAMILY_IPV6] else normalized["peer_address"]
    return BIRD_ROUTER_PEER_TEMPLATE.format(
        familyBlocks="".join(_bird_family_block(normalized, family) for family in normalized["families"]),
        localAddress=local_address,
        localAsn=normalized["local_asn"],
        peerAddress=peer_address,
        peerAsn=normalized["peer_asn"],
    )


def install_router_bgp_session(node: Router, session: Dict[str, Any]) -> Dict[str, Any]:
    normalized = record_bgp_session(node, session)
    if not normalized["route_server_client"]:
        mark_bgp_connected_export(node)
    return normalized


def classify_ospf_interfaces(
    node: Router,
    *,
    stubs: Iterable[str] = (),
    masked: Iterable[str] = (),
) -> Tuple[List[str], List[str]]:
    stub_names = {str(name) for name in stubs}
    masked_names = {str(name) for name in masked}
    active: List[str] = []
    passive: List[str] = ["dummy0"]
    for iface in node.getInterfaces():
        net = iface.getNet()
        name = str(net.getName())
        if name in masked_names:
            continue
        if name in stub_names or net.getType() != NetworkType.Local:
            passive.append(name)
            continue
        active.append(name)
    return active, passive


def set_ospf_interface_intents(node: Router, active: Iterable[str], passive: Iterable[str], families: Iterable[str] = (BGP_FAMILY_IPV4,)) -> None:
    normalized_families = normalize_bgp_families({"families": families})
    node.setAttribute(
        OSPF_INTERFACE_INTENTS_ATTR,
        {
            "active": sorted({str(name) for name in active}),
            "passive": sorted({str(name) for name in passive}),
            "families": normalized_families,
        },
    )


def get_ospf_interface_intents(node: Router) -> Dict[str, List[str]]:
    raw = node.getAttribute(OSPF_INTERFACE_INTENTS_ATTR, {}) or {}
    active = [str(name) for name in list(raw.get("active", []) or [])]
    passive = [str(name) for name in list(raw.get("passive", []) or [])]
    families = normalize_bgp_families({"families": raw.get("families", [BGP_FAMILY_IPV4])})
    return {"active": active, "passive": passive, "families": families}
