# Y11: Smurf and Fraggle Attacks

This example recreates the core mechanism of the historical Smurf attack inside
a controlled SEED Emulator lab. It also includes the closely related Fraggle
attack, which uses UDP broadcast replies instead of ICMP echo replies.

The example uses the mini-Internet topology from
`examples/internet/B00_mini_internet`. It then turns AS152 into a vulnerable
directed-broadcast network with many hosts. The attacker sends ICMP echo
requests to AS152's directed broadcast address while spoofing the victim's
source IP address. Hosts on the AS152 LAN respond to the victim, amplifying the
attacker's traffic.

The Fraggle variant uses the same topology and directed-broadcast behavior, but
the attacker sends spoofed UDP packets to the AS152 directed broadcast address.
Each AS152 host runs a bounded UDP chargen-like lab daemon and sends a UDP
reply to the spoofed victim address.

## Roles

- AS150 `host_0`: attacker.
- AS151 `host_0`: victim.
- AS152 `router0`: vulnerable router with directed broadcast forwarding enabled.
- AS152 `host_0` ... `host_N`: amplifier hosts that respond to broadcast pings
  and run the UDP Fraggle amplifier daemon.

The default directed broadcast address is:

```text
10.152.0.255
```

The default spoofed victim address is:

```text
10.151.0.71
```

The default Fraggle UDP service port is:

```text
19
```

The default victim-side UDP reply port is:

```text
7000
```

## How The Attack Is Enabled

A Smurf attack needs three technical conditions. Modern networks usually break
at least one of them; this example deliberately enables all three inside the
emulator.

First, the attacker must be able to send an ICMP echo request with a spoofed
source address. In this example, AS150 runs:

```text
/opt/smurf-lab/smurf_attack.py
```

This script opens a raw socket and builds an IPv4 packet manually. The packet's
source address is set to the victim, `10.151.0.71`, while the destination is the
AS152 directed broadcast address, `10.152.0.255`.

Second, the router for the target LAN must forward directed broadcast packets.
Normally, routers no longer do this. Y11 enables it on AS152 `router0` using:

```sh
sysctl -w net.ipv4.ip_forward=1
sysctl -w net.ipv4.conf.all.bc_forwarding=1
sysctl -w net.ipv4.conf.default.bc_forwarding=1
```

The example also writes `1` to every existing interface-specific
`bc_forwarding` file under:

```text
/proc/sys/net/ipv4/conf/*/bc_forwarding
```

This makes AS152 `router0` forward a packet addressed to `10.152.0.255` onto
the AS152 LAN as a broadcast.

Third, hosts on the target LAN must answer broadcast ICMP echo requests.
Modern Linux hosts normally ignore these requests. Y11 changes this behavior on
the AS152 amplifier hosts with:

```sh
sysctl -w net.ipv4.icmp_echo_ignore_broadcasts=0
```

For Smurf, when the spoofed packet reaches the AS152 LAN, many AS152 hosts receive the
same broadcast echo request. Each host sends an ICMP echo reply to the spoofed
source address, so the replies go to AS151 `host_0`, the victim.

For Fraggle, each AS152 host also runs:

```text
/opt/smurf-lab/fraggle_amplifier.py
```

This is a small lab-only UDP daemon. It listens on UDP port `19`, accepts lab
traffic from `10.*` addresses, and sends a bounded chargen-like response back
to the packet source. When the attacker spoofs the source address as the
victim, all amplifier replies go to AS151 `host_0`.

The amplification factor depends mainly on the number of AS152 hosts. If
`--target-hosts 30` is used, one spoofed broadcast request can produce replies
from many of those 30 hosts.

The runtime test uses:

```text
/opt/smurf-lab/smurf_monitor.py
```

on the victim to count ICMP echo replies from the AS152 prefix.

It also uses:

```text
/opt/smurf-lab/fraggle_monitor.py
```

to count UDP replies sent by the Fraggle amplifier hosts.

## Visualizing The Attack

The best way to see the amplification effect is from the victim's point of view. Y11
installs a live dashboard on AS151 `host_0`:

```text
/opt/smurf-lab/visualize_attack.py
```

Start the dashboard on the victim first:

```sh
docker compose -f output/docker-compose.yml exec hnode_151_host_0 \
  /opt/smurf-lab/visualize_attack.py --duration 20 --request-count 3
```

