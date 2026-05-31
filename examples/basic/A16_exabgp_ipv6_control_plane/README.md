# A16: ExaBGP IPv6 Control Plane

This example keeps ExaBGP as a service installed through `ExaBgpService + Binding`. The service peers on the IX LAN and announces an IPv6 prefix to a BIRD router.

Run:

```bash
PYTHONPATH=. python3 examples/basic/A16_exabgp_ipv6_control_plane/exabgp_ipv6_control_plane.py
cd examples/basic/A16_exabgp_ipv6_control_plane/output
COMPOSE_PROJECT_NAME=seed_a16_exabgp_ipv6 docker compose up -d --build
```

Checks:

```bash
EXA=$(docker ps --format '{{.Names}}' | grep 'as180.*exabgp')
R2=$(docker ps --format '{{.Names}}' | grep 'as2.*router0')

docker exec "$EXA" sh -lc 'sed -n "1,220p" /etc/exabgp/exabgp.conf'
docker exec "$EXA" sh -lc 'test -p /run/exabgp/live.in && test -p /run/exabgp.in && test -p /run/exabgp.out'
docker exec "$R2" birdc show protocols
docker exec "$R2" birdc show route for 2000:b400:100::1 all

docker exec "$EXA" exabgpcli announce route 2000:b400:200::/64 next-hop self
sleep 3
docker exec "$R2" birdc show route for 2000:b400:200::1 all
docker exec "$EXA" exabgpcli withdraw route 2000:b400:200::/64 next-hop self

docker exec "$EXA" sh -lc "printf '%s\n' 'announce route 2000:b400:300::/64 next-hop self' > /run/exabgp/live.in"
sleep 3
docker exec "$R2" birdc show route for 2000:b400:300::1 all
docker exec "$EXA" sh -lc "printf '%s\n' 'withdraw route 2000:b400:300::/64 next-hop self' > /run/exabgp/live.in"
docker exec "$EXA" sh -lc 'tail -n 40 /var/log/exabgp/live-control.log; tail -n 40 /var/log/exabgp/events.jsonl'
```

Cleanup:

```bash
COMPOSE_PROJECT_NAME=seed_a16_exabgp_ipv6 docker compose down -v
```
