# A17: IPv6 Looking Glass

This example installs the classic Looking Glass frontend on an AS2 host and observes both a FRR router and an IX-facing BIRD router in a dual-stack topology.
The frontend talks to router-local proxy processes over the SEED service management network; route-state still comes from BIRD/FRR, and the ExaBGP event dashboard remains separate.

Run:

```bash
PYTHONPATH=. python3 examples/basic/A17_ipv6_looking_glass/ipv6_looking_glass.py
cd examples/basic/A17_ipv6_looking_glass/output
COMPOSE_PROJECT_NAME=seed_a17_lg_ipv6 docker-compose up -d --build
```

Checks:

```bash
LG=$(docker ps --format '{{.Names}}' | grep 'as2.*looking-glass')
FRR=$(docker ps --format '{{.Names}}' | grep 'as2.*router0')
BIRD=$(docker ps --format '{{.Names}}' | grep 'as151.*router0')

docker exec "$FRR" vtysh -c 'show bgp ipv6 unicast' -c 'show ipv6 ospf6 neighbor'
docker exec "$BIRD" birdc show protocols
docker exec "$BIRD" birdc show route all
docker exec "$LG" sh -lc 'wget -qO- http://127.0.0.1:5000/api/state | python3 -m json.tool'
```

The frontend is exposed on the host port from `SEED_A17_LG_PORT`, default `5017`.

Cleanup:

```bash
COMPOSE_PROJECT_NAME=seed_a17_lg_ipv6 docker-compose down -v
```
