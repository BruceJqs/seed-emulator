# Y10: NTP-Like Amplification

This example recreates the core idea behind historical NTP amplification
incidents inside a controlled SEED Emulator lab. It uses the mini-Internet
topology from `examples/internet/B00_mini_internet`, then adds a few vulnerable
NTP-like UDP services.

The service is intentionally not a real NTP daemon. It is a small Python program
that accepts a tiny monitor-style request and returns a much larger response.
This makes the amplification mechanism clear and avoids depending on obsolete
NTP packages.

## Topology

The base topology is B00. Y10 adds these roles:

- AS150 `host_0`: attacker host, with `/opt/ntp-like/trigger_attack.py`.
- AS151 `host_0`: victim host, with a UDP sink on port `9000`.
- AS152 `host_0`: NTP-like amplifier.
- AS160 `host_0`: NTP-like amplifier.
- AS171 `host_0`: NTP-like amplifier.

The amplifier daemon listens on UDP port `123`. A direct `monlist` request is
answered by the amplifier itself. The example also enables a lab-only reflection
simulation command so the attacker can make the amplifiers send their larger
responses to the victim without using raw source-IP spoofing.

## Visualizing The Attack

The clearest way to see the attack is from the victim's point of view. Y10
installs a live UDP amplification dashboard on AS151 `host_0`:

```text
/opt/ntp-like/visualize_attack.py
```

Start the dashboard on the victim first:

```sh
docker compose -f output/docker-compose.yml exec hnode_151_host_0 \
  /opt/ntp-like/visualize_attack.py --duration 20 --expected-requests 3
```

In another terminal, trigger the attack from AS150:

```sh
docker compose -f output/docker-compose.yml exec hnode_150_host_0 \
  /opt/ntp-like/trigger_attack.sh
```

The dashboard focuses on byte amplification:

```text
NTP-LIKE AMPLIFICATION MONITOR
==============================
Victim view: UDP responses from lab amplifiers

elapsed seconds           : 4.0
expected trigger requests : 3
estimated request bytes   : 108
UDP packets received      : 3
total response bytes      : 3600
unique amplifiers         : 3
estimated byte amp        : 33.3x
packets in last window    : 0
bytes in last window      : 0

Top amplifiers
--------------
10.152.0.71          1 packets     1200 bytes
10.160.0.71          1 packets     1200 bytes
10.171.0.71          1 packets     1200 bytes
```

Internet Map can show packet movement through the topology, but this dashboard
shows the essential effect more directly: small trigger requests cause much
larger UDP responses to arrive at the victim.

## Build

From the repository root:

```sh
python examples/yesterday_once_more/Y10_ntp_amplification/ntp_amplification.py --platform amd
```

The generated Docker files are placed in:

```text
examples/yesterday_once_more/Y10_ntp_amplification/output
```

## Manual Attack Trigger

After starting the emulator, run the trigger from the attacker container:

```sh
docker compose -f output/docker-compose.yml exec hnode_150_host_0 \
  /opt/ntp-like/trigger_attack.sh
```

The default victim is `10.151.0.71:9000`. The default amplifiers are:

```text
10.152.0.71
10.160.0.71
10.171.0.71
```

To run direct queries instead of reflection simulation:

```sh
docker compose -f output/docker-compose.yml exec hnode_150_host_0 \
  /opt/ntp-like/trigger_attack.py --json
```

To inspect victim-side traffic:

```sh
docker compose -f output/docker-compose.yml exec hnode_151_host_0 \
  tail -n 20 /var/log/ntp-like-victim.log
```

For a live victim-side dashboard instead of raw logs:

```sh
docker compose -f output/docker-compose.yml exec hnode_151_host_0 \
  /opt/ntp-like/visualize_attack.py --duration 20 --expected-requests 3
```

## Standard Test Runner

This example follows the `examples/sample` pattern:

```sh
python seedemu/testing/cli.py all examples/yesterday_once_more/Y10_ntp_amplification/example.yaml \
  --artifact-dir ci-artifacts/y10-ntp-amplification
```

The manifest checks that representative B00 services are running and that the
attacker can reach the victim and one amplifier. The custom runtime test checks:

- the attacker, victim, and amplifier containers exist;
- the NTP-like daemons are running;
- direct queries produce amplified responses;
- the reflection simulation causes the victim UDP sink to receive traffic.

## Safety

Run this only inside an isolated emulator. The daemon has an allowlist and the
reflection simulation is token-gated, but it is still intentionally modeling a
dangerous class of UDP amplification behavior.
