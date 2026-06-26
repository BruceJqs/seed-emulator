# SEED Showcase Design Principles

## Model

Simple default model. Clean extension points. Minimal built-in special cases.

## Showcase Unit

Each incident case publishes the same minimum surface:

| Surface | Required Facts |
|---|---|
| topology | roles, node/container counts, external and provider viewpoints |
| mechanism | normal state, injected fault, degraded state, constrained recovery |
| runtime | one command path, live container gate, artifact root |
| intervention | roles, observations, notes, allowed actions, phase gates |
| code | generator, controller, policy, panel, validation test |
| boundary | S1.5 acceptance, S2 guard, out-of-scope service fidelity |

## Document Split

Use two documents when a showcase needs both design and code detail.

| Document | Contents | Excludes |
|---|---|---|
| Design | model, roles, topology shape, mechanism, extension points | code excerpts, run logs, screenshots |
| Implementation | files, source snippets, commands, artifacts, current limits | long-lived design claims |

## Design Page

Required sections:

1. `Model`
2. `Topology`
3. `Mechanism`
4. `Extension Points`
5. `Validation Surface`
6. `Showcase Surface`

Rules:

- Start with topology facts.
- State node/container counts.
- State role names.
- Use one topology block or diagram.
- Keep background out.
- Keep concepts stable across code changes.

## Implementation Page

Required sections:

1. `Files`
2. `Runtime Scale`
3. `Code Points`
4. `Run`
5. `Evidence`
6. `Assets`

Rules:

- Link every file.
- Verify links before commit.
- Use short code excerpts.
- Add comments only around design decisions.
- Put commands before screenshots.
- Keep generated images beside their prompt.

## Visuals

Use visuals only when they answer a missing question.

Useful visuals:

| Visual | Use |
|---|---|
| topology view | show roles, links, and the fault path |
| phase timeline | show baseline, impact, triage, mitigation, verification |
| case matrix | compare scale, mechanism, panel, and recovery gate |
| panel screenshot | show current runtime artifacts from a live or collected run |

AI-generated raster images are acceptable presentation assets. They must carry
case identity, scale, mechanism, validation loop, and S2 boundary. Avoid
decorative-only images.

Do not build custom SVG or overlay tooling unless exact machine-readable
topology proof is required. Prefer real panel or map screenshots for evidence.

Do not use generated images as proof of runtime behavior.

## Tests

A test section should be runnable in one pass.

```sh
generate
up
normal
inject fault
fault
recover
collect
down
```

Show only the commands needed for the target run. Put full logs in artifacts.
