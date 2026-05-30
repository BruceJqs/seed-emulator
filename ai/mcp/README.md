# SeedOps MCP Planning

This folder is reserved for repository-owned MCP contracts and tool policy notes.
The target split is:

- read-only tools: runtime inventory, interface map, route state, logs, pages.
- controlled mutation tools: BGP announce/withdraw, scoped policy edits, service
  restart, rollback.
- evidence tools: export route snapshots, command transcripts, event streams,
  scorer inputs.

Mutation tools should require explicit risk metadata, rollback description, and
scenario-scoped confirmation before execution.
