(() => {
  let requestSize;
  let averageSize;
  let amplificationValue;
  let responseBar;
  let responseScale;

  function showEmptyState() {
    averageSize.textContent = '0 B';
    amplificationValue.textContent = '0.0x';
    responseBar.style.width = '0%';
    responseScale.textContent = 'Waiting for amplified responses';
  }

  TrafficVisualizer.registerExtension({
    mount({root, config, formatBytes}) {
      root.innerHTML = `
        <div class="extension-grid ntp-details">
          <div class="extension-card">
            <div class="label">Fixed request IP packet</div>
            <span class="extension-value" id="ntp-request-size"></span>
            <span class="extension-note" id="ntp-request-payload"></span>
          </div>
          <div class="extension-card">
            <div class="label">Average response IP packet</div>
            <span class="extension-value" id="ntp-average-size">0 B</span>
          </div>
          <div class="extension-card amplification-card">
            <div class="label">IP-layer byte amplification</div>
            <span class="extension-value amplification-value" id="ntp-amplification">0.0x</span>
          </div>
          <div class="extension-card">
            <div class="label">Lab amplifiers</div>
            <span class="extension-value" id="ntp-amplifiers"></span>
          </div>
        </div>
        <div class="amplification-scale">
          <div class="scale-heading">
            <span>Request-to-response scale</span>
            <span id="ntp-response-scale">Waiting for amplified responses</span>
          </div>
          <div class="scale-row">
            <span class="scale-label">Request</span>
            <div class="scale-track"><span class="scale-bar request-bar"></span></div>
            <span class="scale-number">1x</span>
          </div>
          <div class="scale-row">
            <span class="scale-label">Response</span>
            <div class="scale-track"><span class="scale-bar response-bar" id="ntp-response-bar"></span></div>
            <span class="scale-number" id="ntp-response-number">0.0x</span>
          </div>
        </div>`;

      const requestIpBytes = Number(config.request_ip_bytes);
      const requestPayloadBytes = Number(config.request_payload_bytes);
      requestSize = requestIpBytes;
      root.querySelector('#ntp-request-size').textContent = formatBytes(requestIpBytes);
      root.querySelector('#ntp-request-payload').textContent =
        `${formatBytes(requestPayloadBytes)} UDP payload + ` +
        `${formatBytes(requestIpBytes - requestPayloadBytes)} headers`;
      root.querySelector('#ntp-amplifiers').textContent = config.amplifiers;
      averageSize = root.querySelector('#ntp-average-size');
      amplificationValue = root.querySelector('#ntp-amplification');
      responseBar = root.querySelector('#ntp-response-bar');
      responseScale = root.querySelector('#ntp-response-scale');
      const maximum = Number(config.gauge_max_amplification) || 20;
      responseBar.dataset.maximum = String(maximum);
      root.querySelector('.request-bar').style.width = `${100 / maximum}%`;
    },
    update(stats, {formatBytes, root}) {
      if (!stats.total_packets) {
        showEmptyState();
        root.querySelector('#ntp-response-number').textContent = '0.0x';
        return;
      }

      const averageResponseBytes = stats.total_ip_bytes / stats.total_packets;
      const amplification = averageResponseBytes / requestSize;
      const formattedAmplification = `${amplification.toFixed(1)}x`;
      const maximum = Number(responseBar.dataset.maximum);

      averageSize.textContent = formatBytes(Math.round(averageResponseBytes));
      amplificationValue.textContent = formattedAmplification;
      responseScale.textContent = `Observed response is ${formattedAmplification} the request size`;
      responseBar.style.width = `${Math.min(amplification / maximum, 1) * 100}%`;
      root.querySelector('#ntp-response-number').textContent = formattedAmplification;
    },
    reset({root}) {
      showEmptyState();
      root.querySelector('#ntp-response-number').textContent = '0.0x';
    },
  });
})();
