# Traffic Visualizer

Traffic Visualizer is a small, source-tree tool that counts packets observed by
`tcpdump` inside an emulated node and displays the count in a web browser.

The tool is intentionally kept outside the `seedemu` Python package while it is
being developed. Examples load `traffic_visualizer.py` and `dashboard.html`
directly from this directory and copy them into their victim containers. This
means those examples must be run from a SEED Emulator source checkout.

## Container requirements

- Python 3
- `tcpdump`
- permission to capture packets

## Example-owned configuration

Capture settings belong to each example, rather than to this shared directory.
A configuration file has the following shape:

```json
{
  "interface": "any",
  "capture_filter": "icmp or udp",
  "web_host": "0.0.0.0",
  "web_port": 8080
}
```

The emulator script should copy the two shared files and its configuration into
the container, install Python and `tcpdump`, start `traffic_visualizer.py`, and
optionally publish the configured web port on the host.

## HTTP endpoints

- `/` - dashboard
- `/api/stats` - current packet counters
- `/api/reset` - reset counters with an HTTP `POST`
- `/healthz` - capture process status
