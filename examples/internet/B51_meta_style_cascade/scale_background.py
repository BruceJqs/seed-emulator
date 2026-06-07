#!/usr/bin/env python3
import argparse
import ipaddress
import json
import random
from collections import Counter
from pathlib import Path


CASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = CASE_DIR / "scale_tiers.json"
DEFAULT_OUTPUT_ROOT = CASE_DIR / "test_log" / "telemetry"
BASE_ASN = 65000


def _load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def _tier_config(config: dict, tier: str) -> dict:
    try:
        return config["tiers"][tier]
    except KeyError:
        raise SystemExit(f"unknown tier {tier}; expected one of {', '.join(sorted(config['tiers']))}")


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        json.dump(value, fp, indent=2, sort_keys=True)
        fp.write("\n")


def _write_jsonl(path: Path, rows) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as fp:
        for row in rows:
            fp.write(json.dumps(row, sort_keys=True, separators=(",", ":")))
            fp.write("\n")
            count += 1
    return count


def _read_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if line:
                yield json.loads(line)


def _noise_prefix(index: int) -> str:
    network = ipaddress.ip_network("100.64.0.0/10")
    base = int(network.network_address) + (index * 256)
    return str(ipaddress.ip_network((base, 24)))


def _role_counts(tier_cfg: dict) -> Counter:
    role_counts = Counter()
    role_counts["transit"] = tier_cfg["transit_count"]
    role_counts["regional"] = tier_cfg["regional_isp_count"]
    role_counts["route_collector"] = tier_cfg["route_collector_count"]
    role_counts["meta_edge"] = tier_cfg["meta_edge_pop_count"]
    role_counts["meta_dc"] = tier_cfg["meta_dc_count"]
    assigned = sum(role_counts.values())
    role_counts["stub"] = tier_cfg["logical_as_count"] - assigned
    if tier_cfg.get("stub_count") != role_counts["stub"]:
        raise SystemExit(f"stub_count must be {role_counts['stub']} for configured logical_as_count")
    if role_counts["stub"] < tier_cfg["probe_count"]:
        raise SystemExit("probe_count must fit into stub/background AS inventory")
    return role_counts


def _as_inventory(tier: str, tier_cfg: dict):
    role_counts = _role_counts(tier_cfg)
    asn = BASE_ASN
    for role in ("transit", "regional", "route_collector", "meta_edge", "meta_dc", "stub"):
        for idx in range(role_counts[role]):
            yield {
                "asn": asn,
                "tier": tier,
                "role": role,
                "name": f"{tier.lower()}-{role}-{idx + 1:05d}",
                "ix_presence": (idx % tier_cfg["ix_count"]) + 1,
                "customer_cone": (idx % max(1, tier_cfg["transit_count"])) + 1
            }
            asn += 1


def _links(tier: str, tier_cfg: dict):
    transit_asns = list(range(BASE_ASN, BASE_ASN + tier_cfg["transit_count"]))
    regional_start = BASE_ASN + tier_cfg["transit_count"]
    regional_asns = list(range(regional_start, regional_start + tier_cfg["regional_isp_count"]))
    collector_start = regional_start + tier_cfg["regional_isp_count"]
    collector_asns = list(range(collector_start, collector_start + tier_cfg["route_collector_count"]))
    meta_edge_start = collector_start + tier_cfg["route_collector_count"]
    meta_edge_asns = list(range(meta_edge_start, meta_edge_start + tier_cfg["meta_edge_pop_count"]))
    meta_dc_start = meta_edge_start + tier_cfg["meta_edge_pop_count"]
    meta_dc_asns = list(range(meta_dc_start, meta_dc_start + tier_cfg["meta_dc_count"]))
    stub_start = meta_dc_start + tier_cfg["meta_dc_count"]
    stub_asns = list(range(stub_start, BASE_ASN + tier_cfg["logical_as_count"]))

    for idx, asn in enumerate(transit_asns):
        yield {"tier": tier, "relationship": "ix_presence", "asn": asn, "ix": (idx % tier_cfg["ix_count"]) + 1}
        yield {
            "tier": tier,
            "relationship": "peer",
            "left_asn": asn,
            "right_asn": transit_asns[(idx + 1) % len(transit_asns)],
            "ix": (idx % tier_cfg["ix_count"]) + 1
        }

    for idx, asn in enumerate(regional_asns):
        yield {
            "tier": tier,
            "relationship": "provider_customer",
            "provider_asn": transit_asns[idx % len(transit_asns)],
            "customer_asn": asn,
            "ix": (idx % tier_cfg["ix_count"]) + 1
        }

    for idx, asn in enumerate(stub_asns):
        yield {
            "tier": tier,
            "relationship": "provider_customer",
            "provider_asn": regional_asns[idx % len(regional_asns)],
            "customer_asn": asn,
            "ix": (idx % tier_cfg["ix_count"]) + 1
        }

    for idx, asn in enumerate(collector_asns):
        yield {
            "tier": tier,
            "relationship": "collector_peer",
            "collector_asn": asn,
            "observed_asn": transit_asns[idx % len(transit_asns)],
            "ix": (idx % tier_cfg["ix_count"]) + 1
        }

    for idx, asn in enumerate(meta_edge_asns):
        yield {
            "tier": tier,
            "relationship": "meta_edge_external",
            "edge_asn": asn,
            "transit_asn": transit_asns[idx % len(transit_asns)],
            "ix": (idx % tier_cfg["ix_count"]) + 1
        }

    for edge_asn in meta_edge_asns:
        for dc_asn in meta_dc_asns:
            yield {
                "tier": tier,
                "relationship": "meta_internal_dependency",
                "edge_asn": edge_asn,
                "dc_asn": dc_asn,
                "path_class": "health-gated-backbone"
            }


