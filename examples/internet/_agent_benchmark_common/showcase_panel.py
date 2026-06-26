#!/usr/bin/env python3
"""Small read-only showcase panel for the internet outage benchmark cases."""

import argparse
import html
import json
import os
import re
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


CASE_DETAILS = {
    "b51": {
        "default_port": 8510,
        "title": "B51 Meta-style cascade",
        "focus": "Health-gated DNS/service prefix withdrawal after an internal edge-to-DC reachability fault.",
        "nodes": ["AS50 resolver/client", "AS20 edge DNS and health gate", "AS30 DC backend", "AS10 transit", "route collectors"],
        "flow": ["External users resolve and reach the service", "Internal edge-to-DC path fails", "Health gate withdraws edge prefix through BGP", "Resolvers and users lose DNS/service reachability", "Policy rollback and canary reannouncement restore service"],
        "default_commands": ["generate-runtime S1.5", "up-runtime S1.5", "normal-runtime S1.5", "demo-snapshot-runtime S1.5 baseline", "inject-fault-runtime S1.5", "fault-runtime S1.5", "exercise-observe-runtime S1.5 all-roles", "recovery-runtime S1.5", "collect-runtime S1.5"],
    },
    "b52": {
        "default_port": 8520,
        "title": "B52 AWS S3 control plane",
        "focus": "Maintenance-driven index and placement capacity loss with healthy object shards.",
        "nodes": ["public clients", "S3 API frontend", "index quorum", "placement quorum", "object shard", "maintenance tool", "capacity registry"],
        "flow": ["API and dependent services work normally", "Maintenance selector removes too much index and placement capacity", "API returns control-plane 503 while object shard stays healthy", "Operator freezes maintenance, restores index, then placement", "Canary PUT and backlog drain verify recovery"],
        "default_commands": ["generate-runtime S1.5", "up-runtime S1.5", "normal-runtime S1.5", "inject-fault-runtime S1.5", "fault-runtime S1.5", "exercise-observe-runtime S1.5 all-roles", "exercise-action-runtime S1.5 mitigate", "recovery-runtime S1.5", "collect-runtime S1.5"],
    },
    "b53": {
        "default_port": 8530,
        "title": "B53 Fastly edge config bug",
        "focus": "Valid customer config propagates to POPs and triggers a latent edge runtime failure.",
        "nodes": ["global clients", "config API", "validator", "compiler", "distributor", "release manager", "8 edge POPs", "customer origins"],
        "flow": ["Config pipeline and POPs serve normally", "Legal trigger config passes validation and compiles", "Distributor sends the artifact to most POPs", "Affected POPs return 5xx while origins stay healthy", "Distribution freeze, rollback, POP canary, and full restore recover service"],
        "default_commands": ["generate-runtime S1.5", "up-runtime S1.5", "normal-runtime S1.5", "inject-fault-runtime S1.5", "fault-runtime S1.5", "exercise-observe-runtime S1.5 provider-ops", "exercise-action-runtime S1.5 mitigate", "recovery-runtime S1.5", "collect-runtime S1.5"],
    },
    "b54": {
        "default_port": 8540,
        "title": "B54 Cloudflare feature file proxy",
        "focus": "Feature-file expansion propagates globally and breaks the core proxy path while origins remain healthy.",
        "nodes": ["clients", "feature DB", "permission rollout", "generator", "distributor", "known-good store", "core proxy POPs", "tail services"],
        "flow": ["Known-good feature file serves normally", "Permission rollout expands feature generation", "Large feature file is distributed globally", "Core proxy and tail services return 5xx while origins stay healthy", "Stop generation, rollback known-good, fail-small, canary, and tail validation recover"],
        "default_commands": ["generate-runtime S1.5", "up-runtime S1.5", "normal-runtime S1.5", "inject-fault-runtime S1.5", "fault-runtime S1.5", "exercise-observe-runtime S1.5 control-plane", "exercise-action-runtime S1.5 mitigate", "recovery-runtime S1.5", "collect-runtime S1.5"],
    },
    "b55": {
        "default_port": 8550,
        "title": "B55 Verizon route leak",
        "focus": "More-specific BGP leak reaches unfiltered networks while the victim service remains healthy.",
        "nodes": ["victim CDN AS55", "legitimate transit AS56", "filtered transit AS57", "Verizon AS701", "DQE AS702", "Allegheny AS703", "probe ASes", "route collectors"],
        "flow": ["Clients use the victim aggregate route", "DQE export enables a leaked 10.55.0.0/25 more-specific", "Unfiltered access networks and collectors learn the leak", "Filtered networks reject it and victim local health stays green", "Withdraw leak and verify aggregate convergence and service recovery"],
        "default_commands": ["generate-runtime S1.5", "up-runtime S1.5", "normal-runtime S1.5", "inject-fault-runtime S1.5", "fault-runtime S1.5", "exercise-observe-runtime S1.5 route-collectors", "exercise-action-runtime S1.5 withdraw-leak", "recovery-runtime S1.5", "collect-runtime S1.5"],
    },
    "b56": {
        "default_port": 8560,
        "title": "B56 Dyn authoritative DNS DDoS",
        "focus": "Authoritative DNS path overload with cache-miss and secondary-provider contrast; DNS processes stay alive.",
        "nodes": ["Dyn authoritative DNS", "recursive resolver", "client probes", "customer origin", "botnet hosts", "scrubber", "secondary authoritative DNS", "route collectors"],
        "flow": ["Fresh recursive lookups and HTTP work normally", "Bot traffic overloads the Dyn authoritative path", "Fresh Dyn-only lookups fail while named and the origin stay healthy", "Secondary-provider lookup remains usable as contrast", "Scrubber/rate-limit and cache-miss validation prove recovery"],
        "default_commands": ["generate-runtime S1.5", "up-runtime S1.5", "normal-runtime S1.5", "inject-fault-runtime S1.5", "fault-runtime S1.5", "exercise-observe-runtime S1.5 resolvers", "exercise-action-runtime S1.5 activate-scrubber", "recovery-runtime S1.5", "collect-runtime S1.5"],
    },
    "b57": {
        "default_port": 8570,
        "title": "B57 Google network congestion",
        "focus": "Maintenance automation deschedules control-plane jobs, fail-static expires, and external reachability degrades.",
        "nodes": ["service frontends", "customer workloads", "maintenance automation", "cluster managers", "network control plane", "config store", "route distributor", "TE controller"],
        "flow": ["Routes and regional frontends work normally", "Automation deschedules control-plane replicas", "Fail-static expires and external route is withdrawn", "Workloads remain locally alive while users fail externally", "Halt automation, reschedule control plane, distribute config, and verify by region"],
        "default_commands": ["generate-runtime S1.5", "up-runtime S1.5", "normal-runtime S1.5", "inject-fault-runtime S1.5", "fault-runtime S1.5", "exercise-observe-runtime S1.5 network-ops", "exercise-action-runtime S1.5 restore-control-plane", "recovery-runtime S1.5", "collect-runtime S1.5"],
    },
}


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def read_text(path, limit=2000):
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    return text[:limit]


