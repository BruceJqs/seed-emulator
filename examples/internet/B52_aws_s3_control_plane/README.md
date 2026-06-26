# B52 AWS S3 Control Plane

Independent SEED Agent Benchmark case skeleton for the S3-style control-plane capacity incident.

Commands:

```sh
bash b52ctl.sh generate-runtime S0
bash b52ctl.sh up-runtime S0
bash b52ctl.sh normal-runtime S0
bash b52ctl.sh inject-fault-runtime S0
bash b52ctl.sh fault-runtime S0
bash b52ctl.sh exercise-init-runtime S0
bash b52ctl.sh exercise-observe-runtime S0 public-users
bash b52ctl.sh exercise-action-runtime S0 mitigate
bash b52ctl.sh recovery-runtime S0
bash b52ctl.sh collect-runtime S0
bash b52ctl.sh down-runtime S0
```

Current status: S1.5 live accepted with 182 containers, public clients, a router-hosted S3 API frontend, five index subsystem containers, three placement subsystem containers, object-shard health contrast, maintenance tool, capacity registry, status dashboard, policy guard, and the full exercise ledger. The runtime validates maintenance-driven index/placement capacity removal, user-visible API 503, object shard still healthy, ordered recovery state, canary evidence, and restored subsystem containers; a real S3 storage engine remains out of scope.

Showcase panel:

```sh
bash b52ctl.sh panel-snapshot-runtime S1.5
bash b52ctl.sh panel-runtime S1.5 8520
```

Open `http://127.0.0.1:8520/` for the read-only incident panel. The snapshot is written to `test_log/runtime/S1_5/showcase_panel/index.html`.