def _collector_asns(tier_cfg: dict):
    collector_start = BASE_ASN + tier_cfg["transit_count"] + tier_cfg["regional_isp_count"]
    return list(range(collector_start, collector_start + tier_cfg["route_collector_count"]))


def _probe_asns(tier_cfg: dict):
    stub_start = (
        BASE_ASN
        + tier_cfg["transit_count"]
        + tier_cfg["regional_isp_count"]
        + tier_cfg["route_collector_count"]
        + tier_cfg["meta_edge_pop_count"]
        + tier_cfg["meta_dc_count"]
    )
    return list(range(stub_start, stub_start + tier_cfg["probe_count"]))


def _resolver_asns(tier_cfg: dict):
    probes = _probe_asns(tier_cfg)
    count = tier_cfg["recursive_resolver_count"]
    return [probes[idx % len(probes)] for idx in range(count)]


def _route_views(tier: str, tier_cfg: dict, shared: dict, rng: random.Random):
    collectors = _collector_asns(tier_cfg)
    edge_origin = BASE_ASN + tier_cfg["transit_count"] + tier_cfg["regional_isp_count"] + tier_cfg["route_collector_count"]
    transit_base = BASE_ASN
    for idx, collector_asn in enumerate(collectors):
        delay_span = tier_cfg["required_collector_delay_variance_ms"] + 1500
        delay = 500 + idx * delay_span // max(1, len(collectors) - 1)
        yield {
            "tier": tier,
            "phase": "normal",
            "collector": f"collector-{idx + 1:02d}",
            "collector_asn": collector_asn,
            "prefix": shared["dns_prefix"],
            "state": "visible",
            "origin_asn": edge_origin,
            "as_path": [collector_asn, transit_base + (idx % tier_cfg["transit_count"]), edge_origin],
            "delay_ms": delay
        }
        yield {
            "tier": tier,
            "phase": "fault",
            "collector": f"collector-{idx + 1:02d}",
            "collector_asn": collector_asn,
            "prefix": shared["dns_prefix"],
            "state": "withdrawn",
            "origin_asn": edge_origin,
            "as_path": [],
            "delay_ms": delay + 2500 + rng.randint(0, 600)
        }
        yield {
            "tier": tier,
            "phase": "recovery",
            "collector": f"collector-{idx + 1:02d}",
            "collector_asn": collector_asn,
            "prefix": shared["dns_prefix"],
            "state": "visible",
            "origin_asn": edge_origin,
            "as_path": [collector_asn, transit_base + (idx % tier_cfg["transit_count"]), edge_origin],
            "delay_ms": delay + 7000 + rng.randint(0, 900)
        }

    for idx in range(tier_cfg["noise_prefix_count"]):
        prefix = _noise_prefix(idx)
        origin = BASE_ASN + tier_cfg["transit_count"] + idx % max(1, tier_cfg["regional_isp_count"])
        flap = idx < tier_cfg["route_flap_count"]
        for collector_idx, collector_asn in enumerate(collectors):
            yield {
                "tier": tier,
                "phase": "background",
                "collector": f"collector-{collector_idx + 1:02d}",
                "collector_asn": collector_asn,
                "prefix": prefix,
                "state": "flap" if flap else "stable",
                "origin_asn": origin,
                "as_path": [collector_asn, BASE_ASN + ((idx + collector_idx) % tier_cfg["transit_count"]), origin],
                "delay_ms": rng.randint(300, 12000)
            }


