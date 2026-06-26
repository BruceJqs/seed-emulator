# B57 Google Network Congestion

Independent SEED Agent Benchmark case for maintenance automation descheduling network control-plane jobs.

Commands use `b57ctl.sh` with the common runtime surface:

```sh
bash b57ctl.sh generate-runtime S0
bash b57ctl.sh up-runtime S0
bash b57ctl.sh normal-runtime S0
bash b57ctl.sh inject-fault-runtime S0
bash b57ctl.sh fault-runtime S0
bash b57ctl.sh exercise-observe-runtime S0 network-ops
bash b57ctl.sh exercise-action-runtime S0 restore-control-plane
bash b57ctl.sh recovery-runtime S0
bash b57ctl.sh collect-runtime S0
bash b57ctl.sh down-runtime S0
```

Current status: S1.5 live accepted with 194 containers, a case-local Google-style network control plane, 8 region frontend containers, 6 workload containers, real edge BGP peer disable/enable for external route withdrawal/restoration, policy guard, and the full exercise ledger. The runtime validates automation deschedule state, missing control-plane jobs, fail-static expiration, withdrawn external route, external user curl `000`, local service/workload health, constrained recovery, route restoration, and region verification. It models congestion as controlled state and route reachability rather than full packet-level traffic engineering.

Showcase panel:

```sh
bash b57ctl.sh panel-snapshot-runtime S1.5
bash b57ctl.sh panel-runtime S1.5 8570
```

Open `http://127.0.0.1:8570/` for the read-only incident panel. The snapshot is written to `test_log/runtime/S1_5/showcase_panel/index.html`.
