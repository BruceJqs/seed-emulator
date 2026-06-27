#!/bin/sh
set -eu

# Run this inside the attacker container. Defaults:
# - victim: AS151 host_0, 10.151.0.71
# - vulnerable directed-broadcast LAN: AS152, 10.152.0.255
python3 /opt/smurf-lab/smurf_attack.py "$@"
