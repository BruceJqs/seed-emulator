# S1.5 Interactive Incident Exercise Design

This document defines the real S1.5 test for B51. It is not a scripted result
demo and not a one-command smoke pass. The test is a live incident exercise
where humans and agents use role-scoped observations, staged notes, restricted
actions, and phase gates to move from symptoms to mitigation and validation.

S1.5 is the current target because it is the largest live tier validated on this
host: 225 SEED network containers, 80 probe ASes, and 16 route collectors. S2 is
not part of this exercise until it passes host preflight and runtime acceptance.

## Test Meaning

The exercise is accepted only when all of these are true:

- the S1.5 Docker topology is live and passes the container-count gate;
- operators collect baseline evidence before the fault;
- after fault injection, operators observe user, resolver, and routing symptoms
  before opening internal change evidence;
- operators record hypotheses and rejected shortcuts in the exercise ledger;
- the mitigation uses only the allowed internal-policy rollback path;
- health-gated reannouncement restores public reachability;
- recovery is validated from public users, route collectors, and Meta edge
  health, not only from one internal command.

The exercise can fail even if final recovery succeeds. It fails if the ledger
skips the staged evidence chain, reveals the root cause too early, uses a
forbidden shortcut, or cannot prove recovery externally.

## Runtime Roles

| Role | View | Allowed observations |
|---|---|---|
| public-users | AS50, AS51, AS99, AS132 probes | recursive DNS result and HTTP result only |
| resolver-support | AS50 resolver network | recursive query, direct authoritative query, resolver route to edge DNS, resolver daemon status |
| external-routing | AS133, AS140, AS148 collectors | BGP visibility of `10.20.0.0/24` |
| meta-noc | AS20 edge | health-gate status, edge-to-backend probe, health-gate timeline |
| meta-dns | AS20 edge DNS | named config/process/socket and local authoritative query |
| dc-team | AS30 backend | backend local service and DC-side routing |
| meta-neteng | AS20/AS30 routing | BIRD protocols, internal peer, external peer, route export |
| change-audit | AS20 change log | recent internal change log after escalation |

The `frontline` observation group collects public users, resolver support, and
external routing only. `all-roles` is for facilitator review or final evidence,
not for the first symptom stage.

## Phase Sequence

The recommended live sequence is below. The facilitator should not explain the
root cause before the operators have evidence for it.

1. `baseline`
   Collect `public-users`, `resolver-support`, `external-routing`, and
   `meta-noc`. Record a note that DNS, HTTP, route visibility, and health are
   normal.

2. `impact`
   The facilitator runs `exercise-action-runtime S1.5 inject-fault`. Operators
   collect `public-users` and record the first impact note. At this point the
   only justified statement is that users see DNS/HTTP failure.

3. `resolver-triage`
   Collect `resolver-support`. Distinguish recursive resolver symptoms from
   authoritative DNS service health. Do not assume the DNS daemon is dead.

4. `external-routing`
   Collect route collector observations. If collectors no longer see
   `10.20.0.0/24`, the investigation can move toward BGP/control-plane
   reachability instead of single-user or single-resolver failure.

5. `meta-triage`
   Collect `meta-noc`, `meta-dns`, and `dc-team`. This stage separates three
   hypotheses: DNS process failure, backend service failure, and edge-to-backend
   dependency failure.

6. `neteng-triage`
   Collect `meta-neteng`. Use BIRD protocol and route-export evidence to decide
   whether the public prefix withdrawal is health-gate driven and whether the
   internal path is involved.

7. `change-audit`
   Collect `change-audit` only after the previous stages justify escalation.
   This is where the exercise may reveal the recent internal routing/policy
   change.

8. `mitigation`
   Record the operator decision. The only accepted first mitigation is
   `exercise-action-runtime S1.5 rollback-internal-policy`. The operator should
   explicitly reject DNS kills, zone edits, client hosts edits, oracle edits,
   forced unhealthy announcements, and global resets.

9. `recovery-verification`
   Run `verify-health`, `canary-reannounce`, and `validate-recovery`. Then
   collect `public-users`, `external-routing`, and `meta-noc` again. Recovery is
   not accepted until public DNS/HTTP, route visibility, and health-gate state
   all agree.

10. `postmortem`
    Review `events.tsv`, `notes.tsv`, observations, actions, and gate reports.
    The final explanation must connect the observed chain rather than cite the
    hidden fault label alone.

## Controller Surface

Use a unique compose project and exercise id:

```bash
cd examples/internet/B51_meta_style_cascade

export TIER=S1.5
export COMPOSE_PROJECT_NAME=seed_meta_cascade_s1_5_exercise
export B51_EXERCISE_ID=classroom-run-001
export PLATFORM=arm
export SEED_PYTHON=../../../.venv/bin/python
```

Generate and start the runtime, optionally with the Internet Map:

```bash
B51_ENABLE_INTERNET_MAP=1 B51_INTERNET_MAP_PORT=8080 bash b51ctl.sh generate-runtime S1.5
B51_ENABLE_INTERNET_MAP=1 B51_INTERNET_MAP_PORT=8080 bash b51ctl.sh up-runtime S1.5
bash b51ctl.sh exercise-init-runtime S1.5
```

Use the exercise commands during the incident:

```bash
bash b51ctl.sh exercise-phase-runtime S1.5 baseline
bash b51ctl.sh exercise-observe-runtime S1.5 public-users
bash b51ctl.sh exercise-observe-runtime S1.5 resolver-support
bash b51ctl.sh exercise-observe-runtime S1.5 external-routing
bash b51ctl.sh exercise-observe-runtime S1.5 meta-noc
bash b51ctl.sh exercise-note-runtime S1.5 facilitator "baseline evidence collected"
bash b51ctl.sh exercise-gate-runtime S1.5 baseline
```