def _probe_logs(tier: str, tier_cfg: dict, shared: dict, rng: random.Random):
    probes = _probe_asns(tier_cfg)
    resolvers = _resolver_asns(tier_cfg)
    for idx, probe_asn in enumerate(probes):
        resolver_asn = resolvers[idx % len(resolvers)]
        cone = (idx % tier_cfg["required_customer_cones"]) + 1
        ttl_jitter = 1000 + rng.randint(0, 9000)
        probe = f"probe-{idx + 1:04d}"
        yield {
            "tier": tier,
            "phase": "normal",
            "probe": probe,
            "probe_asn": probe_asn,
            "resolver_asn": resolver_asn,
            "customer_cone": cone,
            "domain": shared["domain"],
            "dig_status": "NOERROR",
            "answer": shared["edge_service"],
            "curl_status": 200,
            "route_visible": True,
            "sample_delay_ms": ttl_jitter
        }
        fault_status = "SERVFAIL" if idx % 3 else "TIMEOUT"
        yield {
            "tier": tier,
            "phase": "fault",
            "probe": probe,
            "probe_asn": probe_asn,
            "resolver_asn": resolver_asn,
            "customer_cone": cone,
            "domain": shared["domain"],
            "dig_status": fault_status,
            "answer": "",
            "curl_status": 0,
            "route_visible": False,
            "sample_delay_ms": ttl_jitter + 4000 + rng.randint(0, 6000)
        }
        yield {
            "tier": tier,
            "phase": "recovery",
            "probe": probe,
            "probe_asn": probe_asn,
            "resolver_asn": resolver_asn,
            "customer_cone": cone,
            "domain": shared["domain"],
            "dig_status": "NOERROR",
            "answer": shared["edge_service"],
            "curl_status": 200,
            "route_visible": True,
            "sample_delay_ms": ttl_jitter + 12000 + rng.randint(0, 6000)
        }


def _events(tier: str, tier_cfg: dict, shared: dict):
    return [
        {
            "tier": tier,
            "sequence": 10,
            "phase": "normal",
            "component": "health_gate",
            "event": "healthy",
            "detail": f"backend {shared['backend_dependency']} reachable"
        },
        {
            "tier": tier,
            "sequence": 20,
            "phase": "fault",
            "component": "internal_backbone",
            "event": "policy_change",
            "detail": shared["root_cause"]
        },
        {
            "tier": tier,
            "sequence": 30,
            "phase": "fault",
            "component": "health_gate",
            "event": "unhealthy",
            "detail": "backend_reachable=false"
        },
        {
            "tier": tier,
            "sequence": 40,
            "phase": "fault",
            "component": "bgp",
            "event": "withdraw",
            "detail": f"withdraw {shared['dns_prefix']}"
        },
        {
            "tier": tier,
            "sequence": 50,
            "phase": "fault",
            "component": "external_probes",
            "event": "dns_service_failure",
            "detail": f"{tier_cfg['probe_count']} probes observe resolver/service failures"
        },
        {
            "tier": tier,
            "sequence": 60,
            "phase": "recovery",
            "component": "internal_backbone",
            "event": "rollback_policy_change",
            "detail": "internal reachability restored before reannouncement"
        },
        {
            "tier": tier,
            "sequence": 70,
            "phase": "recovery",
            "component": "bgp",
            "event": "canary_reannounce",
            "detail": f"route collectors observe {shared['dns_prefix']} returning"
        }
    ]


