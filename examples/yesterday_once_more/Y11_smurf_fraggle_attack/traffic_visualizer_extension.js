(() => {
  let averageSize;
  let serviceStatus;
  let serviceLatency;
  let serviceSuccessRate;
  let serviceFailures;
  let serviceTimeline;
  let impactConfig;

  function setStatus(label, className) {
    serviceStatus.textContent = label;
    serviceStatus.className = `impact-status ${className}`;
  }

  function showWaiting() {
    setStatus('WAITING', 'waiting');
    serviceLatency.textContent = '--';
    serviceSuccessRate.textContent = '--';
    serviceFailures.textContent = '0';
    serviceTimeline.replaceChildren();
    const message = document.createElement('span');
    message.className = 'timeline-empty';
    message.textContent = 'Waiting for the legitimate client';
    serviceTimeline.appendChild(message);
  }

  function updateImpact(impact) {
    if (!impact || !impact.sample_count) {
      showWaiting();
      return;
    }

    const isStale = impact.last_probe_age_seconds > impactConfig.impact_stale_seconds;
    const latencyIsHigh = impact.latest_latency_ms >= impactConfig.impact_latency_warning_ms;
    if (isStale) {
      setStatus('UNREACHABLE', 'unreachable');
    } else if (impact.latest_success === false) {
      setStatus('FAILED', 'unreachable');
    } else if (impact.success_rate < 100 || latencyIsHigh) {
      setStatus('DEGRADED', 'degraded');
    } else {
      setStatus('HEALTHY', 'healthy');
    }

    serviceLatency.textContent = impact.latest_latency_ms === null
      ? 'Timeout'
      : `${impact.latest_latency_ms.toFixed(1)} ms`;
    serviceSuccessRate.textContent = `${impact.success_rate.toFixed(1)}%`;
    serviceFailures.textContent = String(impact.failure_count);

    serviceTimeline.replaceChildren();
    impact.samples.slice(-30).forEach((sample) => {
      const bar = document.createElement('i');
      bar.className = sample.success ? 'probe-sample success' : 'probe-sample failure';
      const percent = sample.success
        ? Math.max(6, Math.min(sample.latency_ms / impactConfig.impact_chart_max_ms, 1) * 100)
        : 100;
      bar.style.height = `${percent}%`;
      bar.title = sample.success ? `${sample.latency_ms.toFixed(1)} ms` : 'Failed';
      serviceTimeline.appendChild(bar);
    });
  }

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
        </div>
        <section class="impact-panel" aria-label="Victim service impact">
          <div class="impact-heading">
            <div>
              <div class="label">Victim impact</div>
              <strong>Legitimate HTTP service</strong>
            </div>
            <span class="impact-status waiting" id="impact-status">WAITING</span>
          </div>
          <div class="impact-metrics">
            <div><span class="label">Current latency</span><strong id="impact-latency">--</strong></div>
            <div><span class="label">Recent success</span><strong id="impact-success-rate">--</strong></div>
            <div><span class="label">Failures</span><strong id="impact-failures">0</strong></div>
          </div>
          <div class="label timeline-label">Recent probes (higher is slower; red is failed)</div>
          <div class="probe-timeline" id="impact-timeline"></div>
        </section>`;

      impactConfig = {
        impact_latency_warning_ms: Number(config.impact_latency_warning_ms) || 150,
        impact_stale_seconds: Number(config.impact_stale_seconds) || 4,
        impact_chart_max_ms: Number(config.impact_chart_max_ms) || 500,
      };
      root.querySelector('#broadcast-network').textContent = config.amplifier_network;
      averageSize = root.querySelector('#broadcast-average-size');
      serviceStatus = root.querySelector('#impact-status');
      serviceLatency = root.querySelector('#impact-latency');
      serviceSuccessRate = root.querySelector('#impact-success-rate');
      serviceFailures = root.querySelector('#impact-failures');
      serviceTimeline = root.querySelector('#impact-timeline');
      showWaiting();
    },
    update(stats, {formatBytes}) {
      averageSize.textContent = formatBytes(stats.average_ip_packet_size);
      updateImpact(stats.impact);
    },
    reset() {
      averageSize.textContent = '0 B';
      showWaiting();
    },
  });
})();
