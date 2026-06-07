# B51 Meta-style Cascade Handoff

This is the closure note for the current Meta-style Internet outage example.
The case is ready to be treated as the first completed benchmark-style example
for this branch, with clear runtime limits.

## What Is Complete

- A case-local SEED Internet example lives in this directory and does not modify
  core `seedemu` APIs.
- The topology models an internal edge-to-DC reachability failure that causes a
  health-gated BGP withdrawal of the public DNS/service prefix.
- S0, S1, and S1.5 are real Docker runtime tiers. Telemetry fixture generation
  is explicitly separated from runtime acceptance.
- S1.5 is the largest validated live tier on this host: 225 live containers, 80
  probes, and 16 route collectors.
- The restricted recovery path rolls back the internal path policy fault,
  verifies backend health, waits for health-gate-managed reannouncement, and
  validates external DNS/HTTP and route visibility.
- The interactive S1.5 exercise layer provides staged role observations,
  operator notes, action ledgers, and phase gates. This is the participatory
  exercise path; the old demo runbook is only a facilitator aid.
- S2 is guarded and not accepted. It must not be reported as passed.

## Main Files

- `meta_style_cascade.py`: topology generator and tier construction.
- `b51ctl.sh`: controller for generation, runtime checks, fault injection,
  restricted recovery, telemetry fixtures, S2 preflight, and exercise commands.
- `interactive_exercise_design.md`: participatory S1.5 exercise contract.
- `README.md`: operator-facing entry point.
- `case_metadata.json`: machine-readable scenario metadata and tier boundaries.
- `agent_policy.json`: allowed observations/actions and forbidden shortcuts.
- `scoring_stub.json`: placeholder scoring policy.
- `scale_tiers.json`, `scale_background.py`, `scale_plan.md`: optional
  telemetry fixture generation and scale semantics.
- `progress_p0_p3.md`, `progress_s1_s2.md`: historical validation evidence.
- `HANDOFF.md`: this closure note.

## Test Entries

From the repository root:

```bash
tests/internet/meta_style_cascade/exercise_static.sh
```

This is a non-runtime static check for the exercise ledger and controller
guards. It does not start containers and does not prove runtime behavior.

```bash
COMPOSE_PROJECT_NAME=seed_meta_cascade_runtime \
  PLATFORM=arm \
  SEED_PYTHON=.venv/bin/python \
  tests/internet/meta_style_cascade/full_sequence.sh
```

This runs the configured runtime ladder. The default runtime ladder is S0 and
S1. Set `B51_RUNTIME_LADDER=S1.5` only when intentionally running the larger
intermediate tier.

## S1.5 Interactive Exercise Entry

Use S1.5 when demonstrating the actual participatory incident process:

```bash
cd examples/internet/B51_meta_style_cascade

export TIER=S1.5
export COMPOSE_PROJECT_NAME=seed_meta_cascade_s1_5_exercise
export B51_EXERCISE_ID=run-001
export PLATFORM=arm
export SEED_PYTHON=../../../.venv/bin/python

bash b51ctl.sh generate-runtime S1.5
bash b51ctl.sh up-runtime S1.5
bash b51ctl.sh exercise-init-runtime S1.5
```

Then follow `interactive_exercise_design.md`. The exercise is accepted by the
ledger and phase gates plus runtime recovery validation, not by narration.

## Evidence Already Recorded

Historical evidence is summarized in `progress_s1_s2.md`:

- S0 smoke passed after the runtime/telemetry scale semantics correction.
- S1 ordered runtime passed with 129 live containers.
- S1 restricted intervention and recovery passed.
- S1.5 full intervention runtime passed with 225 live containers, 80 probes,
  and 16 collectors.
- S2 preflight remains diagnostic-only and blocked on this host.
- The S1.5 interactive exercise redesign was statically checked but not yet run
  end to end as a live exercise.

Generated runtime artifacts and logs are under ignored `output/` and
`test_log/` paths. They are local evidence, not files intended for commit.

## S2 Boundary

Do not run S2 on the current host unless explicitly preparing it first. The
previous local S2 attempt exhausted host neighbor/ARP capacity. Current S2
runtime commands are guarded by:

- `B51_ALLOW_S2_RUNTIME=1`
- `gc_thresh1>=4096`
- `gc_thresh2>=8192`
- `gc_thresh3>=65536`

Without those conditions, `s2-preflight` remains the only safe S2 command. It
does not start containers.

## Closeout Criteria

Before treating this case as closed for handoff:

- `bash -n b51ctl.sh` passes.
- Python files compile.
- JSON metadata/policy/scoring files parse.
- `tests/internet/meta_style_cascade/exercise_static.sh` passes.
- `b51ctl.sh s2-preflight` confirms S2 is blocked rather than accidentally
  accepted on an unprepared host.
- `git add -n` shows only source/docs/tests, not `output/`, `test_log/`, or
  input goal-pack material.

After those checks, the remaining work is not to keep expanding this case. The
next benchmark case should start from this structure, but should not inherit
Meta-specific constants, ASNs, domain names, or root-cause logic blindly.
