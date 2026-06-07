# B56 Dyn Authoritative DNS DDoS

Independent live SEED Agent Benchmark case for a Dyn-style authoritative DNS DDoS with cache and secondary-DNS contrast.

The mechanism does not kill DNS. Fault injection simulates an overloaded authoritative path for the Dyn-only domain. The customer origin remains healthy, the `named` process remains visible, and a secondary-provider domain is used as a control.

Commands:

```sh
bash b56ctl.sh generate-runtime S0
bash b56ctl.sh up-runtime S0
bash b56ctl.sh normal-runtime S0
bash b56ctl.sh inject-fault-runtime S0
bash b56ctl.sh fault-runtime S0
bash b56ctl.sh exercise-init-runtime S0
bash b56ctl.sh exercise-observe-runtime S0 resolvers
bash b56ctl.sh exercise-action-runtime S0 activate-scrubber
bash b56ctl.sh recovery-runtime S0
bash b56ctl.sh collect-runtime S0
bash b56ctl.sh down-runtime S0
```

S1.5 is live accepted with 178 containers and the full incident exercise ledger. S2 is guarded by `s2-preflight` and must not be started on an unprepared host.
