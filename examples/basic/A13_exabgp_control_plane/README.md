# A13 ExaBGP Control Plane

`A13` adds ExaBGP into a SEED topology as a router backend.

The ExaBGP router joins the IX peering LAN directly, records BGP events, and
can announce or withdraw prefixes through `/run/exabgp/live.in`.

## What it proves

- ExaBGP can be selected with `createRouter(..., routingBackend="exabgp")`.
- The peer router keeps its normal BIRD backend while ExaBGP acts as an IX BGP speaker.
- The built-in dashboard exposes live ExaBGP JSON events over HTTP.

## Topology

- `AS2/router0` is the provider edge
- `AS180/exabgp` is an ExaBGP router on `ix100` at `10.100.0.180`
- `AS180/exabgp` announces `198.51.100.0/24` to `AS2/router0`

## Build

```bash
cd examples/basic/A13_exabgp_control_plane
PYTHONPATH=../.. python3 exabgp_control_plane.py
cd output
DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 COMPOSE_PROJECT_NAME=a13 docker-compose build
COMPOSE_PROJECT_NAME=a13 docker-compose up -d
```

## Runtime checks

```bash
EXA=$(docker ps --format '{{.Names}}' | grep 'as180.*exabgp')
R2=$(docker ps --format '{{.Names}}' | grep 'as2.*router0')
docker exec "$EXA" sh -lc 'ps aux | grep -E "exabgp|dashboard|live_control" | grep -v grep'
docker exec "$EXA" sh -lc 'test -f /etc/exabgp/exabgp.conf && sed -n "1,180p" /etc/exabgp/exabgp.conf'
docker exec "$EXA" sh -lc 'test -p /run/exabgp/live.in && tail -n 40 /var/log/exabgp/exabgp.log'
docker exec "$R2" birdc show protocols
docker exec "$R2" birdc show route for 198.51.100.1 all
docker exec "$EXA" sh -lc "printf '%s\n' 'announce route 203.2.3.0/24 next-hop self' > /run/exabgp/live.in"
docker exec "$R2" birdc show route for 203.2.3.1 all
docker exec "$EXA" sh -lc "printf '%s\n' 'withdraw route 203.2.3.0/24 next-hop self' > /run/exabgp/live.in"
```

The ExaBGP dashboard is available at `http://localhost:5001/`.