def key_values(path):
    values = {}
    for line in read_text(path).splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def count_compose_services(output_dir):
    compose = output_dir / "docker-compose.yml"
    if not compose.exists():
        return 0
    count = 0
    for line in compose.read_text(encoding="utf-8", errors="ignore").splitlines():
        if re.match(r"^\s{2}[A-Za-z0-9_.-]+:\s*$", line):
            count += 1
    return count


def docker_live_count(project):
    if not project:
        return None
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", f"label=com.docker.compose.project={project}", "--format", "{{.Names}}"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return len([line for line in result.stdout.splitlines() if line.strip()])


def artifact_summary(artifact_dir):
    files = list(artifact_dir.rglob("*")) if artifact_dir.exists() else []
    regular = [path for path in files if path.is_file()]
    return {
        "exists": artifact_dir.exists(),
        "file_count": len(regular),
        "runtime_count": key_values(artifact_dir / "runtime_container_count.txt"),
        "normal_files": len(list(artifact_dir.glob("normal*"))),
        "fault_files": len(list(artifact_dir.glob("fault*"))),
        "recovery_files": len(list(artifact_dir.glob("recovery*"))),
        "exercise_dirs": len(list((artifact_dir / "exercise").glob("*"))) if (artifact_dir / "exercise").exists() else 0,
        "collect_files": len(list((artifact_dir / "host").rglob("*"))) if (artifact_dir / "host").exists() else 0,
    }


