# Traffic Visualizer

Traffic Visualizer is a small, source-tree tool that counts packets and IPv4
bytes observed by `tcpdump` inside an emulated node and displays the totals in a
web browser. Byte counts use the IPv4 Total Length field, so they include the IP
header, transport header, and payload.

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
A configuration file can also provide presentation settings and optional
example-owned extension assets:

```json
{
  "interface": "any",
  "capture_filter": "icmp or udp",
  "web_host": "0.0.0.0",
  "web_port": 8080,
  "frontend": {
    "title": "Example title",
    "subtitle": "Traffic arriving at the victim",
    "accent_color": "#38bdf8",
    "extension_js": "extension.js",
    "extension_css": "extension.css",
    "options": {
      "example_value": "available to the extension"
    }
  }
}
```

Extension paths are resolved relative to the configuration file. Both files
are optional; without them, the generic dashboard works by itself. The base
page loads the CSS and calls JavaScript hooks registered as follows:

```javascript
TrafficVisualizer.registerExtension({
  mount(context) {},
  update(stats, context) {},
  reset(context) {},
});
```

`context` contains the extension root element, `frontend.options`, API version,
and number/byte formatting helpers. Extension errors are contained in the
extension area so the generic counters continue to update. This small contract
lets an example add attack-specific explanations or derived values without
forking the capture agent or dashboard.

The emulator script should copy the two shared files and its configuration into
the container, install Python and `tcpdump`, start `traffic_visualizer.py`, and
optionally publish the configured web port on the host.

## HTTP endpoints

- `/` - dashboard
- `/api/stats` - current packet counters
- `/api/config` - frontend metadata and extension options
- `/api/reset` - reset counters with an HTTP `POST`
- `/extension.js` and `/extension.css` - optional example-owned assets
- `/healthz` - capture process status
