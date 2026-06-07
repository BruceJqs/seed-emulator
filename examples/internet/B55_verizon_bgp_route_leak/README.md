# B55 Verizon BGP Route Leak

Independent live SEED Agent Benchmark case for a Verizon/DQE/Allegheny-style more-specific route leak.

The mechanism is network-level: the victim service stays healthy, normal probes use the victim aggregate `10.55.0.0/24`, and fault injection enables a DQE export session so `10.55.0.0/25` propagates through Allegheny and Verizon to unfiltered access networks.

Commands:

```sh
bash b55ctl.sh generate-runtime S0
bash b55ctl.sh up-runtime S0
bash b55ctl.sh normal-runtime S0
bash b55ctl.sh inject-fault-runtime S0
bash b55ctl.sh fault-runtime S0
bash b55ctl.sh exercise-init-runtime S0
bash b55ctl.sh exercise-observe-runtime S0 route-collectors
bash b55ctl.sh exercise-action-runtime S0 withdraw-leak
bash b55ctl.sh recovery-runtime S0
bash b55ctl.sh collect-runtime S0
bash b55ctl.sh down-runtime S0
```

S1.5 is live accepted with 177 containers and the full incident exercise ledger. S2 is guarded by `s2-preflight` and must not be started on an unprepared host.
