# B54 Cloudflare Feature File Proxy

Independent SEED Agent Benchmark case skeleton for a bad internally generated feature file propagating into a core proxy path.

Commands use `b54ctl.sh` with the common runtime surface:

```sh
bash b54ctl.sh generate-runtime S0
bash b54ctl.sh up-runtime S0
bash b54ctl.sh normal-runtime S0
bash b54ctl.sh inject-fault-runtime S0
bash b54ctl.sh fault-runtime S0
bash b54ctl.sh exercise-observe-runtime S0 control-plane
bash b54ctl.sh exercise-action-runtime S0 mitigate
bash b54ctl.sh recovery-runtime S0
bash b54ctl.sh collect-runtime S0
bash b54ctl.sh down-runtime S0
```

Current status: S1.5 live accepted with 191 containers, a case-local feature-file control plane, 8 core-proxy POP containers, KV/Access/Turnstile/dashboard tail services, 3 customer origins, policy guard, controlled known-good rollback, and the full exercise ledger. The runtime validates DB permission rollout, runaway feature generation, bad feature count/size/hash, global distribution, core proxy 5xx, origin-health contrast, fail-small rollback, canary, and tail-service validation. It is not a full Cloudflare proxy or Bot Management implementation.

Showcase panel:

```sh
bash b54ctl.sh panel-snapshot-runtime S1.5
bash b54ctl.sh panel-runtime S1.5 8540
```

Open `http://127.0.0.1:8540/` for the read-only incident panel. The snapshot is written to `test_log/runtime/S1_5/showcase_panel/index.html`.
