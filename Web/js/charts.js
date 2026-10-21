/**
 * charts.js - High-Performance Real-Time Canvas Line Charts
 * Pure Vanilla Canvas implementation with smooth cubic Bezier splines,
 * luminous gradient fills, gridlines, glowing threshold lines, and auto-scaling.
 */

class MiniLineChart {
  constructor(canvasId, options = {}) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');

    this.options = Object.assign({
      lineColor: '#00f2fe',
      fillColor: 'rgba(0, 242, 254, 0.18)',
      unit: '',
      maxPoints: 30,
      minY: 0,
      maxY: null,
      targetLine: null,
      targetColor: 'rgba(239, 68, 68, 0.65)'
    }, options);

    this.data = [];
    this.width = 540;
    this.height = 220;
    this.setupDPI();

    window.addEventListener('resize', () => {
      this.setupDPI();
      this.render();
    });
  }

  setupDPI() {
    if (!this.canvas) return;
    const dpr = window.devicePixelRatio || 1;
    let rect = this.canvas.getBoundingClientRect();
    let w = rect.width;
    let h = rect.height;

    // If canvas is hidden or 0, check parent container or default fallback
    if (!w || w <= 0 || !h || h <= 0) {
      if (this.canvas.parentElement) {
        w = this.canvas.parentElement.clientWidth;
        h = this.canvas.parentElement.clientHeight;
      }
    }
    if (!w || w <= 0) w = 540;
    if (!h || h <= 0) h = 220;

    this.width = w;
    this.height = h;

    this.canvas.width = Math.floor(w * dpr);
    this.canvas.height = Math.floor(h * dpr);

    if (this.ctx) {
      this.ctx.setTransform(1, 0, 0, 1, 0, 0); // reset transform matrix
      this.ctx.scale(dpr, dpr);
    }
  }

  addData(val) {
    this.data.push(val);
    if (this.data.length > this.options.maxPoints) {
      this.data.shift();
    }
    this.render();
  }

  setData(dataArray) {
    this.data = [...dataArray];
    this.render();
  }

  clear() {
    this.data = [];
    if (this.ctx) this.ctx.clearRect(0, 0, this.width || 540, this.height || 220);
  }

  render() {
    if (!this.ctx) return;
    if (!this.data || this.data.length === 0) {
      this.ctx.clearRect(0, 0, this.width || 540, this.height || 220);
      return;
    }

    // Auto-setup dimensions if needed or if container size changed
    if (!this.width || !this.height || this.width <= 0 || this.height <= 0) {
      this.setupDPI();
    } else {
      const rect = this.canvas.getBoundingClientRect();
      if (rect.width > 0 && Math.abs(rect.width - this.width) > 6) {
        this.setupDPI();
      }
    }

    const w = this.width || 540;
    const h = this.height || 220;
    const padding = { top: 22, right: 28, bottom: 25, left: 42 };

    const ctx = this.ctx;
    ctx.clearRect(0, 0, w, h);

    // Compute dynamic min & max Y
    let minVal = this.options.minY !== null ? this.options.minY : Math.min(...this.data);
    let maxVal = this.options.maxY !== null ? this.options.maxY : Math.max(...this.data);
    if (minVal === maxVal) { maxVal += 10; minVal = Math.max(0, minVal - 5); }
    const range = maxVal - minVal || 1;

    // Draw horizontal grid lines
    ctx.save();
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.06)';
    ctx.lineWidth = 1;
    ctx.font = '9px "JetBrains Mono", monospace';
    ctx.fillStyle = 'rgba(148, 163, 184, 0.6)';
    ctx.textAlign = 'right';

    const steps = 4;
    for (let i = 0; i <= steps; i++) {
      const yVal = minVal + (range / steps) * i;
      const y = h - padding.bottom - ((yVal - minVal) / range) * (h - padding.top - padding.bottom);

      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(w - padding.right, y);
      ctx.stroke();

      ctx.fillText(yVal.toFixed(1) + this.options.unit, padding.left - 6, y + 3);
    }

    // Optional Target Threshold Line
    if (this.options.targetLine !== null) {
      const targetY = h - padding.bottom - ((this.options.targetLine - minVal) / range) * (h - padding.top - padding.bottom);
      ctx.save();
      ctx.strokeStyle = this.options.targetColor;
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(padding.left, targetY);
      ctx.lineTo(w - padding.right, targetY);
      ctx.stroke();

      ctx.fillStyle = this.options.targetColor;
      ctx.font = '8px "JetBrains Mono", monospace';
      ctx.textAlign = 'left';
      ctx.fillText('TARGET SLA', w - padding.right - 54, targetY - 4);
      ctx.restore();
    }

    // Calculate Cartesian points
    const points = this.data.map((val, idx) => {
      const x = padding.left + (idx / Math.max(1, this.data.length - 1)) * (w - padding.left - padding.right);
      const y = h - padding.bottom - ((val - minVal) / range) * (h - padding.top - padding.bottom);
      return { x, y };
    });

    if (points.length < 2) {
      ctx.restore();
      return;
    }

    // Helper: Build smooth cubic Bezier path
    function buildBezierPath(c, pts) {
      c.moveTo(pts[0].x, pts[0].y);
      for (let i = 0; i < pts.length - 1; i++) {
        const p0 = pts[Math.max(0, i - 1)];
        const p1 = pts[i];
        const p2 = pts[i + 1];
        const p3 = pts[Math.min(pts.length - 1, i + 2)];

        const cp1x = p1.x + (p2.x - p0.x) / 6;
        const cp1y = p1.y + (p2.y - p0.y) / 6;
        const cp2x = p2.x - (p3.x - p1.x) / 6;
        const cp2y = p2.y - (p3.y - p1.y) / 6;

        c.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, p2.x, p2.y);
      }
    }

    // 1. Draw smooth gradient fill under the curve
    const gradient = ctx.createLinearGradient(0, padding.top, 0, h - padding.bottom);
    gradient.addColorStop(0, this.options.fillColor);
    gradient.addColorStop(0.85, 'rgba(0, 0, 0, 0.05)');
    gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');

    ctx.beginPath();
    buildBezierPath(ctx, points);
    ctx.lineTo(points[points.length - 1].x, h - padding.bottom);
    ctx.lineTo(points[0].x, h - padding.bottom);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // 2. Draw smooth luminous stroke line
    ctx.beginPath();
    buildBezierPath(ctx, points);
    ctx.strokeStyle = this.options.lineColor;
    ctx.lineWidth = 2.5;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.shadowColor = this.options.lineColor;
    ctx.shadowBlur = 9;
    ctx.stroke();

    // 3. Draw pulsing active point at latest data entry
    const latest = points[points.length - 1];
    ctx.shadowBlur = 0;

    // Outer glow halo
    ctx.beginPath();
    ctx.arc(latest.x, latest.y, 7, 0, Math.PI * 2);
    ctx.fillStyle = this.options.fillColor;
    ctx.fill();

    // Inner bright dot
    ctx.beginPath();
    ctx.arc(latest.x, latest.y, 4, 0, Math.PI * 2);
    ctx.fillStyle = '#ffffff';
    ctx.shadowColor = this.options.lineColor;
    ctx.shadowBlur = 12;
    ctx.fill();

    ctx.restore();
  }
}