def build_state(case_dir, case_id, tier, project, prefix):
    details = CASE_DETAILS.get(case_id, {})
    metadata = read_json(case_dir / "case_metadata.json")
    policy = read_json(case_dir / "agent_policy.json")
    output_dir = case_dir / "output"
    artifact_dir = case_dir / "test_log" / "runtime" / tier
    return {
        "case_id": case_id,
        "tier": "S1.5" if tier == "S1_5" else tier,
        "project": project,
        "container_prefix": prefix,
        "metadata": metadata,
        "policy": policy,
        "details": details,
        "output": {
            "compose_exists": (output_dir / "docker-compose.yml").exists(),
            "generated_tier": read_text(output_dir / ".agent-benchmark-runtime-tier", 80).strip()
            or read_text(output_dir / ".b51-runtime-tier", 80).strip(),
            "compose_service_count": count_compose_services(output_dir),
        },
        "runtime": {
            "live_containers": docker_live_count(project),
            "artifacts": artifact_summary(artifact_dir),
        },
        "readme_excerpt": "\n".join(read_text(case_dir / "README.md", 1200).splitlines()[0:12]),
    }


def esc(value):
    return html.escape(str(value), quote=True)


def badge(label, ok):
    cls = "ok" if ok else "missing"
    value = "present" if ok else "missing"
    return f'<span class="badge {cls}">{esc(label)}: {value}</span>'