def generate(tier: str, config_path: Path, output_root: Path) -> Path:
    config = _load_config(config_path)
    tier_cfg = _tier_config(config, tier)
    shared = config["shared"]
    rng = random.Random(tier_cfg["random_seed"])
    out_dir = output_root / tier
    out_dir.mkdir(parents=True, exist_ok=True)

    as_count = _write_jsonl(out_dir / "as_inventory.jsonl", _as_inventory(tier, tier_cfg))
    link_count = _write_jsonl(out_dir / "links.jsonl", _links(tier, tier_cfg))
    route_view_count = _write_jsonl(out_dir / "route_views.jsonl", _route_views(tier, tier_cfg, shared, rng))
    probe_log_count = _write_jsonl(out_dir / "probe_logs.jsonl", _probe_logs(tier, tier_cfg, shared, rng))
    event_count = _write_jsonl(out_dir / "events.jsonl", _events(tier, tier_cfg, shared))

    manifest = {
        "schema": "meta-style-cascade-scale-artifacts-v1",
        "tier": tier,
        "description": tier_cfg["description"],
        "random_seed": tier_cfg["random_seed"],
        "domain": shared["domain"],
        "dns_prefix": shared["dns_prefix"],
        "root_cause": shared["root_cause"],
        "counts": {
            "logical_as": as_count,
            "links": link_count,
            "route_view_rows": route_view_count,
            "probe_log_rows": probe_log_count,
            "events": event_count,
            "route_collectors": tier_cfg["route_collector_count"],
            "probes": tier_cfg["probe_count"],
            "recursive_resolvers": tier_cfg["recursive_resolver_count"],
            "ix": tier_cfg["ix_count"],
            "noise_prefixes": tier_cfg["noise_prefix_count"],
            "route_flaps": tier_cfg["route_flap_count"],
            "meta_edge_pops": tier_cfg["meta_edge_pop_count"],
            "meta_dcs": tier_cfg["meta_dc_count"]
        },
        "thresholds": {
            "required_customer_cones": tier_cfg["required_customer_cones"],
            "required_collector_delay_variance_ms": tier_cfg["required_collector_delay_variance_ms"]
        },
        "files": {
            "as_inventory": "as_inventory.jsonl",
            "links": "links.jsonl",
            "route_views": "route_views.jsonl",
            "probe_logs": "probe_logs.jsonl",
            "events": "events.jsonl"
        }
    }
    _write_json(out_dir / "manifest.json", manifest)
    return out_dir


def _fail(errors: list, message: str) -> None:
    errors.append(message)


