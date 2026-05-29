# A12 BGP Mixed Backend

`A12` demonstrates mixed BGP control planes inside one SEED topology.

The network keeps the default BIRD backend on some routers and creates selected
routers with `routingBackend="frr"`.

## What it proves

- BIRD and FRRouting can coexist in one emulated network.
- Selected routers can run FRR for BGP/OSPF while neighboring routers still use BIRD.
- The control-plane tooling can inspect both backends in one runtime.

## Topology

- `AS2` is a transit provider with two internal routers: `r1` and `r2`
- `AS151` and `AS152` are customer ASes
- `AS2/r2` and `AS151/router0` run FRRouting for BGP
- `AS2/r1` and `AS152/router0` stay on BIRD
- `AS2/r1` peers with `AS151/router0` at `ix100`
- `AS2/r2` peers with `AS152/router0` at `ix101`

## Build

```bash
PYTHONPATH=. python3 examples/basic/A12_bgp_mixed_backend/bgp_mixed_backend.py
cd examples/basic/A12_bgp_mixed_backend/output
DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 COMPOSE_PROJECT_NAME=a12 docker-compose build
COMPOSE_PROJECT_NAME=a12 docker-compose up -d
```

## Runtime checks

```bash
dockps | grep -E 'as2|as151|as152'
FRR_AS2=$(docker ps --format '{{.Names}}' | grep 'as2.*r2')
FRR_AS151=$(docker ps --format '{{.Names}}' | grep 'as151.*router0')
BIRD_AS2=$(docker ps --format '{{.Names}}' | grep 'as2.*r1')
BIRD_AS152=$(docker ps --format '{{.Names}}' | grep 'as152.*router0')
docker exec "$FRR_AS2" sh -lc 'test -f /etc/frr/frr.conf && ! pgrep bird && sed -n "1,220p" /etc/frr/frr.conf'
docker exec "$FRR_AS151" sh -lc 'test -f /etc/frr/frr.conf && ! pgrep bird && sed -n "1,220p" /etc/frr/frr.conf'
docker exec "$BIRD_AS2" sh -lc 'test -f /etc/bird/bird.conf && sed -n "1,220p" /etc/bird/bird.conf'
docker exec "$FRR_AS2" vtysh -c 'show bgp summary' -c 'show ip ospf neighbor' -c 'show bgp ipv4 unicast'
docker exec "$FRR_AS151" vtysh -c 'show bgp summary' -c 'show ip route bgp'
docker exec "$BIRD_AS2" birdc show protocols
docker exec "$BIRD_AS2" birdc show route all
docker exec "$BIRD_AS152" birdc show protocols
docker exec "$BIRD_AS152" birdc show route all
curl --noproxy '*' http://127.0.0.1:8080/pro/home
```

The route output should show that mixed BIRD/FRR routers exchange customer
prefixes through normal BGP. Check the next hop, AS path, large communities, and
local preference in the route details; those attributes prove that the backend
renderer is preserving SEED route-policy intent, not only starting a daemon.

The exact container names are generated in `output/docker-compose.yml`.
