# Email Service Design

This document describes the B29 email scenario and the current `EmailService`
implementation boundary. B29 combines SEED routing, DNS, real mail daemons, and
an optional webmail frontend into a deterministic end-to-end application
scenario.

## Design Position

B29 is an application-service scenario built on top of the existing SEED layer
model:

- `Base`, `Routing`, `Ebgp`, `Ibgp`, and `Ospf` build the AS, IX, and routing
  substrate.
- `DomainNameService` creates root, TLD, and authoritative zones with real A and
  MX records.
- `DomainNameCachingService` gives each provider AS a local DNS cache.
- `EmailService` records mail providers and attaches real
  `mailserver/docker-mailserver` containers to the compiled Docker topology.
- `docker-compose-roundcube.yml` adds Roundcube as an external webmail frontend
  for interactive validation.

`EmailService` is currently a compiler helper rather than a standard
`Service + Binding` implementation. It keeps enough provider intent to generate
stable mailserver containers and support the B29 scenario, while the scenario
itself still owns DNS zone layout, AS topology, and provider peering policy.

## Core File Map

| Concern | File / entry point | Role |
| --- | --- | --- |
| Scenario topology | `examples/internet/B29_email_dns/email_realistic.py` | Builds ASes, IXes, DNS zones, local DNS caches, mail providers, and BGP peering. |
| Email helper | `seedemu/services/EmailService.py` | Records providers, writes mail wrapper artifacts, and attaches custom mail containers to Docker output. |
| Operator CLI | `examples/internet/B29_email_dns/b29ctl.sh` | Runs pre-checks, generation, compose startup, account setup, tests, and cleanup. |
| Roundcube helper | `examples/internet/B29_email_dns/manage_roundcube.sh` | Starts and stops the webmail frontend compose stack. |
| Cross-provider tests | `examples/internet/B29_email_dns/run_cross_tests.sh` | Sends tokenized mail flows and verifies recipient mailboxes. |
| Runtime compose | `examples/internet/B29_email_dns/docker-compose-roundcube.yml` | Defines Roundcube and database services outside the generated SEED compose file. |

## B29 Flow

```text
email_realistic.py
-> Base/Routing/Ebgp/Ibgp/Ospf build the routed Internet
-> DomainNameService writes authoritative A/MX records
-> DomainNameCachingService installs AS-local caches
-> EmailService.add_provider(...) records mail provider intent
-> EmailService.attach_to_docker(...) attaches custom mail containers
-> Docker compiler emits the runnable topology
-> b29ctl.sh start provisions accounts and starts Roundcube
-> run_cross_tests.sh validates DNS, SMTP, IMAP, and mailbox delivery
```

The important design point is that email success depends on multiple SEED
subsystems at once. A successful cross-domain delivery proves the data plane,
DNS/MX path, SMTP transport, recipient mailbox, and optional webmail access are
all coherent.

## Provider Model

Each provider entry contains:

- provider name and domain, such as `qq.com` or `gmail.com`.
- AS number and mail host IP.
- gateway and network attachment details for Docker.
- SMTP/IMAP ports and account data used by the validation scripts.
- DNS information consumed by the scenario when creating A and MX records.

B29 uses deterministic transport maps for classroom reliability. DNS/MX records
remain real runtime evidence, but Postfix transport rules keep cross-provider
next hops stable and avoid transient resolver timing from dominating the
demonstration.

## Validation Contract

The scenario is considered valid when:

- provider containers are attached to the expected AS networks.
- provider DNS caches resolve the mail domains and MX targets.
- mail providers can reach each other across AS boundaries.
- a generated message token appears in the intended recipient mailbox.
- sender logs show successful SMTP handoff and receiver logs show mailbox save.
- Roundcube can connect to the same provider accounts used by CLI validation.

The primary validation entry points are:

```bash
cd examples/internet/B29_email_dns
bash b29ctl.sh doctor
bash b29ctl.sh start
bash b29ctl.sh test
bash b29ctl.sh test --all
bash b29ctl.sh stop
```

## Design Boundaries

- Keep Internet topology, routing policy, and DNS zones in the scenario code.
- Keep mail provider intent and Docker mailserver attachment in `EmailService`.
- Keep account provisioning and runtime checks in operator scripts.
- Do not model B29 as an external-only demo; it should remain reproducible from
  the scenario source and generated Docker output.
- Do not present the current helper as the final service abstraction. A future
  mainline version should move provider installation toward standard
  `Service + Binding` semantics.

## Future Work

- Promote `EmailService` from compiler helper to standard `Service + Binding`.
- Make provider/domain/MX/mail-daemon policy explicit service intent.
- Add optional SPF, DKIM, DMARC, STARTTLS, MTA-STS, and DANE modes.
- Add structured SeedOps tools for MX trace, SMTP probe, IMAP probe, queue
  inspection, and delivery-log summarization.
