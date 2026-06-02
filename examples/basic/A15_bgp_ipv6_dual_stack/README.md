# A15: IPv6 Dual-Stack BGP Control Plane

This example mirrors the mixed BIRD/FRR control-plane shape from A12, but enables optional IPv6 addressing from `Base(enableIpv6=True)`. It is a validation scenario for the simulator-level IPv6 design, not the boundary of IPv6 support.

What it proves:

- Docker networks are generated as dual-stack networks with IPv6 IPAM.
- BIRD and FRR routers receive both IPv4 and IPv6 addresses on the same topology.
- OSPFv2 and OSPFv3 coexist for internal routing.
- eBGP and iBGP sessions are rendered from the same protocol intent for IPv4 and IPv6.

Run:

```bash
PYTHONPATH=. python3 examples/basic/A15_bgp_ipv6_dual_stack/bgp_ipv6_dual_stack.py
cd examples/basic/A15_bgp_ipv6_dual_stack/output
COMPOSE_PROJECT_NAME=seed_a15_ipv6 docker-compose up -d --build
```

Checks:

```bash
FRR_AS2=$(docker ps --format '{{.Names}}' | grep 'as2.*r2')
FRR_AS151=$(docker ps --format '{{.Names}}' | grep 'as151.*router0')
BIRD_AS2=$(docker ps --format '{{.Names}}' | grep 'as2.*r1')
BIRD_AS152=$(docker ps --format '{{.Names}}' | grep 'as152.*router0')

docker exec "$FRR_AS2" ip -6 addr
docker exec "$FRR_AS2" vtysh -c 'show bgp ipv6 unicast summary' -c 'show ipv6 ospf6 neighbor' -c 'show bgp ipv6 unicast'
docker exec "$FRR_AS151" vtysh -c 'show bgp ipv6 unicast' -c 'show ipv6 route bgp'
docker exec "$BIRD_AS2" birdc show protocols
docker exec "$BIRD_AS2" birdc show route all
docker exec "$BIRD_AS152" birdc show route all
```

Cleanup:

```bash
COMPOSE_PROJECT_NAME=seed_a15_ipv6 docker-compose down -v
```
