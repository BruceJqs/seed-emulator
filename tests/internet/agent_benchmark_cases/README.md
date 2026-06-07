# Agent Benchmark Cases 02-07 Tests

`static_contract.sh` checks controller command contracts, policy-denied shortcuts, and exercise ledger behavior.

`generate_smoke.sh` regenerates S0 Docker outputs for B52-B57 and checks that the B55/B56 control scripts are present in generated artifacts.

The static contract also rejects CJK text in benchmark source documentation, configs, and tests so that newly added user-facing material stays English-only.

These tests are not S1.5 runtime acceptance. Live acceptance still requires starting the generated Docker project, running normal/fault/recovery/exercise/collect/down, and checking residual cleanup.