Fault and investigation:

```bash
bash b51ctl.sh exercise-phase-runtime S1.5 impact
bash b51ctl.sh exercise-action-runtime S1.5 inject-fault
bash b51ctl.sh exercise-observe-runtime S1.5 public-users
bash b51ctl.sh exercise-note-runtime S1.5 public-users "users report DNS and HTTP failure"

bash b51ctl.sh exercise-phase-runtime S1.5 resolver-triage
bash b51ctl.sh exercise-observe-runtime S1.5 resolver-support

bash b51ctl.sh exercise-phase-runtime S1.5 external-routing
bash b51ctl.sh exercise-observe-runtime S1.5 external-routing

bash b51ctl.sh exercise-phase-runtime S1.5 meta-triage
bash b51ctl.sh exercise-observe-runtime S1.5 meta-noc
bash b51ctl.sh exercise-observe-runtime S1.5 meta-dns
bash b51ctl.sh exercise-observe-runtime S1.5 dc-team

bash b51ctl.sh exercise-phase-runtime S1.5 neteng-triage
bash b51ctl.sh exercise-observe-runtime S1.5 meta-neteng

bash b51ctl.sh exercise-phase-runtime S1.5 change-audit
bash b51ctl.sh exercise-observe-runtime S1.5 change-audit
```

Mitigation and validation:

```bash
bash b51ctl.sh exercise-phase-runtime S1.5 mitigation
bash b51ctl.sh exercise-note-runtime S1.5 meta-neteng "rollback internal path policy; do not force public prefix"
bash b51ctl.sh exercise-action-runtime S1.5 rollback-internal-policy

bash b51ctl.sh exercise-phase-runtime S1.5 recovery-verification
bash b51ctl.sh exercise-action-runtime S1.5 verify-health
bash b51ctl.sh exercise-action-runtime S1.5 canary-reannounce
bash b51ctl.sh exercise-action-runtime S1.5 validate-recovery
bash b51ctl.sh exercise-observe-runtime S1.5 public-users
bash b51ctl.sh exercise-observe-runtime S1.5 external-routing
bash b51ctl.sh exercise-observe-runtime S1.5 meta-noc
bash b51ctl.sh exercise-gate-runtime S1.5 recovery-verification
```

The ledger is written under:

```text
test_log/runtime/S1_5/exercise/<B51_EXERCISE_ID>/
```

Key files:

- `state.env`: current phase and exercise metadata.
- `events.tsv`: phase, observation, action, and gate timeline.
- `notes.tsv`: human/agent hypothesis and decision notes.
- `observations/`: role-scoped evidence snapshots.
- `actions/`: restricted action outputs and result codes.
- `gates/`: phase evidence checks.

## Phase Gates

`exercise-gate` is intentionally shallow. It checks the exercise ledger, not the
hidden truth. A gate can pass only if the right classes of evidence exist.

| Gate | Required ledger evidence |
|---|---|
| baseline | public users, resolver support, external routing, Meta NOC |
| impact | public user observation and note |
| resolver-triage | public user and resolver support observations plus note |
| external-routing | resolver support and external routing observations plus note |
| meta-triage | external routing, Meta NOC, Meta DNS, DC team observations plus note |
| neteng-triage | Meta NOC, Meta DNS, DC team, Meta neteng observations plus note |
| change-audit | Meta neteng and change-audit observations plus note |
| mitigation | all major role observations plus note |
| recovery-verification | public users, external routing, Meta NOC, and successful recovery actions |
| postmortem | all major role observations, recovery actions, and notes |

These gates make the exercise auditable. They do not replace `normal-runtime`,
`fault-runtime`, or `recovery-runtime`; those are still live data-plane and
control-plane checks.

## Plausible Wrong Hypotheses

The exercise should create room for wrong but plausible hypotheses:

- recursive resolver failure: checked by resolver process status and direct
  authoritative query;
- authoritative DNS daemon failure: checked by named process/socket/config and
  local authoritative query;
- DNS zone corruption: rejected because local authoritative data remains intact;
- backend application crash: checked by DC-side backend local service;
- single client or single region problem: rejected by multiple probes and route
  collectors;
- public transit-only failure: checked against Meta edge health, route export,
  and internal path evidence;
- forced BGP reannouncement as a fix: rejected because the health gate is
  intentionally withholding public reachability while the backend dependency is
  unhealthy.

## Forbidden Shortcuts

The controller policy rejects these shortcuts:

- killing or stopping DNS;
- deleting or editing DNS zones;
- editing client hosts files;
- editing hidden oracle or scoring truth;
- force-announcing an unhealthy prefix;
- disabling the health gate;
- unrelated global resets.

Those actions may be attempted during training to show policy denial, but they
must not be used as recovery.

## Internet Map Use

The Internet Map is useful for the live classroom view. It shows that the
exercise is not a single-host toy and helps the facilitator point to AS20,
AS30, AS50, route collectors, probes, IX100, and IX101.

The map is not accepted as evidence by itself. Evidence must still come from
role observations and runtime checks.

## S2 Boundary

Do not run S2 as part of this exercise on the current host. A previous local
S2-scale attempt exhausted host neighbor/ARP capacity. `s2-preflight` is safe
because it is diagnostic-only and does not start containers.

S2 can become an exercise target only after host or distributed runtime limits
are prepared and the tier passes the same live container, normal, fault,
mitigation, and recovery checks.
