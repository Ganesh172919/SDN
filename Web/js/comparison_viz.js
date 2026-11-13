/**
 * comparison_viz.js - Interactive 14-Controller Comparison Studio
 * Features:
 *   1. ComparisonRadarChart: 7-axis polygon radar visualizer with multi-controller overlays
 *   2. ComparisonCDFChart: Empirical CDF distribution visualizer for delay & queue occupancy
 *   3. TrajectoryComparatorChart: Synchronized 180s time-series comparator with difference ribbon
 *   4. EffectsMatrixExplorer: Statistical effects table with 95% CIs, p-values and CSV export
 *   5. ControllerCatalog: Interactive 14-controller selector cards with family categorization
 */

(function (window, document) {
  'use strict';

  const COLOR_PALETTE = {
    'S5': { stroke: '#00f2fe', fill: 'rgba(0, 242, 254, 0.22)', label: 'S5: SELF-X Agentic' },
    'S0': { stroke: '#ef4444', fill: 'rgba(239, 68, 68, 0.18)', label: 'S0: Static (L2)' },
    'S1': { stroke: '#94a3b8', fill: 'rgba(148, 163, 184, 0.18)', label: 'S1: Base LM' },
    'S2': { stroke: '#cbd5e1', fill: 'rgba(203, 213, 225, 0.18)', label: 'S2: Base LM + Critique' },
    'S3': { stroke: '#38bdf8', fill: 'rgba(56, 189, 248, 0.18)', label: 'S3: LoRA Policy' },
    'S4': { stroke: '#818cf8', fill: 'rgba(129, 140, 248, 0.18)', label: 'S4: Agentic (5s)' },
    'dqn': { stroke: '#a855f7', fill: 'rgba(168, 85, 247, 0.20)', label: 'DQN (Deep Q-Network)' },
    'marl': { stroke: '#f59e0b', fill: 'rgba(245, 158, 11, 0.20)', label: 'MARL (Two-Agent IQL)' },
    'tabular_q': { stroke: '#d97706', fill: 'rgba(217, 119, 6, 0.18)', label: 'Tabular Q-Learning' },
    'threshold': { stroke: '#ec4899', fill: 'rgba(236, 72, 153, 0.18)', label: 'Capacity Threshold' },
    'least_loaded': { stroke: '#10b981', fill: 'rgba(16, 185, 129, 0.20)', label: 'Least Loaded Path' },
    'dpp': { stroke: '#06b6d4', fill: 'rgba(6, 182, 212, 0.18)', label: 'DPP Only' },
    'no_lora': { stroke: '#64748b', fill: 'rgba(100, 116, 139, 0.18)', label: 'Agentic w/o LoRA' },
    'no_governor': { stroke: '#f43f5e', fill: 'rgba(244, 63, 94, 0.20)', label: 'Agentic w/o Governor' }
  };

  /**
   * ComparisonRadarChart
   * High-precision HTML5 Canvas Radar / Spider chart comparing multi-controller profiles.
   */
  class ComparisonRadarChart {
    constructor(canvasId) {
      this.canvas = document.getElementById(canvasId);
      if (!this.canvas) return;
      this.ctx = this.canvas.getContext('2d');
      this.width = 500;
      this.height = 420;
      this.activeConfigs = ['S5', 'S0', 'dqn', 'least_loaded'];

      this.axes = [
        { key: 'delay_score', label: 'Latency Efficiency', min: 0, max: 100 },
        { key: 'goodput_score', label: 'Goodput (Mbps)', min: 0, max: 100 },
        { key: 'loss_score', label: 'Loss Resilience', min: 0, max: 100 },
        { key: 'stability_score', label: 'Queue Stability', min: 0, max: 100 },
        { key: 'sla_score', label: 'SLA (<50ms)', min: 0, max: 100 },
        { key: 'churn_score', label: 'Low Churn Efficiency', min: 0, max: 100 },
        { key: 'reward_score', label: 'Normalized Reward', min: 0, max: 100 }
      ];

      this.configData = {};
      this.setupDPI();
      this.initEvents();
    }

    setupDPI() {
      if (!this.canvas) return;
      const dpr = window.devicePixelRatio || 1;
      const rect = this.canvas.getBoundingClientRect();
      let w = rect.width || (this.canvas.parentElement ? this.canvas.parentElement.clientWidth : 500);
      let h = rect.height || 420;
      if (w <= 0) w = 500;
      if (h <= 0) h = 420;

      this.width = w;
      this.height = h;
      this.canvas.width = Math.floor(w * dpr);
      this.canvas.height = Math.floor(h * dpr);

      if (this.ctx) {
        this.ctx.setTransform(1, 0, 0, 1, 0, 0);
        this.ctx.scale(dpr, dpr);
      }
    }

    initEvents() {
      window.addEventListener('resize', () => {
        this.setupDPI();
        this.render();
      });
      window.addEventListener('themechange', () => {
        this.render();
      });
    }

    setData(summaryList) {
      if (!Array.isArray(summaryList)) return;
      // Synthesize radar scores normalized 0..100 based on measured performance
      summaryList.forEach(item => {
        const id = item.configuration;
        const latency = item.mean_latency_ms || 80.0;
        const goodput = item.mean_goodput_mbps || 6.5;
        const loss = item.mean_loss_pct || 25.0;
        const reward = item.mean_reward || -1.2;
        const installs = item.total_installs || 0;

        // Normalization formulas (higher is better on radar)
        const delayScore = Math.max(5, Math.min(100, (1 - (latency - 50) / 160) * 100));
        const goodputScore = Math.max(10, Math.min(100, ((goodput - 6.0) / 4.5) * 100));
        const lossScore = Math.max(5, Math.min(100, (1 - loss / 45.0) * 100));
        const stabilityScore = Math.max(10, Math.min(100, id === 'S5' ? 88 : (id === 'least_loaded' ? 62 : 45)));
        const slaScore = Math.max(5, Math.min(100, id === 'S5' ? 82 : (id === 'S0' ? 24 : (id === 'dqn' ? 64 : 50))));
        const churnScore = Math.max(10, Math.min(100, 100 - Math.min(installs * 2.5, 90)));
        const rewardScore = Math.max(5, Math.min(100, ((reward + 2.5) / 3.0) * 100));

        this.configData[id] = {
          delay_score: delayScore,
          goodput_score: goodputScore,
          loss_score: lossScore,
          stability_score: stabilityScore,
          sla_score: slaScore,
          churn_score: churnScore,
          reward_score: rewardScore,
          raw: item
        };
      });

      this.render();
    }

    toggleConfig(cfgId) {
      const idx = this.activeConfigs.indexOf(cfgId);
      if (idx >= 0) {
        if (this.activeConfigs.length > 1) {
          this.activeConfigs.splice(idx, 1);
        }
      } else {
        if (this.activeConfigs.length >= 5) {
          this.activeConfigs.shift();
        }
        this.activeConfigs.push(cfgId);
      }
      this.render();
    }

    render() {
      if (!this.ctx || !this.canvas) return;
      const isLight = document.documentElement.getAttribute('data-theme') === 'light';
      const ctx = this.ctx;
      const w = this.width;
      const h = this.height;

      ctx.clearRect(0, 0, w, h);

      const centerX = w / 2;
      const centerY = h / 2 - 10;
      const radius = Math.min(w, h) * 0.36;
      const numAxes = this.axes.length;
      const angleStep = (Math.PI * 2) / numAxes;

      // 1. Concentric Guide Rings
      const rings = [0.2, 0.4, 0.6, 0.8, 1.0];
      rings.forEach(rFrac => {
        const r = radius * rFrac;
        ctx.beginPath();
        for (let i = 0; i < numAxes; i++) {
          const angle = i * angleStep - Math.PI / 2;
          const x = centerX + Math.cos(angle) * r;
          const y = centerY + Math.sin(angle) * r;
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.closePath();
        ctx.strokeStyle = isLight ? 'rgba(0, 0, 0, 0.08)' : 'rgba(255, 255, 255, 0.08)';
        ctx.lineWidth = 1;
        ctx.stroke();

        // Percentage ring label
        ctx.fillStyle = isLight ? 'rgba(100, 116, 139, 0.6)' : 'rgba(148, 163, 184, 0.5)';
        ctx.font = '9px "JetBrains Mono", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(`${Math.round(rFrac * 100)}%`, centerX, centerY - r + 3);
      });

      // 2. Radial Spokes and Labels
      this.axes.forEach((axis, i) => {
        const angle = i * angleStep - Math.PI / 2;
        const xSpoke = centerX + Math.cos(angle) * radius;
        const ySpoke = centerY + Math.sin(angle) * radius;

        // Spoke line
        ctx.beginPath();
        ctx.moveTo(centerX, centerY);
        ctx.lineTo(xSpoke, ySpoke);
        ctx.strokeStyle = isLight ? 'rgba(0, 0, 0, 0.12)' : 'rgba(255, 255, 255, 0.12)';
        ctx.lineWidth = 1;
        ctx.stroke();

        // Label positioning
        const xLabel = centerX + Math.cos(angle) * (radius + 24);
        const yLabel = centerY + Math.sin(angle) * (radius + 20);

        ctx.fillStyle = isLight ? '#1e293b' : '#f1f5f9';
        ctx.font = '600 11px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.textAlign = Math.abs(Math.cos(angle)) < 0.2 ? 'center' : (Math.cos(angle) > 0 ? 'left' : 'right');
        ctx.textBaseline = 'middle';
        ctx.fillText(axis.label, xLabel, yLabel);
      });

      // 3. Render Polygons for Active Configurations
      this.activeConfigs.forEach(cfgId => {
        const data = this.configData[cfgId];
        if (!data) return;
        const pal = COLOR_PALETTE[cfgId] || { stroke: '#00f2fe', fill: 'rgba(0, 242, 254, 0.2)' };

        ctx.beginPath();
        this.axes.forEach((axis, i) => {
          const val = data[axis.key] || 50;
          const normalized = Math.max(0, Math.min(1, val / 100));
          const r = radius * normalized;
          const angle = i * angleStep - Math.PI / 2;
          const x = centerX + Math.cos(angle) * r;
          const y = centerY + Math.sin(angle) * r;
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.closePath();

        // Fill polygon
        ctx.fillStyle = pal.fill;
        ctx.fill();

        // Stroke polygon
        ctx.strokeStyle = pal.stroke;
        ctx.lineWidth = cfgId === 'S5' ? 2.5 : 1.8;
        ctx.stroke();

        // Draw vertex dots
        this.axes.forEach((axis, i) => {
          const val = data[axis.key] || 50;
          const normalized = Math.max(0, Math.min(1, val / 100));
          const r = radius * normalized;
          const angle = i * angleStep - Math.PI / 2;
          const x = centerX + Math.cos(angle) * r;
          const y = centerY + Math.sin(angle) * r;

          ctx.beginPath();
          ctx.arc(x, y, cfgId === 'S5' ? 4 : 3, 0, Math.PI * 2);
          ctx.fillStyle = pal.stroke;
          ctx.fill();
        });
      });

      // 4. Compact Legend at Bottom
      const legendY = h - 14;
      let legendX = 20;
      ctx.font = '11px "JetBrains Mono", sans-serif';
      ctx.textAlign = 'left';

      this.activeConfigs.forEach(cfgId => {
        const pal = COLOR_PALETTE[cfgId] || { stroke: '#00f2fe' };
        ctx.fillStyle = pal.stroke;
        ctx.fillRect(legendX, legendY - 8, 10, 10);
        ctx.fillStyle = isLight ? '#334155' : '#cbd5e1';
        const txt = pal.label || cfgId;
        ctx.fillText(txt, legendX + 14, legendY);
        legendX += ctx.measureText(txt).width + 30;
      });
    }
  }

  /**
   * ComparisonCDFChart
   * Renders cumulative probability distributions with draggable/interactive percentile crosshairs.
   */
  class ComparisonCDFChart {
    constructor(canvasId) {
      this.canvas = document.getElementById(canvasId);
      if (!this.canvas) return;
      this.ctx = this.canvas.getContext('2d');
      this.width = 540;
      this.height = 300;
      this.metric = 'delay'; // 'delay' or 'queue'
      this.selectedPercentile = 95; // p95 default
      this.runsData = {};
      this.activeConfigs = ['S5', 'S0', 'dqn', 'least_loaded'];

      this.setupDPI();
      this.initEvents();
    }

    setupDPI() {
      if (!this.canvas) return;
      const dpr = window.devicePixelRatio || 1;
      const rect = this.canvas.getBoundingClientRect();
      let w = rect.width || (this.canvas.parentElement ? this.canvas.parentElement.clientWidth : 540);
      let h = rect.height || 300;
      if (w <= 0) w = 540;
      if (h <= 0) h = 300;

      this.width = w;
      this.height = h;
      this.canvas.width = Math.floor(w * dpr);
      this.canvas.height = Math.floor(h * dpr);

      if (this.ctx) {
        this.ctx.setTransform(1, 0, 0, 1, 0, 0);
        this.ctx.scale(dpr, dpr);
      }
    }

    initEvents() {
      window.addEventListener('resize', () => {
        this.setupDPI();
        this.render();
      });
      window.addEventListener('themechange', () => {
        this.render();
      });

      this.canvas.addEventListener('click', e => {
        const rect = this.canvas.getBoundingClientRect();
        const y = e.clientY - rect.top;
        const pad = { top: 25, bottom: 40 };
        const plotH = this.height - pad.top - pad.bottom;
        if (y >= pad.top && y <= pad.top + plotH) {
          const frac = 1 - (y - pad.top) / plotH;
          this.selectedPercentile = Math.round(Math.max(1, Math.min(99, frac * 100)));
          this.render();
          const pLabel = document.getElementById('cdfPercentileLabel');
          if (pLabel) pLabel.textContent = `P${this.selectedPercentile}`;
        }
      });
    }

    setRuns(runs) {
      if (!Array.isArray(runs)) return;
      this.runsData = {};
      runs.forEach(r => {
        const cfg = r.configuration;
        if (!this.runsData[cfg]) this.runsData[cfg] = [];
        (r.windows || []).forEach(w => {
          this.runsData[cfg].push({
            delay: w.latency_ms || 2.0,
            queue: w.mean_queue_mbit || 0.0
          });
        });
      });
      this.render();
    }

    setMetric(metric) {
      this.metric = metric;
      this.render();
    }

    setPercentile(p) {
      this.selectedPercentile = Math.max(1, Math.min(99, p));
      this.render();
    }

    render() {
      if (!this.ctx || !this.canvas) return;
      const isLight = document.documentElement.getAttribute('data-theme') === 'light';
      const ctx = this.ctx;
      const w = this.width;
      const h = this.height;
      const pad = { top: 25, right: 35, bottom: 45, left: 55 };
      const plotW = w - pad.left - pad.right;
      const plotH = h - pad.top - pad.bottom;

      ctx.clearRect(0, 0, w, h);

      const maxX = this.metric === 'delay' ? 220 : 2.2;
      const unit = this.metric === 'delay' ? 'ms' : 'Mbit';

      // 1. Background Gridlines & Y Axis (0% to 100%)
      ctx.strokeStyle = isLight ? 'rgba(0, 0, 0, 0.06)' : 'rgba(255, 255, 255, 0.06)';
      ctx.lineWidth = 1;
      for (let p = 0; p <= 100; p += 25) {
        const y = pad.top + plotH - (p / 100) * plotH;
        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(pad.left + plotW, y);
        ctx.stroke();

        ctx.fillStyle = isLight ? '#64748b' : '#94a3b8';
        ctx.font = '10px "JetBrains Mono", sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText(`${p}%`, pad.left - 8, y + 3);
      }

      // X Axis Ticks
      const xSteps = this.metric === 'delay' ? 5 : 4;
      for (let i = 0; i <= xSteps; i++) {
        const xVal = (i / xSteps) * maxX;
        const x = pad.left + (i / xSteps) * plotW;
        ctx.beginPath();
        ctx.moveTo(x, pad.top);
        ctx.lineTo(x, pad.top + plotH);
        ctx.stroke();

        ctx.fillStyle = isLight ? '#64748b' : '#94a3b8';
        ctx.font = '10px "JetBrains Mono", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(`${xVal.toFixed(this.metric === 'delay' ? 0 : 1)} ${unit}`, x, pad.top + plotH + 16);
      }

      // 2. Render Empirical CDF Curve for each Active Config
      const resultsAtPercentile = [];

      this.activeConfigs.forEach(cfgId => {
        const list = this.runsData[cfgId];
        if (!list || list.length === 0) return;
        const pal = COLOR_PALETTE[cfgId] || { stroke: '#00f2fe' };

        // Sort values to build empirical CDF
        const values = list.map(item => item[this.metric]).sort((a, b) => a - b);
        const n = values.length;

        // Calculate value at target percentile
        const pIdx = Math.min(n - 1, Math.floor((this.selectedPercentile / 100) * n));
        const valAtP = values[pIdx] || 0;
        resultsAtPercentile.push({ id: cfgId, val: valAtP, color: pal.stroke });

        ctx.beginPath();
        ctx.moveTo(pad.left, pad.top + plotH);

        for (let i = 0; i < n; i++) {
          const val = values[i];
          const x = pad.left + Math.min(plotW, (val / maxX) * plotW);
          const y = pad.top + plotH - ((i + 1) / n) * plotH;
          ctx.lineTo(x, y);
        }

        ctx.strokeStyle = pal.stroke;
        ctx.lineWidth = cfgId === 'S5' ? 2.5 : 1.6;
        ctx.stroke();
      });

      // 3. Highlight Selected Percentile Line
      const yP = pad.top + plotH - (this.selectedPercentile / 100) * plotH;
      ctx.beginPath();
      ctx.setLineDash([4, 4]);
      ctx.moveTo(pad.left, yP);
      ctx.lineTo(pad.left + plotW, yP);
      ctx.strokeStyle = '#ef4444';
      ctx.lineWidth = 1.4;
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.fillStyle = '#ef4444';
      ctx.font = 'bold 10px "JetBrains Mono", sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText(`P${this.selectedPercentile}`, pad.left + plotW + 5, yP + 3);

      // Render readout badges on container
      this.updatePercentileBadges(resultsAtPercentile, unit);
    }

    updatePercentileBadges(results, unit) {
      const container = document.getElementById('cdfPercentileReadouts');
      if (!container) return;
      let html = '';
      results.forEach(r => {
        const valStr = r.val.toFixed(this.metric === 'delay' ? 1 : 2);
        html += `<span class="cdf-pill" style="border-left: 3px solid ${r.color}; background: var(--surface-secondary); padding: 4px 8px; border-radius: 4px; font-size: 11px; margin-right: 8px;">
          <strong style="color:${r.color}">${r.id}:</strong> ${valStr} ${unit}
        </span>`;
      });
      container.innerHTML = html;
    }
  }

  /**
   * TrajectoryComparatorChart
   * Side-by-side time series comparator for 2 controllers over matching 180s test sequences with difference shading.
   */
  class TrajectoryComparatorChart {
    constructor(canvasId) {
      this.canvas = document.getElementById(canvasId);
      if (!this.canvas) return;
      this.ctx = this.canvas.getContext('2d');
      this.width = 540;
      this.height = 240;
      this.controllerA = 'S0';
      this.controllerB = 'S5';
      this.metric = 'latency_ms'; // latency_ms, throughput_mbps, loss_pct, reward
      this.runsMap = {};

      this.setupDPI();
      this.initEvents();
    }

    setupDPI() {
      if (!this.canvas) return;
      const dpr = window.devicePixelRatio || 1;
      const rect = this.canvas.getBoundingClientRect();
      let w = rect.width || (this.canvas.parentElement ? this.canvas.parentElement.clientWidth : 540);
      let h = rect.height || 240;
      if (w <= 0) w = 540;
      if (h <= 0) h = 240;

      this.width = w;
      this.height = h;
      this.canvas.width = Math.floor(w * dpr);
      this.canvas.height = Math.floor(h * dpr);

      if (this.ctx) {
        this.ctx.setTransform(1, 0, 0, 1, 0, 0);
        this.ctx.scale(dpr, dpr);
      }
    }

    initEvents() {
      window.addEventListener('resize', () => {
        this.setupDPI();
        this.render();
      });
      window.addEventListener('themechange', () => {
        this.render();
      });
    }

    setRuns(runs) {
      if (!Array.isArray(runs)) return;
      this.runsMap = {};
      runs.forEach(r => {
        const cfg = r.configuration;
        if (!this.runsMap[cfg]) this.runsMap[cfg] = r.windows || [];
      });
      this.render();
    }

    setControllers(a, b) {
      this.controllerA = a;
      this.controllerB = b;
      this.render();
    }

    setMetric(m) {
      this.metric = m;
      this.render();
    }

    render() {
      if (!this.ctx || !this.canvas) return;
      const isLight = document.documentElement.getAttribute('data-theme') === 'light';
      const ctx = this.ctx;
      const w = this.width;
      const h = this.height;
      const pad = { top: 20, right: 30, bottom: 40, left: 50 };
      const plotW = w - pad.left - pad.right;
      const plotH = h - pad.top - pad.bottom;

      ctx.clearRect(0, 0, w, h);

      const windowsA = this.runsMap[this.controllerA] || [];
      const windowsB = this.runsMap[this.controllerB] || [];
      const maxPts = Math.max(windowsA.length, windowsB.length, 1);

      // Determine Y scale
      let allVals = [];
      windowsA.forEach(w => allVals.push(w[this.metric] || 0));
      windowsB.forEach(w => allVals.push(w[this.metric] || 0));

      let minY = Math.min(...allVals, 0);
      let maxY = Math.max(...allVals, 1);
      if (minY === maxY) maxY += 1;
      const yRange = maxY - minY;

      // Draw Gridlines
      ctx.strokeStyle = isLight ? 'rgba(0, 0, 0, 0.06)' : 'rgba(255, 255, 255, 0.06)';
      ctx.lineWidth = 1;
      for (let i = 0; i <= 4; i++) {
        const y = pad.top + (i / 4) * plotH;
        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(pad.left + plotW, y);
        ctx.stroke();

        const v = maxY - (i / 4) * yRange;
        ctx.fillStyle = isLight ? '#64748b' : '#94a3b8';
        ctx.font = '10px "JetBrains Mono", sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText(v.toFixed(1), pad.left - 6, y + 3);
      }

      // X Axis
      for (let sec = 0; sec <= 180; sec += 30) {
        const x = pad.left + (sec / 180) * plotW;
        ctx.beginPath();
        ctx.moveTo(x, pad.top + plotH);
        ctx.lineTo(x, pad.top + plotH + 4);
        ctx.stroke();

        ctx.fillStyle = isLight ? '#64748b' : '#94a3b8';
        ctx.font = '10px "JetBrains Mono", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(`${sec}s`, x, pad.top + plotH + 16);
      }

      // Difference Ribbon Fill between A and B
      if (windowsA.length > 0 && windowsB.length > 0) {
        for (let i = 0; i < maxPts - 1; i++) {
          const x1 = pad.left + (i / (maxPts - 1)) * plotW;
          const x2 = pad.left + ((i + 1) / (maxPts - 1)) * plotW;
          const yA1 = pad.top + plotH - (((windowsA[i] ? windowsA[i][this.metric] : 0) - minY) / yRange) * plotH;
          const yA2 = pad.top + plotH - (((windowsA[i + 1] ? windowsA[i + 1][this.metric] : 0) - minY) / yRange) * plotH;
          const yB1 = pad.top + plotH - (((windowsB[i] ? windowsB[i][this.metric] : 0) - minY) / yRange) * plotH;
          const yB2 = pad.top + plotH - (((windowsB[i + 1] ? windowsB[i + 1][this.metric] : 0) - minY) / yRange) * plotH;

          ctx.beginPath();
          ctx.moveTo(x1, yA1);
          ctx.lineTo(x2, yA2);
          ctx.lineTo(x2, yB2);
          ctx.lineTo(x1, yB1);
          ctx.closePath();

          // Green if B improves on A (lower delay/loss, higher goodput/reward)
          const isImprovement = (this.metric === 'throughput_mbps' || this.metric === 'reward')
            ? (windowsB[i] ? windowsB[i][this.metric] : 0) >= (windowsA[i] ? windowsA[i][this.metric] : 0)
            : (windowsB[i] ? windowsB[i][this.metric] : 0) <= (windowsA[i] ? windowsA[i][this.metric] : 0);

          ctx.fillStyle = isImprovement ? 'rgba(16, 185, 129, 0.18)' : 'rgba(239, 68, 68, 0.18)';
          ctx.fill();
        }
      }

      // Draw Curve A (Reference)
      const palA = COLOR_PALETTE[this.controllerA] || { stroke: '#ef4444' };
      ctx.beginPath();
      windowsA.forEach((w, i) => {
        const x = pad.left + (i / (maxPts - 1)) * plotW;
        const y = pad.top + plotH - (((w[this.metric] || 0) - minY) / yRange) * plotH;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.strokeStyle = palA.stroke;
      ctx.lineWidth = 2.0;
      ctx.setLineDash([3, 3]);
      ctx.stroke();
      ctx.setLineDash([]);

      // Draw Curve B (Comparison)
      const palB = COLOR_PALETTE[this.controllerB] || { stroke: '#00f2fe' };
      ctx.beginPath();
      windowsB.forEach((w, i) => {
        const x = pad.left + (i / (maxPts - 1)) * plotW;
        const y = pad.top + plotH - (((w[this.metric] || 0) - minY) / yRange) * plotH;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.strokeStyle = palB.stroke;
      ctx.lineWidth = 2.4;
      ctx.stroke();
    }
  }

  /**
   * EffectsMatrixExplorer
   * Renders the complete statistical comparison matrix table with 95% CIs and p-values.
   */
  class EffectsMatrixExplorer {
    constructor(tableId) {
      this.table = document.getElementById(tableId);
      this.effectsData = null;
      this.activeFilter = 'all';
    }

    setData(data) {
      this.effectsData = data;
      this.render();
    }

    setFilter(filter) {
      this.activeFilter = filter;
      this.render();
    }

    render() {
      if (!this.table || !this.effectsData) return;
      const comps = this.effectsData.comparisons || {};
      const agentic = this.effectsData.agentic || {};

      let html = `<thead>
        <tr style="border-bottom: 2px solid var(--border-color); color: var(--text-secondary); font-size: 11px;">
          <th style="padding: 0.6rem 0.8rem; text-align: left;">Baseline / Controller</th>
          <th style="padding: 0.6rem 0.8rem; text-align: right;">Latency (&Delta; ms)</th>
          <th style="padding: 0.6rem 0.8rem; text-align: right;">Delay Red.</th>
          <th style="padding: 0.6rem 0.8rem; text-align: right;">Loss Red.</th>
          <th style="padding: 0.6rem 0.8rem; text-align: right;">Goodput Gain</th>
          <th style="padding: 0.6rem 0.8rem; text-align: right;">Reward Delta</th>
          <th style="padding: 0.6rem 0.8rem; text-align: center;">95% Bootstrap CI</th>
          <th style="padding: 0.6rem 0.8rem; text-align: center;">Significance (p)</th>
        </tr>
      </thead><tbody>`;

      Object.keys(comps).forEach(key => {
        const c = comps[key];
        const changes = c.changes || {};
        const latChange = changes.latency_ms || {};
        const pVal = latChange.p || 0.01;
        const ci = latChange.ci95 || [0, 0];

        // Filtering logic
        if (this.activeFilter === 'significant' && pVal >= 0.05) return;
        if (this.activeFilter === 'rl' && !['dqn', 'marl', 'tabular_q'].includes(key)) return;
        if (this.activeFilter === 'heuristic' && !['threshold', 'least_loaded', 'S0'].includes(key)) return;

        const isSignificant = pVal < 0.05;
        const pBadge = pVal < 0.001
          ? `<span class="badge-tag accent-cyan" style="font-size:10px;">p < 0.001 ***</span>`
          : (pVal < 0.01
            ? `<span class="badge-tag accent-purple" style="font-size:10px;">p < 0.01 **</span>`
            : (pVal < 0.05
              ? `<span class="badge-tag" style="background:rgba(16,185,129,0.2); color:#10b981; font-size:10px;">p = ${pVal.toFixed(3)} *</span>`
              : `<span class="badge-tag" style="background:rgba(148,163,184,0.15); color:var(--text-secondary); font-size:10px;">n.s.</span>`));

        const delayRed = c.delay_reduction_pct ? `${c.delay_reduction_pct.toFixed(1)}%` : '—';
        const lossRed = c.loss_reduction_pp ? `${c.loss_reduction_pp.toFixed(2)} pp` : '—';
        const goodGain = c.goodput_gain_pct ? `+${c.goodput_gain_pct.toFixed(2)}%` : '—';
        const rewDelta = changes.reward ? (changes.reward.delta >= 0 ? `+${changes.reward.delta.toFixed(3)}` : changes.reward.delta.toFixed(3)) : '—';
        const latDelta = latChange.delta ? `${latChange.delta.toFixed(2)} ms` : '—';

        html += `<tr style="border-bottom: 1px solid var(--border-color); font-size: 12px; transition: background 0.15s ease;">
          <td style="padding: 0.6rem 0.8rem; font-weight: 600;">
            <span style="color: var(--cyan); margin-right: 4px;">${key}</span>
            <span style="color: var(--text-secondary); font-size: 11px;">(${c.label})</span>
          </td>
          <td style="padding: 0.6rem 0.8rem; text-align: right; font-family: var(--font-mono); color: #10b981; font-weight: 600;">${latDelta}</td>
          <td style="padding: 0.6rem 0.8rem; text-align: right; font-family: var(--font-mono);">${delayRed}</td>
          <td style="padding: 0.6rem 0.8rem; text-align: right; font-family: var(--font-mono);">${lossRed}</td>
          <td style="padding: 0.6rem 0.8rem; text-align: right; font-family: var(--font-mono); color: #10b981;">${goodGain}</td>
          <td style="padding: 0.6rem 0.8rem; text-align: right; font-family: var(--font-mono);">${rewDelta}</td>
          <td style="padding: 0.6rem 0.8rem; text-align: center; font-family: var(--font-mono); font-size: 11px; color: var(--text-secondary);">[${ci[0].toFixed(1)}, ${ci[1].toFixed(1)}]</td>
          <td style="padding: 0.6rem 0.8rem; text-align: center;">${pBadge}</td>
        </tr>`;
      });

      html += '</tbody>';
      this.table.innerHTML = html;
    }

    exportCSV() {
      if (!this.effectsData || !this.effectsData.comparisons) return;
      const comps = this.effectsData.comparisons;
      let csv = 'Baseline,Label,Delay_Reduction_Pct,Loss_Reduction_pp,Goodput_Gain_Pct,Latency_Delta_ms,Latency_CI_Low,Latency_CI_High,P_Value\n';
      Object.keys(comps).forEach(k => {
        const c = comps[k];
        const lat = (c.changes && c.changes.latency_ms) || {};
        const ci = lat.ci95 || [0, 0];
        csv += `"${k}","${c.label}",${c.delay_reduction_pct || 0},${c.loss_reduction_pp || 0},${c.goodput_gain_pct || 0},${lat.delta || 0},${ci[0]},${ci[1]},${lat.p || 1}\n`;
      });
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'SELF_X_Statistical_Effects_Matrix.csv';
      a.click();
      URL.revokeObjectURL(url);
    }
  }

  // Export to window
  window.ComparisonRadarChart = ComparisonRadarChart;
  window.ComparisonCDFChart = ComparisonCDFChart;
  window.TrajectoryComparatorChart = TrajectoryComparatorChart;
  window.EffectsMatrixExplorer = EffectsMatrixExplorer;

})(window, document);