class TelemetryChartsManager {
  constructor() {
    this.chartLatency = new MiniLineChart('chartLatency', {
      lineColor: '#38bdf8',
      fillColor: 'rgba(56, 189, 248, 0.22)',
      unit: 'ms',
      minY: 0,
      maxY: 35,
      targetLine: 15
    });

    this.chartThroughput = new MiniLineChart('chartThroughput', {
      lineColor: '#10b981',
      fillColor: 'rgba(16, 185, 129, 0.22)',
      unit: 'M',
      minY: 0,
      maxY: 16
    });

    this.chartLoss = new MiniLineChart('chartLoss', {
      lineColor: '#ef4444',
      fillColor: 'rgba(239, 68, 68, 0.22)',
      unit: '%',
      minY: 0,
      maxY: 12,
      targetLine: 1
    });

    this.chartReward = new MiniLineChart('chartReward', {
      lineColor: '#a855f7',
      fillColor: 'rgba(168, 85, 247, 0.22)',
      unit: '',
      minY: -2,
      maxY: 20
    });

    this.initHistory();
  }

  initHistory() {
    this.clear();
  }

  renderAll() {
    [this.chartLatency, this.chartThroughput, this.chartLoss, this.chartReward].forEach(chart => {
      if (chart) {
        chart.setupDPI();
        chart.render();
      }
    });
  }

  setLiveMode(enabled) {
    if (enabled) this.clear();
  }

