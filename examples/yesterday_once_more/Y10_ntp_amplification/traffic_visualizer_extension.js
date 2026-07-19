(() => {
  let averageSize;

  TrafficVisualizer.registerExtension({
    mount({root, config}) {
      root.innerHTML = `
        <div class="extension-grid ntp-details">
          <div class="extension-card">
            <div class="label">Attack pattern</div>
            <span class="extension-value">Small request → large reply</span>
          </div>
          <div class="extension-card">
            <div class="label">Lab amplifiers</div>
            <span class="extension-value" id="ntp-amplifiers"></span>
          </div>
          <div class="extension-card">
            <div class="label">Average observed IP packet</div>
            <span class="extension-value" id="ntp-average-size">0 B</span>
          </div>
        </div>`;
      root.querySelector('#ntp-amplifiers').textContent = config.amplifiers;
      averageSize = root.querySelector('#ntp-average-size');
    },
    update(stats, {formatBytes}) {
      averageSize.textContent = formatBytes(stats.average_ip_packet_size);
    },
    reset() {
      averageSize.textContent = '0 B';
    },
  });
})();
