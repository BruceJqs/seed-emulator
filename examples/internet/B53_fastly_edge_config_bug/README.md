# B53 Fastly Edge Config Bug

Independent SEED Agent Benchmark case skeleton for a legal customer config triggering a latent edge runtime bug.

Commands use `b53ctl.sh` with the common runtime surface:

```sh
bash b53ctl.sh generate-runtime S0
bash b53ctl.sh up-runtime S0
bash b53ctl.sh normal-runtime S0
bash b53ctl.sh inject-fault-runtime S0
bash b53ctl.sh fault-runtime S0
bash b53ctl.sh exercise-observe-runtime S0 public-users
bash b53ctl.sh exercise-action-runtime S0 mitigate
bash b53ctl.sh recovery-runtime S0
bash b53ctl.sh collect-runtime S0
bash b53ctl.sh down-runtime S0
```

Current status: S1.5 live accepted with 186 containers, a case-local Fastly-style control plane, 8 edge POP containers, 3 customer origins, controlled rollback action, policy guard, and the full exercise ledger. The runtime validates legal trigger config acceptance, validator pass, compiler artifact v43, distributor propagation to 7/8 affected POPs, origin-health contrast, rollback, POP canary, full restore, and hotfix-note evidence. It is not a full CDN cache/runtime implementation.

Showcase panel:

```sh
bash b53ctl.sh panel-snapshot-runtime S1.5
bash b53ctl.sh panel-runtime S1.5 8530
```

Open `http://127.0.0.1:8530/` for the read-only incident panel. The snapshot is written to `test_log/runtime/S1_5/showcase_panel/index.html`.