  clear() {
    [this.chartLatency, this.chartThroughput, this.chartLoss, this.chartReward].forEach(chart => {
      if (chart) chart.clear();
    });
  }

  updateMetrics(latency, throughput, loss, reward) {
    if (this.chartLatency && typeof latency === 'number' && !isNaN(latency)) {
      this.chartLatency.addData(latency);
      const valEl = document.getElementById('chartLatencyVal');
      if (valEl) valEl.textContent = latency.toFixed(1);
    }
    if (this.chartThroughput && typeof throughput === 'number' && !isNaN(throughput)) {
      this.chartThroughput.addData(throughput);
      const valEl = document.getElementById('chartThroughputVal');
      if (valEl) valEl.textContent = throughput.toFixed(1);
    }
    if (this.chartLoss && typeof loss === 'number' && !isNaN(loss)) {
      this.chartLoss.addData(loss);
      const valEl = document.getElementById('chartLossVal');
      if (valEl) valEl.textContent = loss.toFixed(1);
    }
    if (this.chartReward && typeof reward === 'number' && !isNaN(reward)) {
      this.chartReward.addData(reward);
      const valEl = document.getElementById('chartRewardVal');
      if (valEl) valEl.textContent = (reward >= 0 ? '+' : '') + reward.toFixed(2);
    }
  }
}

class BenchmarkBarChart {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.data = null;
    this.scenario = 'mixed';
    this.metric = 'loss_pct';
    this.width = 900;
    this.height = 320;
    this.setupDPI();