def verify(tier: str, config_path: Path, output_root: Path) -> Path:
    config = _load_config(config_path)
    tier_cfg = _tier_config(config, tier)
    shared = config["shared"]
    out_dir = output_root / tier
    manifest_path = out_dir / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"missing manifest: {manifest_path}")
    with manifest_path.open("r", encoding="utf-8") as fp:
        manifest = json.load(fp)

    errors = []
    if manifest.get("tier") != tier:
        _fail(errors, "manifest tier mismatch")
    if manifest["counts"]["logical_as"] != tier_cfg["logical_as_count"]:
        _fail(errors, "logical AS count mismatch")
    if manifest["counts"]["route_collectors"] != tier_cfg["route_collector_count"]:
        _fail(errors, "route collector count mismatch")
    if manifest["counts"]["probes"] != tier_cfg["probe_count"]:
        _fail(errors, "probe count mismatch")

    role_counts = Counter(row["role"] for row in _read_jsonl(out_dir / "as_inventory.jsonl"))
    for role, expected in _role_counts(tier_cfg).items():
        if role_counts[role] != expected:
            _fail(errors, f"role count mismatch for {role}: {role_counts[role]} != {expected}")

    route_rows = list(_read_jsonl(out_dir / "route_views.jsonl"))
    meta_rows = [row for row in route_rows if row["prefix"] == shared["dns_prefix"]]
    if not any(row["phase"] == "normal" and row["state"] == "visible" for row in meta_rows):
        _fail(errors, "meta prefix missing normal visible route-view rows")
    if not any(row["phase"] == "fault" and row["state"] == "withdrawn" for row in meta_rows):
        _fail(errors, "meta prefix missing fault withdrawn route-view rows")
    if not any(row["phase"] == "recovery" and row["state"] == "visible" for row in meta_rows):
        _fail(errors, "meta prefix missing recovery visible route-view rows")
    delays = [row["delay_ms"] for row in meta_rows if row["phase"] == "fault"]
    if not delays or max(delays) - min(delays) < tier_cfg["required_collector_delay_variance_ms"]:
        _fail(errors, "collector delay variance too small")
    if any(row["prefix"] == shared["dns_prefix"] and row["phase"] == "background" for row in route_rows):
        _fail(errors, "background noise touches protected DNS prefix")

    probe_rows = list(_read_jsonl(out_dir / "probe_logs.jsonl"))
    phase_counts = Counter(row["phase"] for row in probe_rows)
    expected_probe_rows = tier_cfg["probe_count"]
    for phase in ("normal", "fault", "recovery"):
        if phase_counts[phase] != expected_probe_rows:
            _fail(errors, f"probe phase count mismatch for {phase}")
    if any(row["phase"] == "normal" and row["dig_status"] != "NOERROR" for row in probe_rows):
        _fail(errors, "normal probe has non-success DNS status")
    if any(row["phase"] == "fault" and row["dig_status"] == "NOERROR" for row in probe_rows):
        _fail(errors, "fault probe unexpectedly has successful DNS status")
    if any(row["phase"] == "fault" and row["route_visible"] for row in probe_rows):
        _fail(errors, "fault probe still sees protected route")
    cones = {row["customer_cone"] for row in probe_rows if row["phase"] == "normal"}
    if len(cones) < tier_cfg["required_customer_cones"]:
        _fail(errors, "probe distribution has too few customer cones")
    resolvers = {row["resolver_asn"] for row in probe_rows}
    if len(resolvers) < min(tier_cfg["recursive_resolver_count"], tier_cfg["probe_count"]):
        _fail(errors, "resolver distribution is narrower than configured")

    events = list(_read_jsonl(out_dir / "events.jsonl"))
    event_names = {(row["phase"], row["component"], row["event"]) for row in events}
    required_events = {
        ("normal", "health_gate", "healthy"),
        ("fault", "internal_backbone", "policy_change"),
        ("fault", "health_gate", "unhealthy"),
        ("fault", "bgp", "withdraw"),
        ("fault", "external_probes", "dns_service_failure"),
        ("recovery", "internal_backbone", "rollback_policy_change"),
        ("recovery", "bgp", "canary_reannounce")
    }
    missing = required_events - event_names
    if missing:
        _fail(errors, f"missing event chain entries: {sorted(missing)}")

    forbidden_text = "\n".join(json.dumps(row, sort_keys=True) for row in events + route_rows[:50] + probe_rows[:50])
    for forbidden in shared["forbidden_shortcuts"]:
        if forbidden in forbidden_text:
            _fail(errors, f"forbidden shortcut appears in artifacts: {forbidden}")

    report = {
        "tier": tier,
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "checked": {
            "logical_as": manifest["counts"]["logical_as"],
            "route_collectors": manifest["counts"]["route_collectors"],
            "probes": manifest["counts"]["probes"],
            "route_view_rows": manifest["counts"]["route_view_rows"],
            "probe_log_rows": manifest["counts"]["probe_log_rows"],
            "collector_delay_variance_ms": max(delays) - min(delays) if delays else 0,
            "customer_cones": len(cones),
            "resolver_asns": len(resolvers),
            "normal_probe_rows": phase_counts["normal"],
            "fault_probe_rows": phase_counts["fault"],
            "recovery_probe_rows": phase_counts["recovery"]
        }
    }
    _write_json(out_dir / "verification_report.json", report)
    if errors:
        raise SystemExit(f"{tier} verification failed; see {out_dir / 'verification_report.json'}")
    return out_dir / "verification_report.json"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate and verify B51 S1/S2 telemetry fixtures. "
            "These artifacts are not runtime tier acceptance."
        )
    )
    parser.add_argument("command", choices=("generate", "verify", "run"))
    parser.add_argument("--tier", required=True, choices=("S1", "S2"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()

    if args.command == "generate":
        out_dir = generate(args.tier, args.config, args.output_root)
        print(f"{args.tier} generated at {out_dir}")
    elif args.command == "verify":
        report_path = verify(args.tier, args.config, args.output_root)
        print(f"{args.tier} verification passed: {report_path}")
    else:
        out_dir = generate(args.tier, args.config, args.output_root)
        report_path = verify(args.tier, args.config, args.output_root)
        print(f"{args.tier} generated at {out_dir}")
        print(f"{args.tier} verification passed: {report_path}")


if __name__ == "__main__":
    main()
