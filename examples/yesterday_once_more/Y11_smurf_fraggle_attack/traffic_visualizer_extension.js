(() => {
  let averageSize;

  TrafficVisualizer.registerExtension({
    mount({root, config}) {
      root.innerHTML = `
        <div class="extension-grid broadcast-details">
          <div class="extension-card">
            <div class="label">Smurf mode</div>
            <span class="extension-value">ICMP echo replies</span>
          </div>
          <div class="extension-card">
            <div class="label">Fraggle mode</div>
            <span class="extension-value">UDP chargen-like replies</span>
          </div>
          <div class="extension-card">
            <div class="label">Amplifier LAN</div>
            <span class="extension-value" id="broadcast-network"></span>
          </div>
          <div class="extension-card">
            <div class="label">Average observed IP packet</div>
            <span class="extension-value" id="broadcast-average-size">0 B</span>
          </div>
        </div>`;
      root.querySelector('#broadcast-network').textContent = config.amplifier_network;
      averageSize = root.querySelector('#broadcast-average-size');
    },
    update(stats, {formatBytes}) {
      averageSize.textContent = formatBytes(stats.average_ip_packet_size);
    },
    reset() {
      averageSize.textContent = '0 B';
    },
  });
})();