    window.addEventListener('resize', () => {
      this.setupDPI();
      this.render();
    });
  }

  setupDPI() {
    if (!this.canvas) return;
    const dpr = window.devicePixelRatio || 1;
    let rect = this.canvas.getBoundingClientRect();
    let w = rect.width || (this.canvas.parentElement ? this.canvas.parentElement.clientWidth : 900);
    let h = rect.height || 320;
    if (w <= 0) w = 900;
    if (h <= 0) h = 320;
    this.width = w;
    this.height = h;
    this.canvas.width = Math.floor(w * dpr);
    this.canvas.height = Math.floor(h * dpr);
    if (this.ctx) {
      this.ctx.setTransform(1, 0, 0, 1, 0, 0);
      this.ctx.scale(dpr, dpr);
    }
  }

  clear() {
    this.setupDPI();
    if (this.ctx) {
      this.ctx.clearRect(0, 0, this.width, this.height);
    }
    const table = document.getElementById('benchmarkMetricsTable');
    if (table) {
      table.innerHTML = `<tbody><tr><td colspan="6" style="text-align:center; padding:1.5rem; color:var(--text-secondary);">No benchmark data available.</td></tr></tbody>`;
    }
  }

  setData(summaryData) {
    if (!summaryData || typeof summaryData !== 'object' || !summaryData.groups) {
      this.data = null;
      this.clear();
      return;
    }
    this.data = summaryData;
    this.render();
  }

  setScenario(scenario) {
    this.scenario = scenario;
    if (!this.data || !this.data.groups || !this.data.groups[this.scenario]) {
      this.clear();
      return;
    }
    this.render();
  }

  setMetric(metric) {
    this.metric = metric;
    this.render();
  }

  render() {
    if (!this.ctx) return;
    if (!this.data || !this.data.groups || !this.data.groups[this.scenario]) {
      this.clear();
      return;
    }
    const group = this.data.groups[this.scenario];
    if (!group) {
      this.clear();
      return;
    }

    this.setupDPI();
    const w = this.width;
    const h = this.height;
    const ctx = this.ctx;
    ctx.clearRect(0, 0, w, h);

    const controllers = Object.keys(this.data.controllers || group);
    const padding = { top: 35, right: 30, bottom: 45, left: 65 };
    const chartW = w - padding.left - padding.right;
    const chartH = h - padding.top - padding.bottom;

    const entries = controllers.map(cid => {
      const cdata = group[cid];
      if (!cdata || !cdata.metrics || !cdata.metrics[this.metric]) return null;
      const m = cdata.metrics[this.metric];
      if (typeof m.mean !== 'number' || isNaN(m.mean)) return null;

      let val = m.mean;
      const hasCI = Boolean(
        m.ci95 &&
        Array.isArray(m.ci95) &&
        m.ci95.length === 2 &&
        typeof m.ci95[0] === 'number' &&
        typeof m.ci95[1] === 'number' &&
        !isNaN(m.ci95[0]) &&
        !isNaN(m.ci95[1])
      );
      let ciLow = hasCI ? m.ci95[0] : null;
      let ciHigh = hasCI ? m.ci95[1] : null;

      if (this.metric === 'throughput_kbps') {
        val /= 1000;
        if (hasCI) {
          ciLow /= 1000;
          ciHigh /= 1000;
        }
      }

      return {
        id: cid,
        label: cdata.label || (this.data.controllers && this.data.controllers[cid]) || cid,
        val: val,
        hasCI: hasCI,
        ciLow: ciLow,
        ciHigh: ciHigh,
        actions: cdata.actions,
        vetoes: cdata.vetoes
      };
    }).filter(Boolean);

    if (entries.length === 0) {
      this.clear();
      return;
    }

    let maxVal = Math.max(...entries.map(e => e.hasCI ? Math.max(e.val, e.ciHigh) : e.val));
    maxVal = maxVal <= 0 ? 1 : maxVal * 1.15;
    const minVal = 0;

    // Gridlines
    ctx.save();
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.06)';
    ctx.lineWidth = 1;
    ctx.fillStyle = 'rgba(148, 163, 184, 0.6)';
    ctx.font = '10px monospace';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';

    const steps = 4;
    for (let i = 0; i <= steps; i++) {
      const frac = i / steps;
      const yVal = minVal + frac * (maxVal - minVal);
      const yPx = padding.top + chartH - frac * chartH;

      ctx.beginPath();
      ctx.moveTo(padding.left, yPx);
      ctx.lineTo(w - padding.right, yPx);
      ctx.stroke();

      let labelText = yVal.toFixed(1);
      if (this.metric === 'loss_pct') labelText += '%';
      else if (this.metric === 'latency_ms') labelText += ' ms';
      else if (this.metric === 'throughput_kbps') labelText += ' M';

      ctx.fillText(labelText, padding.left - 8, yPx);
    }

    // Bars and Error Whiskers
    const n = entries.length;
    const slotW = chartW / n;
    const barW = Math.min(slotW * 0.58, 48);

    entries.forEach((e, idx) => {
      const centerX = padding.left + idx * slotW + slotW / 2;
      const barX = centerX - barW / 2;
      const barH = (Math.max(0, e.val) / maxVal) * chartH;
      const barY = padding.top + chartH - barH;

      let fillColor = 'rgba(148, 163, 184, 0.45)';
      let strokeColor = '#94a3b8';
      if (e.id === 'A4') {
        fillColor = 'rgba(0, 242, 254, 0.65)';
        strokeColor = '#00f2fe';
      } else if (e.id === 'H2') {
        fillColor = 'rgba(245, 158, 11, 0.65)';
        strokeColor = '#f59e0b';
      } else if (e.id === 'O2') {
        fillColor = 'rgba(168, 85, 247, 0.65)';
        strokeColor = '#a855f7';
      } else if (e.id === 'H1') {
        fillColor = 'rgba(239, 68, 68, 0.5)';
        strokeColor = '#ef4444';
      }

      ctx.fillStyle = fillColor;
      ctx.strokeStyle = strokeColor;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      if (ctx.roundRect) {
        ctx.roundRect(barX, barY, barW, barH, [4, 4, 0, 0]);
      } else {
        ctx.rect(barX, barY, barW, barH);
      }
      ctx.fill();
      ctx.stroke();

      // Whisker: Only draw when genuine confidence interval is present (do not fabricate error bars)
      if (e.hasCI) {
        const yLow = padding.top + chartH - (e.ciLow / maxVal) * chartH;
        const yHigh = padding.top + chartH - (e.ciHigh / maxVal) * chartH;
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(centerX, yLow);
        ctx.lineTo(centerX, yHigh);
        ctx.moveTo(centerX - 4, yHigh);
        ctx.lineTo(centerX + 4, yHigh);
        ctx.moveTo(centerX - 4, yLow);
        ctx.lineTo(centerX + 4, yLow);
        ctx.stroke();
      }

      // Value label
      ctx.fillStyle = '#f8fafc';
      ctx.textAlign = 'center';
      ctx.font = '10px sans-serif';
      let valStr = e.val.toFixed(this.metric === 'throughput_kbps' ? 1 : 2);
      const topLabelY = e.hasCI ? Math.min(barY, padding.top + chartH - (e.ciHigh / maxVal) * chartH) : barY;
      ctx.fillText(valStr, centerX, topLabelY - 6);

      // Controller label below X axis
      ctx.fillStyle = e.id === 'A4' ? '#00f2fe' : (e.id === 'H2' ? '#f59e0b' : '#cbd5e1');
      ctx.font = e.id === 'A4' ? 'bold 11px sans-serif' : '10px sans-serif';
      ctx.fillText(e.id, centerX, padding.top + chartH + 16);
    });

    ctx.restore();
    this.updateTable(entries);
  }

  updateTable(entries) {
    const table = document.getElementById('benchmarkMetricsTable');
    if (!table) return;

    let unit = '%';
    if (this.metric === 'latency_ms') unit = 'ms';
    else if (this.metric === 'throughput_kbps') unit = 'Mbps';

    let html = `<thead>
      <tr style="border-bottom: 1px solid rgba(255,255,255,0.1); color: var(--text-secondary);">
        <th style="padding:0.4rem 0.6rem; text-align:left;">ID</th>
        <th style="padding:0.4rem 0.6rem; text-align:left;">Controller Technique</th>
        <th style="padding:0.4rem 0.6rem; text-align:right;">Mean (${unit})</th>
        <th style="padding:0.4rem 0.6rem; text-align:right;">95% Bootstrap CI</th>
        <th style="padding:0.4rem 0.6rem; text-align:right;">Actions (no_op / rate / reroute)</th>
        <th style="padding:0.4rem 0.6rem; text-align:right;">Vetoes</th>
      </tr>
    </thead><tbody>`;

    entries.forEach(e => {
      const isKey = e.id === 'A4' || e.id === 'H2';
      const rowStyle = isKey ? 'background: rgba(0, 242, 254, 0.05); font-weight: 600;' : '';

      // Mean format: preserve valid 0 as 0.00
      const meanStr = (typeof e.val === 'number' && !isNaN(e.val))
        ? e.val.toFixed(this.metric === 'throughput_kbps' ? 1 : 2)
        : '—';

      // CI format: if missing, display — (do not fabricate [val, val])
      const ciStr = e.hasCI
        ? `[${e.ciLow.toFixed(2)}, ${e.ciHigh.toFixed(2)}]`
        : '—';

      // Actions format: if missing or not an object, display —
      let actStr = '—';
      if (e.actions && typeof e.actions === 'object' && Object.keys(e.actions).length > 0) {
        const noOp = typeof e.actions.no_op === 'number' ? e.actions.no_op : 0;
        const rateLimit = typeof e.actions.rate_limit === 'number' ? e.actions.rate_limit : 0;
        const reroute = typeof e.actions.reroute === 'number' ? e.actions.reroute : 0;
        actStr = `${noOp} / ${rateLimit} / ${reroute}`;
      }

      // Vetoes format: preserve valid 0 as 0, missing as —
      let vetoStr = '—';
      let vetoColor = 'var(--text-secondary)';
      if (typeof e.vetoes === 'number' && !isNaN(e.vetoes)) {
        vetoStr = String(e.vetoes);
        vetoColor = e.vetoes === 0 ? '#34d399' : '#f87171';
      }

      html += `<tr style="border-bottom: 1px solid rgba(255,255,255,0.04); ${rowStyle}">
        <td style="padding:0.4rem 0.6rem; color:${e.id === 'A4' ? '#00f2fe' : (e.id === 'H2' ? '#fbbf24' : '#94a3b8')};">${e.id}</td>
        <td style="padding:0.4rem 0.6rem;">${e.label}</td>
        <td style="padding:0.4rem 0.6rem; text-align:right;">${meanStr}</td>
        <td style="padding:0.4rem 0.6rem; text-align:right; color:var(--text-secondary); font-family:monospace;">${ciStr}</td>
        <td style="padding:0.4rem 0.6rem; text-align:right; font-family:monospace;">${actStr}</td>
        <td style="padding:0.4rem 0.6rem; text-align:right; color:${vetoColor};">${vetoStr}</td>
      </tr>`;
    });
    html += '</tbody>';
    table.innerHTML = html;
  }
}

window.TelemetryChartsManager = TelemetryChartsManager;
window.BenchmarkBarChart = BenchmarkBarChart;