In another terminal, trigger the attack from AS150:

```sh
docker compose -f output/docker-compose.yml exec hnode_150_host_0 \
  /opt/smurf-lab/trigger_attack.sh --count 3
```

For Fraggle, start the UDP dashboard on the victim:

```sh
docker compose -f output/docker-compose.yml exec hnode_151_host_0 \
  /opt/smurf-lab/visualize_attack.py --mode fraggle --duration 20 --request-count 3
```

Then trigger the UDP broadcast attack from AS150:

```sh
docker compose -f output/docker-compose.yml exec hnode_150_host_0 \
  /opt/smurf-lab/trigger_attack.sh --mode fraggle --count 3
```

The dashboard shows the attack as amplification:

```text
SMURF ATTACK MONITOR
====================
Victim view: ICMP echo replies from 10.152.0.*

elapsed seconds        : 4.0
spoofed requests       : 3
ICMP replies received  : 36
unique amplifier hosts : 12
estimated amplification: 12.0x
replies in last window : 0

Top replying hosts
------------------
10.152.0.71          3 replies
10.152.0.72          3 replies
10.152.0.73          3 replies
```

Internet Map is still useful for seeing packets move through the topology, but
the victim dashboard makes the key lesson clearer: a small number of spoofed
requests can cause many hosts to send replies to the victim.

## Build

From the repository root:

```sh
python examples/yesterday_once_more/Y11_smurf_attack/smurf_attack_example.py --platform amd
```

To change the number of amplifier hosts on the AS152 LAN:

```sh
python examples/yesterday_once_more/Y11_smurf_attack/smurf_attack_example.py \
  --platform amd \
  --target-hosts 30
```

The generated Docker files are placed in:

```text
examples/yesterday_once_more/Y11_smurf_attack/output
```

## Manual Attack Trigger

After starting the emulator, run the attack trigger from AS150:

```sh
docker compose -f output/docker-compose.yml exec hnode_150_host_0 \
  /opt/smurf-lab/trigger_attack.sh --count 3
```

To run the Fraggle variant:

```sh
docker compose -f output/docker-compose.yml exec hnode_150_host_0 \
  /opt/smurf-lab/trigger_attack.sh --mode fraggle --count 3
```

To observe victim-side replies, start the monitor on AS151 before triggering the
attack. For a live dashboard, use:

```sh
docker compose -f output/docker-compose.yml exec hnode_151_host_0 \
  /opt/smurf-lab/visualize_attack.py --duration 20 --request-count 3
```

For the Fraggle dashboard:

```sh
docker compose -f output/docker-compose.yml exec hnode_151_host_0 \
  /opt/smurf-lab/visualize_attack.py --mode fraggle --duration 20 --request-count 3
```

For a compact JSON summary, use:

```sh
docker compose -f output/docker-compose.yml exec hnode_151_host_0 \
  sh -lc 'python3 /opt/smurf-lab/smurf_monitor.py --duration 10'
```

For the Fraggle JSON summary:

```sh
docker compose -f output/docker-compose.yml exec hnode_151_host_0 \
  sh -lc 'python3 /opt/smurf-lab/fraggle_monitor.py --duration 10 --port 7000'
```

## Standard Test Runner

This example follows the `examples/sample` pattern:

```sh
python seedemu/testing/cli.py all examples/yesterday_once_more/Y11_smurf_attack/example.yaml \
  --artifact-dir ci-artifacts/y11-smurf-attack
```

The runtime test verifies:

- the directed-broadcast router and amplifier hosts are generated;
- AS152 router has `bc_forwarding` enabled;
- AS152 hosts respond to broadcast ICMP echo requests;
- the victim receives multiple ICMP echo replies after the attacker sends
  spoofed echo requests to `10.152.0.255`.
- AS152 hosts run the bounded UDP Fraggle amplifier daemon;
- the victim receives multiple UDP replies after the attacker sends spoofed UDP
  requests to `10.152.0.255:19`.

## Safety

Run this only inside an isolated emulator. The example deliberately recreates an
unsafe historical router behavior that modern routers normally disable. The
Fraggle UDP service is a lab daemon with bounded response size and lab-prefix
filtering; it is not intended to be exposed outside the emulator.
