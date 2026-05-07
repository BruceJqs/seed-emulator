# Z30: B30 Mini Internet ExaBGP IX Tool Discovery

`Z30` is the agent-facing runtime bundle for
`examples/internet/B30_mini_internet_exabgp_ix/output`.

Use it when the goal is to discover ExaBGP and IX route-server evidence surfaces
in a mini-internet runtime without changing configuration or route state.

## Best Use

- ExaBGP IX tool discovery
- route-server and peer evidence collection
- read-only BGP observability rehearsal
- documenting what a future controlled experiment could safely target

## Tool Path

1. `workspace_refresh`
2. `inventory_list_nodes`
3. `routing_protocol_summary`
4. `routing_looking_glass`
5. `ops_logs` / `ops_exec` for bounded read-only evidence collection

## Read-Only Boundary

This bundle is evidence-only. Do not edit files, restart services, change Docker
state, announce prefixes, withdraw prefixes, inject faults, or alter BGP policy.

Allowed shell use is limited to commands such as `cat`, `tail`, `grep`, `ps`,
`ss`, and read-only routing CLI inspection.

## Command

```bash
./scripts/seed-codex run \
  "Attach to examples/internet/B30_mini_internet_exabgp_ix/output; locate the ExaBGP IX tool surfaces, summarize peers, route-server evidence, logs, listeners, and current announcements without making configuration changes." \
  --workspace-name z30_probe \
  --attach-output-dir examples/internet/B30_mini_internet_exabgp_ix/output \
  --policy read_only
```

## Mission Entry

```bash
./scripts/seed-codex mission start \
  --task TS_B30_EXABGP_IX_TOOL_DISCOVERY \
  --objective "Discover ExaBGP IX tool evidence surfaces without changing configuration" \
  --attach-output-dir examples/internet/B30_mini_internet_exabgp_ix/output
```

## Status

- live readiness: `conditional_go`
- read-only evidence collection only
- intended to sit between the A13 ExaBGP control-plane bundle and the A14 event looking-glass bundle
