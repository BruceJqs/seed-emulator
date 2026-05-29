# Hackathon Project Sandbox

This track asks a practical question: can an agent take an arbitrary student or
hackathon project and make it run inside a controlled SEED network?

This is not just deployment convenience. It creates a realistic path from
"someone gave me a project" to a repeatable networked experiment with probes,
constraints, logs, and scoring.

## Problem Definition

Input:

- a Git repository or archive
- possibly incomplete README
- Dockerfile, Compose file, npm/python/go project, or mixed stack
- optional database, object store, model server, API keys, background worker

Agent output:

- a runnable SEED scenario
- generated or repaired container build instructions
- service bindings and network placement
- health checks and user probes
- minimal patch summary
- replayable runbook

## Why SEED Is Better Than Plain Docker

Plain Docker answers "does the container start?" SEED can answer:

- can the project run behind DNS, mail, proxy, CDN, or BGP constraints?
- what happens when services are isolated by network policy?
- can multiple teams' projects coexist with realistic address and port planning?
- can the agent debug service dependencies from the outside, not only from
  inside the container?
- can the same project be used later in red/blue or incident tasks?

## Failure Modes To Encode

```yaml
deployment_failures:
  dockerfile:
    - missing system package
    - wrong working directory
    - build context too large
    - hardcoded localhost dependency
  compose:
    - port conflict
    - missing network
    - wrong service name
    - database not ready before app starts
  app:
    - missing environment variable
    - migration not run
    - static path wrong
    - file permission error
  runtime:
    - health check false positive
    - service binds 127.0.0.1 only
    - model/object-store dependency missing
    - resource limit hit
```

## Task Levels

### H1: Single-Service Project

- infer start command
- build image
- attach one host to one LAN
- expose one page/API
- verify with curl/page probe

### H2: Multi-Service Compose Project

- detect app, DB, cache, worker
- translate service dependencies into SEED nodes or services
- handle migrations and health checks
- verify API + DB-backed behavior

### H3: Networked Project

- add DNS names
- place frontend/backend/database on separate networks
- enforce client-only entrypoint
- verify internal-only services are not exposed

### H4: Broken Project

- project intentionally has one defect
- agent must patch minimally
- scorer checks that the project runs and unrelated files are not churned

### H5: Competition Sandbox

- multiple projects run in isolated team ASes
- shared scoreboard and traffic generator
- fixed resource and network policies
- per-team agent can repair only its own area

## Package Contract

```yaml
scenario:
  id: sandbox.compose_db_migration.v1
  input_repo: ./projects/sample-ticket-app
  allowed_edits:
    - Dockerfile
    - docker-compose.yml
    - seed_scenario.py
    - .env.example
  forbidden_edits:
    - app business logic except declared bug fix
  required_probes:
    - build succeeds
    - app HTTP 200
    - DB-backed create/read flow succeeds
    - logs contain no fatal migration error
  score:
    deployment_success: 35
    functional_probe: 25
    minimal_edits: 15
    explanation: 10
    reproducibility: 10
    safety: 5
```

## First Runnable Demo

Use a tiny intentionally imperfect web app:

- Flask or Node API
- Postgres or MariaDB
- one migration step
- one frontend page
- one missing environment variable in the initial repo

Agent task:

```text
Deploy this project into SEED. Do not expose the database publicly.
Fix only what is required to make /health and /tickets pass.
Give build, run, curl, log, and rollback evidence.
```

Oracle:

- container images built
- app can resolve DB by service name
- database is not published to host
- `/health` returns ok
- create/read probe passes
- patch touches only allowed files

## Implementation Notes

Do not build a large SDK first. Add a thin scenario adapter:

```text
project import -> service graph -> SEED nodes/services -> compiler output -> probes
```

The adapter should emit normal SEED Python or existing Service/Binding calls so
it does not bypass core abstractions.
