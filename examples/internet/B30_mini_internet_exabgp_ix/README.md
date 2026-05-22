# Mini Internet ExaBGP IX Control Plane

This example extends `examples.internet.B00_mini_internet` with one additional
IX-connected control-plane router:

- `AS180` router `exabgp`
- IX: `ix100`
- IX address: `10.100.0.180`
- Local ASN: `180`
- Announcement: `203.0.113.0/24`
- Extra static announcement: `203.0.114.0/24`
- eBGP peers: `AS2/r100` and `AS3/r100`

The router runs ExaBGP, a live control FIFO, a JSON event sink, and a small
dashboard. ExaBGP is used here as an IX directly connected control-plane tool:
it speaks BGP from the router on the peering LAN and can inject or observe
routes at the exchange. It is not modeled as a normal host service behind an AS
router.

The base mini-internet is generated as a control-plane topology without regular
end hosts, because this example is about IX BGP tooling rather than data-plane
web services.

## Running

Generate the Docker output:

```bash
python ./mini_internet_exabgp_ix.py amd
```

Use `arm` instead of `amd` for ARM64 images.

The dashboard listens on container port `5000`. The host port is read from
`SEED_B30_EXABGP_PORT` and defaults to `5106`:

```bash
SEED_B30_EXABGP_PORT=5106 python ./mini_internet_exabgp_ix.py amd
```

Start the emulation manually:

```bash
cd output
DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 COMPOSE_PROJECT_NAME=b30 docker-compose build
COMPOSE_PROJECT_NAME=b30 docker-compose up -d
```

After BGP converges, open the dashboard at:

```text
http://localhost:5106/
```

If you changed `SEED_B30_EXABGP_PORT`, use that host port instead.
For command-line checks on hosts with an HTTP proxy configured, bypass the proxy:

```bash
curl --noproxy '*' http://127.0.0.1:5106/
```

## Live route injection

The AS180 router exposes `/run/exabgp/live.in` inside the ExaBGP container. Write
ExaBGP text API commands to that FIFO to announce or withdraw routes without
regenerating the topology or editing `/etc/exabgp/exabgp.conf`.

```bash
EXA=$(docker ps --format '{{.Names}}' | grep 'as180.*exabgp')
R2=$(docker ps --format '{{.Names}}' | grep 'as2.*r100')
R3=$(docker ps --format '{{.Names}}' | grep 'as3.*r100')
docker exec "$EXA" sh -lc "printf '%s\n' 'announce route 203.2.3.0/24 next-hop self' > /run/exabgp/live.in"
docker exec "$R2" birdc show route for 203.2.3.1 all
docker exec "$R3" birdc show route for 203.2.3.1 all
docker exec "$EXA" tail -n 20 /var/log/exabgp/live-control.log
```

Withdraw the same route:

```bash
docker exec "$EXA" sh -lc "printf '%s\n' 'withdraw route 203.2.3.0/24 next-hop self' > /run/exabgp/live.in"
docker exec "$R2" birdc show route for 203.2.3.1 all
```

## Notes

This example uses `createRouter("exabgp", routingBackend="exabgp")`. The AS180
router is an IX-connected BGP speaker, not a host-side application attached
behind another router.
The example uses the normal B00 Docker network mode rather than self-managed
dummy-address mode, because published dashboard ports must remain reachable from
the host.