def render_html(state):
    details = state["details"]
    metadata = state["metadata"]
    artifacts = state["runtime"]["artifacts"]
    runtime_count = artifacts["runtime_count"]
    normal_ok = artifacts["normal_files"] > 0
    fault_ok = artifacts["fault_files"] > 0
    recovery_ok = artifacts["recovery_files"] > 0
    exercise_ok = artifacts["exercise_dirs"] > 0
    compose_ok = state["output"]["compose_exists"]
    live = state["runtime"]["live_containers"]
    current_status = metadata.get("current_runtime_status", metadata.get("scope", "No runtime status recorded."))
    command_lines = [f"bash {state['case_id']}ctl.sh {cmd}" for cmd in details.get("default_commands", [])]
    html_commands = "\n".join(command_lines)
    nodes = "".join(f"<li>{esc(item)}</li>" for item in details.get("nodes", []))
    flow = "".join(f"<li>{esc(item)}</li>" for item in details.get("flow", []))
    normal_evidence = "".join(f"<li>{esc(item)}</li>" for item in metadata.get("normal_evidence", []))
    fault_evidence = "".join(f"<li>{esc(item)}</li>" for item in metadata.get("fault_evidence", []))
    recovery = metadata.get("recovery_sequence", metadata.get("recovery_evidence", []))
    recovery_evidence = "".join(f"<li>{esc(item)}</li>" for item in recovery)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(details.get("title", state["case_id"]))}</title>
  <style>
    :root {{ color-scheme: light; --ink: #16202a; --muted: #5e6a76; --line: #d6dde5; --ok: #127a45; --bad: #a23b32; --panel: #f6f8fb; --accent: #275c9d; }}
    body {{ margin: 0; font: 14px/1.45 system-ui, -apple-system, Segoe UI, sans-serif; color: var(--ink); background: #fff; }}
    header {{ padding: 28px 36px 20px; border-bottom: 1px solid var(--line); background: linear-gradient(180deg, #f8fafc, #fff); }}
    main {{ padding: 24px 36px 40px; display: grid; gap: 18px; grid-template-columns: minmax(0, 1.25fr) minmax(320px, .75fr); }}
    h1 {{ margin: 0 0 8px; font-size: 28px; letter-spacing: 0; }}
    h2 {{ margin: 0 0 10px; font-size: 17px; letter-spacing: 0; }}
    p {{ margin: 0 0 10px; }}
    section {{ border: 1px solid var(--line); border-radius: 8px; padding: 16px; background: #fff; }}
    .wide {{ grid-column: 1 / -1; }}
    .muted {{ color: var(--muted); }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }}
    .metric {{ background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 10px; min-height: 58px; }}
    .metric b {{ display: block; font-size: 20px; }}
    .badge {{ display: inline-block; margin: 4px 6px 4px 0; padding: 4px 8px; border-radius: 999px; border: 1px solid var(--line); font-size: 12px; }}
    .ok {{ color: var(--ok); background: #edf8f2; border-color: #b9e2ca; }}
    .missing {{ color: var(--bad); background: #fff2f0; border-color: #efc5bf; }}
    ol, ul {{ margin: 0; padding-left: 20px; }}
    li {{ margin: 4px 0; }}
    pre {{ overflow: auto; padding: 12px; border-radius: 6px; border: 1px solid var(--line); background: #101820; color: #eaf2fb; font-size: 12px; }}
    .flow {{ display: grid; grid-template-columns: 1fr; gap: 8px; }}
    .flow li {{ padding: 8px 10px; background: var(--panel); border: 1px solid var(--line); border-radius: 6px; }}
    @media (max-width: 900px) {{ main {{ grid-template-columns: 1fr; padding: 18px; }} header {{ padding: 22px 18px 16px; }} .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
  </style>
</head>
<body>
  <header>
    <h1>{esc(details.get("title", state["case_id"]))}</h1>
    <p>{esc(details.get("focus", metadata.get("title", "")))}</p>
    <p class="muted">Tier {esc(state["tier"])} | project {esc(state["project"])} | source case id {esc(metadata.get("id", state["case_id"]))}</p>
  </header>
  <main>
    <section class="wide">
      <h2>Runtime Readiness</h2>
      <div>
        {badge("compose", compose_ok)}
        {badge("normal evidence", normal_ok)}
        {badge("fault evidence", fault_ok)}
        {badge("recovery evidence", recovery_ok)}
        {badge("exercise ledger", exercise_ok)}
      </div>
      <div class="grid">
        <div class="metric"><span class="muted">Live containers</span><b>{esc(live if live is not None else "unknown")}</b></div>
        <div class="metric"><span class="muted">Recorded live gate</span><b>{esc(runtime_count.get("live_containers", "missing"))}</b></div>
        <div class="metric"><span class="muted">Minimum gate</span><b>{esc(runtime_count.get("minimum_required", "missing"))}</b></div>
        <div class="metric"><span class="muted">Artifact files</span><b>{esc(artifacts["file_count"])}</b></div>
      </div>
    </section>
    <section>
      <h2>Incident Structure</h2>
      <ul>{nodes}</ul>
    </section>
    <section>
      <h2>Mechanism Flow</h2>
      <ol class="flow">{flow}</ol>
    </section>
    <section>
      <h2>Evidence Contract</h2>
      <p><b>Normal</b></p>
      <ul>{normal_evidence}</ul>
      <p><b>Fault</b></p>
      <ul>{fault_evidence}</ul>
      <p><b>Recovery</b></p>
      <ul>{recovery_evidence}</ul>
    </section>
    <section>
      <h2>Current Scope</h2>
      <p>{esc(current_status)}</p>
      <p class="muted">S2 remains guarded by preflight and is not part of the default local showcase run.</p>
    </section>
    <section class="wide">
      <h2>Suggested Live Sequence</h2>
      <pre>{esc(html_commands)}</pre>
      <p class="muted">The panel is read-only. It surfaces generated output and runtime artifacts; it does not mutate the emulation.</p>
    </section>
  </main>
</body>
</html>
"""


class PanelHandler(BaseHTTPRequestHandler):
    state_builder = None

    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        path = urlparse(self.path).path
        state = type(self).state_builder()
        if path == "/api/status.json":
            data = json.dumps(state, indent=2, sort_keys=True).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if path in ("/", "/index.html"):
            data = render_html(state).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_error(404)


def main():
    parser = argparse.ArgumentParser(description="Serve or render a showcase panel for an internet outage benchmark case.")
    parser.add_argument("--case-dir", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--tier", default="S0")
    parser.add_argument("--project", default="")
    parser.add_argument("--prefix", default="")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int)
    parser.add_argument("--snapshot-out")
    args = parser.parse_args()

    case_dir = Path(args.case_dir).resolve()
    case_id = args.case_id.lower()
    details = CASE_DETAILS.get(case_id, {})
    port = args.port or int(os.environ.get(f"{case_id.upper()}_SHOWCASE_PORT", details.get("default_port", 8590)))

    def state_builder():
        return build_state(case_dir, case_id, args.tier, args.project, args.prefix)

    if args.snapshot_out:
        out = Path(args.snapshot_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_html(state_builder()), encoding="utf-8")
        print(out)
        return

    PanelHandler.state_builder = state_builder
    server = ThreadingHTTPServer((args.host, port), PanelHandler)
    print(f"showcase panel for {case_id} listening at http://{args.host}:{port}/")
    server.serve_forever()


if __name__ == "__main__":
    main()
