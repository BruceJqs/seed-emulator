# Mini Internet ExaBGP IX Control Plane

This example extends `examples.internet.B00_mini_internet` with one additional
IX-connected control-plane router:

- `AS180` router `exabgp`
- IX: `ix100`
- IX address: `10.100.0.180`
- Local ASN: `180`
- Announcement: `203.0.113.0/24`
- eBGP peers: `AS2/r100` and `AS3/r100`

The router runs ExaBGP, a JSON event sink, and a small dashboard. ExaBGP is used
here as an IX directly connected control-plane tool: it speaks BGP from the
router on the peering LAN and can inject or observe routes at the exchange. It
is not modeled as a normal host service behind an AS router.

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
docker compose build
docker compose up -d
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

## Notes

This example intentionally uses the planned Core Worker A router-speaker API:
`claimRouterSpeaker(...)` and `addPeer(...)`. Those calls mark the AS180 router's
BGP speaker as owned by ExaBGP and define explicit IX eBGP peers without
treating ExaBGP as a regular host-side application.
The example uses the normal B00 Docker network mode rather than self-managed
dummy-address mode, because published dashboard ports must remain reachable from
the host.
