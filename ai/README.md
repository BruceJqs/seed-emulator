# SEED AI Assets

This directory is the repository-owned entry point for AI-assisted SEED work. It
keeps project skills, future MCP contracts, and agent-facing conventions close to
the code they describe.

## Layout

```text
ai/
  skills/
    seed-control-plane-design/
      SKILL.md
  mcp/
    README.md
```

## Current Scope

- `skills/seed-control-plane-design`: design-review rules for BIRD/FRR,
  ExaBGP, BGP/OSPF intent, Looking Glass, and runtime validation evidence.
- `mcp/`: planning surface for future SeedOps MCP contracts, risk gates, and
  evidence export.

## Expansion Rules

- Add a skill only when it captures a reusable workflow or design boundary.
- Keep `SKILL.md` concise; move large reference material to a `references/`
  folder inside that skill only when needed.
- Do not commit secrets, local Codex state, runtime outputs, or generated Docker
  artifacts.
- MCP contracts should separate read-only inventory/inspection from controlled
  mutation tools.

Planned skill families:

- `seed-email-service-ops`: DNS/MX/SMTP/IMAP/Roundcube service-chain diagnosis.
- `seed-agent-benchmark-authoring`: incident package, oracle, scorer, and replay
  evidence authoring.
- `seed-runtime-evidence`: repeatable config/process/neighbor/route/page/log
  validation patterns.
