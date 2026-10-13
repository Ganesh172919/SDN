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
    if (this.ctx) this.ctx.clearRect(0, 0, this.width, this.height);
  }

  render() {
    if (!this.ctx || !this.data || this.data.length === 0) return;

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
    const initialLat = [24, 25, 28, 26, 22, 18, 14, 11, 9, 8, 7, 6.5, 6.2, 5.8, 5.4, 5.2];
    const initialTp = [8.5, 8.8, 9.2, 9.5, 10.1, 10.8, 11.2, 11.5, 11.8, 12.0, 12.2, 12.5, 12.8];
    const initialLoss = [7.8, 8.2, 6.5, 4.2, 2.1, 1.2, 0.8, 0.4, 0.2, 0.1, 0.0, 0.0];
    const initialRew = [-0.5, 0.2, 1.4, 2.8, 4.5, 6.2, 8.1, 9.9, 11.4, 12.8, 13.9, 14.6];

    this.chartLatency.setData(initialLat);
    this.chartThroughput.setData(initialTp);
    this.chartLoss.setData(initialLoss);
    this.chartReward.setData(initialRew);
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
    if (this.chartLatency) {
      this.chartLatency.addData(latency);
      const valEl = document.getElementById('chartLatencyVal');
      if (valEl) valEl.textContent = latency.toFixed(1);
    }
    if (this.chartThroughput) {
      this.chartThroughput.addData(throughput);
      const valEl = document.getElementById('chartThroughputVal');
      if (valEl) valEl.textContent = throughput.toFixed(1);
    }
    if (this.chartLoss) {
      this.chartLoss.addData(loss);
      const valEl = document.getElementById('chartLossVal');
      if (valEl) valEl.textContent = loss.toFixed(1);
    }
    if (this.chartReward) {
      this.chartReward.addData(reward);
      const valEl = document.getElementById('chartRewardVal');
      if (valEl) valEl.textContent = (reward >= 0 ? '+' : '') + reward.toFixed(2);
    }
  }
}

window.TelemetryChartsManager = TelemetryChartsManager;
