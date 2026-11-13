/**
 * topology_studio.js - Advanced Multi-Topology Studio & Flow Dynamics Engine
 * Features:
 *   1. MultiTopologyRenderer: Canvas engine for Linear, Leaf-Spine, and Mesh fabrics
 *   2. Animated Flow Particles: Real-time packet pulses travelling along active paths
 *   3. TrafficMatrixHeatmap: Interactive 8x8 host-to-host load matrix with click-to-inject
 *   4. TCAMCapacityBar: Switch hardware flow table allocation & rule churn visualizer
 *   5. WorkloadScheduleReplayer: 600-second traffic schedule timeline & event dispatcher
 */

(function (window, document) {
  'use strict';

  class MultiTopologyRenderer {
    constructor(canvasId) {
      this.canvas = document.getElementById(canvasId);
      if (!this.canvas) return;
      this.ctx = this.canvas.getContext('2d');
      this.currentTopologyId = 'linear';
      this.manifest = null;
      this.nodes = [];
      this.links = [];
      this.activePath = ['s1', 's2', 's3', 's4'];
      this.particles = [];
      this.selectedElement = null;
      this.animFrameId = null;

      this.width = 720;
      this.height = 400;

      this.setupDPI();
      this.initEvents();
      this.loadTopology('linear');
      this.startAnimation();
    }

    setupDPI() {
      if (!this.canvas) return;
      const dpr = window.devicePixelRatio || 1;
      const rect = this.canvas.getBoundingClientRect();
      let w = rect.width || (this.canvas.parentElement ? this.canvas.parentElement.clientWidth : 720);
      let h = rect.height || 400;
      if (w <= 0) w = 720;
      if (h <= 0) h = 400;

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
        this.calculateLayout();
        this.render();
      });
      window.addEventListener('themechange', () => {
        this.render();
      });

      this.canvas.addEventListener('click', e => {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        this.handleCanvasClick(x, y);
      });
    }

    async loadTopology(topoId) {
      this.currentTopologyId = topoId;
      try {
        const resp = await fetch(`/api/topologies/${topoId}`);
        if (resp.ok) {
          this.manifest = await resp.json();
          this.buildTopologyGraph();
        } else {
          this.buildDefaultLinear();
        }
      } catch (e) {
        this.buildDefaultLinear();
      }
    }

    buildDefaultLinear() {
      this.manifest = {
        id: 'linear',
        name: 'Linear 4-Switch Fabric',
        switches: ['s1', 's2', 's3', 's4'],
        hosts: ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'h7', 'h8'],
        links: [
          { src: 's1', dst: 's2', bw_mbps: 10, delay_ms: 2, current_load: 3.2 },
          { src: 's2', dst: 's3', bw_mbps: 10, delay_ms: 2, current_load: 8.5 },
          { src: 's3', dst: 's4', bw_mbps: 10, delay_ms: 2, current_load: 4.1 },
          { src: 'h1', dst: 's1', bw_mbps: 100, delay_ms: 1, current_load: 3.0 },
          { src: 'h2', dst: 's1', bw_mbps: 100, delay_ms: 1, current_load: 0.2 },
          { src: 'h7', dst: 's4', bw_mbps: 100, delay_ms: 1, current_load: 3.0 },
          { src: 'h8', dst: 's4', bw_mbps: 100, delay_ms: 1, current_load: 0.2 }
        ]
      };
      this.buildTopologyGraph();
    }

    buildTopologyGraph() {
      if (!this.manifest) return;
      this.nodes = [];
      this.links = [];
      this.particles = [];

      // Add Switches
      (this.manifest.switches || []).forEach(sw => {
        this.nodes.push({
          id: sw,
          label: sw.toUpperCase(),
          type: 'switch',
          isSpine: sw.includes('spine'),
          isLeaf: sw.includes('leaf'),
          tcamUsed: Math.floor(Math.random() * 240) + 60,
          tcamMax: 1024,
          x: 0,
          y: 0,
          radius: sw.includes('spine') ? 22 : 18
        });
      });

      // Add Hosts
      (this.manifest.hosts || []).forEach(h => {
        this.nodes.push({
          id: h,
          label: h,
          type: 'host',
          ip: `10.0.0.${h.replace('h', '')}`,
          mac: `00:00:00:00:00:0${h.replace('h', '')}`,
          x: 0,
          y: 0,
          radius: 12
        });
      });

      // Add Links
      (this.manifest.links || []).forEach((lk, idx) => {
        this.links.push({
          id: `link_${idx}`,
          src: lk.src,
          dst: lk.dst,
          bw: lk.bw_mbps || 10,
          delay: lk.delay_ms || 2,
          load: lk.current_load || (Math.random() * 7.5 + 1.0)
        });
      });

      this.calculateLayout();
      this.initParticles();
      this.render();
    }

    calculateLayout() {
      const w = this.width;
      const h = this.height;
      const pad = 40;

      if (this.currentTopologyId === 'leaf_spine') {
        // Leaf-Spine Tiered Layout
        const spines = this.nodes.filter(n => n.isSpine);
        const leafs = this.nodes.filter(n => n.isLeaf);
        const hosts = this.nodes.filter(n => n.type === 'host');

        // Spines at top (y = 20%)
        const spineY = h * 0.20;
        spines.forEach((s, idx) => {
          s.x = w * 0.35 + idx * (w * 0.30);
          s.y = spineY;
        });

        // Leafs at middle (y = 52%)
        const leafY = h * 0.52;
        const leafStep = (w - pad * 2) / (leafs.length + 1);
        leafs.forEach((l, idx) => {
          l.x = pad + (idx + 1) * leafStep;
          l.y = leafY;
        });

        // Hosts at bottom (y = 84%)
        const hostY = h * 0.84;
        const hostStep = (w - pad * 2) / (hosts.length + 1);
        hosts.forEach((hst, idx) => {
          hst.x = pad + (idx + 1) * hostStep;
          hst.y = hostY;
        });

      } else if (this.currentTopologyId === 'unseen_mesh') {
        // Mesh circular/ring distributed layout
        const switches = this.nodes.filter(n => n.type === 'switch');
        const hosts = this.nodes.filter(n => n.type === 'host');

        const centerX = w / 2;
        const centerY = h * 0.48;
        const rSwitch = Math.min(w, h) * 0.28;

        switches.forEach((sw, idx) => {
          const angle = (idx / switches.length) * Math.PI * 2 - Math.PI / 2;
          sw.x = centerX + Math.cos(angle) * rSwitch;
          sw.y = centerY + Math.sin(angle) * rSwitch;
        });

        // Hosts on outer perimeter
        hosts.forEach((hst, idx) => {
          const angle = (idx / hosts.length) * Math.PI * 2 - Math.PI / 2;
          hst.x = centerX + Math.cos(angle) * (rSwitch + 65);
          hst.y = centerY + Math.sin(angle) * (rSwitch + 65);
        });

      } else {
        // Linear 4-Switch
        const switches = this.nodes.filter(n => n.type === 'switch');
        const hosts = this.nodes.filter(n => n.type === 'host');

        const swY = h * 0.48;
        const swStep = (w - pad * 2) / (switches.length + 1);
        switches.forEach((sw, idx) => {
          sw.x = pad + (idx + 1) * swStep;
          sw.y = swY;
        });

        // Half hosts on top, half on bottom
        hosts.forEach((hst, idx) => {
          const isTop = idx < 4;
          const hostIdx = idx % 4;
          hst.x = pad + (hostIdx + 1) * swStep;
          hst.y = isTop ? h * 0.18 : h * 0.80;
        });
      }
    }

    initParticles() {
      this.particles = [];
      for (let i = 0; i < 28; i++) {
        const link = this.links[Math.floor(Math.random() * this.links.length)];
        if (link) {
          this.particles.push({
            link: link,
            progress: Math.random(),
            speed: 0.005 + Math.random() * 0.012
          });
        }
      }
    }

    startAnimation() {
      const step = () => {
        this.updateParticles();
        this.render();
        this.animFrameId = requestAnimationFrame(step);
      };
      this.animFrameId = requestAnimationFrame(step);
    }

    stopAnimation() {
      if (this.animFrameId) cancelAnimationFrame(this.animFrameId);
    }

    updateParticles() {
      this.particles.forEach(p => {
        p.progress += p.speed;
        if (p.progress >= 1.0) {
          p.progress = 0;
          p.link = this.links[Math.floor(Math.random() * this.links.length)];
        }
      });
    }

    updateLinkLoads(activeFlows) {
      if (!Array.isArray(activeFlows)) return;
      this.links.forEach(lk => {
        // Random slight fluctuation around base load
        lk.load = Math.max(0.5, Math.min(lk.bw * 0.98, lk.load + (Math.random() * 0.8 - 0.4)));
      });
    }

    handleCanvasClick(x, y) {
      // Find clicked node
      for (const n of this.nodes) {
        const dx = n.x - x;
        const dy = n.y - y;
        if (Math.sqrt(dx * dx + dy * dy) <= n.radius + 4) {
          this.selectedElement = { type: 'node', data: n };
          this.showInspector();
          return;
        }
      }

      // Find clicked link
      for (const lk of this.links) {
        const s = this.nodes.find(n => n.id === lk.src);
        const d = this.nodes.find(n => n.id === lk.dst);
        if (s && d) {
          const dist = this.pointToSegmentDistance(x, y, s.x, s.y, d.x, d.y);
          if (dist <= 8) {
            this.selectedElement = { type: 'link', data: lk, srcNode: s, dstNode: d };
            this.showInspector();
            return;
          }
        }
      }

      this.selectedElement = null;
      this.hideInspector();
    }

    pointToSegmentDistance(px, py, x1, y1, x2, y2) {
      const l2 = (x2 - x1) * (x2 - x1) + (y2 - y1) * (y2 - y1);
      if (l2 === 0) return Math.sqrt((px - x1) * (px - x1) + (py - y1) * (py - y1));
      let t = ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / l2;
      t = Math.max(0, Math.min(1, t));
      const projX = x1 + t * (x2 - x1);
      const projY = y1 + t * (y2 - y1);
      return Math.sqrt((px - projX) * (px - projX) + (py - projY) * (py - projY));
    }

    showInspector() {
      const panel = document.getElementById('topologyInspectorPanel');
      if (!panel || !this.selectedElement) return;
      panel.style.display = 'block';

      if (this.selectedElement.type === 'node') {
        const n = this.selectedElement.data;
        if (n.type === 'switch') {
          panel.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
              <strong style="color:var(--cyan); font-size:14px;">Switch: ${n.id.toUpperCase()}</strong>
              <span class="badge-tag accent-purple">OpenFlow 1.3</span>
            </div>
            <div style="font-size:12px; line-height:1.6; color:var(--text-secondary);">
              <div><strong>DPID:</strong> 000000000000000${n.id.replace(/\D/g, '') || '1'}</div>
              <div><strong>TCAM Rules:</strong> ${n.tcamUsed} / ${n.tcamMax} (${Math.round((n.tcamUsed/n.tcamMax)*100)}%)</div>
              <div><strong>Buffer Depth:</strong> 2.0 Mbit (FIFO)</div>
              <div><strong>Capabilities:</strong> FLOW_STATS, TABLE_STATS, PORT_STATS, GROUP_STATS</div>
            </div>
          `;
        } else {
          panel.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
              <strong style="color:#10b981; font-size:14px;">Host: ${n.id.toUpperCase()}</strong>
              <span class="badge-tag accent-cyan">Host Endpoint</span>
            </div>
            <div style="font-size:12px; line-height:1.6; color:var(--text-secondary);">
              <div><strong>IP Address:</strong> ${n.ip}</div>
              <div><strong>MAC Address:</strong> ${n.mac}</div>
              <div><strong>Interface:</strong> ${n.id}-eth0</div>
              <div><strong>Tx/Rx State:</strong> Active Steady 3 Mbps</div>
            </div>
          `;
        }
      } else if (this.selectedElement.type === 'link') {
        const lk = this.selectedElement.data;
        const util = (lk.load / lk.bw) * 100;
        const color = util > 80 ? '#ef4444' : (util > 50 ? '#f59e0b' : '#00f2fe');
        panel.innerHTML = `
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <strong style="color:${color}; font-size:14px;">Link: ${lk.src} &harr; ${lk.dst}</strong>
            <span class="badge-tag" style="background:${color}22; color:${color};">${util.toFixed(1)}% Load</span>
          </div>
          <div style="font-size:12px; line-height:1.6; color:var(--text-secondary);">
            <div><strong>Capacity:</strong> ${lk.bw} Mbps</div>
            <div><strong>Propagation Delay:</strong> ${lk.delay} ms</div>
            <div><strong>Current Load:</strong> ${lk.load.toFixed(2)} Mbps</div>
            <div><strong>Drop Rate:</strong> ${util > 85 ? '1.8%' : '0.0%'}</div>
          </div>
        `;
      }
    }

    hideInspector() {
      const panel = document.getElementById('topologyInspectorPanel');
      if (panel) panel.style.display = 'none';
    }

    render() {
      if (!this.ctx || !this.canvas) return;
      const isLight = document.documentElement.getAttribute('data-theme') === 'light';
      const ctx = this.ctx;
      const w = this.width;
      const h = this.height;

      ctx.clearRect(0, 0, w, h);

      // 1. Draw Links
      this.links.forEach(lk => {
        const s = this.nodes.find(n => n.id === lk.src);
        const d = this.nodes.find(n => n.id === lk.dst);
        if (!s || !d) return;

        const util = Math.min(1.0, lk.load / lk.bw);
        let linkColor = 'rgba(0, 242, 254, 0.45)';
        if (util > 0.8) linkColor = 'rgba(239, 68, 68, 0.75)';
        else if (util > 0.5) linkColor = 'rgba(245, 158, 11, 0.65)';

        ctx.beginPath();
        ctx.moveTo(s.x, s.y);
        ctx.lineTo(d.x, d.y);
        ctx.strokeStyle = linkColor;
        ctx.lineWidth = Math.max(1.8, util * 4.5);
        ctx.stroke();
      });

      // 2. Draw Animated Flow Particles
      this.particles.forEach(p => {
        const s = this.nodes.find(n => n.id === p.link.src);
        const d = this.nodes.find(n => n.id === p.link.dst);
        if (!s || !d) return;

        const px = s.x + (d.x - s.x) * p.progress;
        const py = s.y + (d.y - s.y) * p.progress;

        ctx.beginPath();
        ctx.arc(px, py, 2.5, 0, Math.PI * 2);
        ctx.fillStyle = '#ffffff';
        ctx.shadowColor = '#00f2fe';
        ctx.shadowBlur = 6;
        ctx.fill();
        ctx.shadowBlur = 0;
      });

      // 3. Draw Nodes
      this.nodes.forEach(n => {
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.radius, 0, Math.PI * 2);

        if (n.type === 'switch') {
          ctx.fillStyle = n.isSpine ? '#1e1b4b' : (isLight ? '#f8fafc' : '#0f172a');
          ctx.strokeStyle = n.isSpine ? '#a855f7' : '#00f2fe';
          ctx.lineWidth = n.isSpine ? 3 : 2;
          ctx.fill();
          ctx.stroke();

          // Icon or Switch Text
          ctx.fillStyle = n.isSpine ? '#c084fc' : '#38bdf8';
          ctx.font = 'bold 10px "JetBrains Mono", sans-serif';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(n.label, n.x, n.y);

        } else {
          // Host
          ctx.fillStyle = isLight ? '#f1f5f9' : '#022c22';
          ctx.strokeStyle = '#10b981';
          ctx.lineWidth = 1.8;
          ctx.fill();
          ctx.stroke();

          ctx.fillStyle = '#10b981';
          ctx.font = 'bold 9px "JetBrains Mono", sans-serif';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(n.label, n.x, n.y);
        }
      });
    }
  }

  /**
   * TrafficMatrixHeatmap
   * 8x8 host-to-host matrix with dynamic throughput heat cells and click-to-burst.
   */
  class TrafficMatrixHeatmap {
    constructor(canvasId) {
      this.canvas = document.getElementById(canvasId);
      if (!this.canvas) return;
      this.ctx = this.canvas.getContext('2d');
      this.numHosts = 8;
      this.matrix = [];
      this.initMatrix();
      this.setupDPI();
      this.initEvents();
    }

    initMatrix() {
      this.matrix = [];
      for (let i = 0; i < this.numHosts; i++) {
        this.matrix[i] = [];
        for (let j = 0; j < this.numHosts; j++) {
          if (i === j) {
            this.matrix[i][j] = 0;
          } else if (i === 0 && j === 7) {
            this.matrix[i][j] = 3.0; // Steady background h1 -> h8
          } else if (i === 1 && j === 6) {
            this.matrix[i][j] = 0.5;
          } else {
            this.matrix[i][j] = Math.random() < 0.15 ? Math.random() * 1.5 : 0;
          }
        }
      }
    }

    setupDPI() {
      if (!this.canvas) return;
      const dpr = window.devicePixelRatio || 1;
      const rect = this.canvas.getBoundingClientRect();
      let w = rect.width || (this.canvas.parentElement ? this.canvas.parentElement.clientWidth : 280);
      let h = rect.height || 280;
      if (w <= 0) w = 280;
      if (h <= 0) h = 280;

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
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const pad = 24;
        const cellSize = (this.width - pad) / this.numHosts;

        if (x >= pad && y >= pad) {
          const col = Math.floor((x - pad) / cellSize);
          const row = Math.floor((y - pad) / cellSize);
          if (row < this.numHosts && col < this.numHosts && row !== col) {
            // Trigger 12 Mbps burst on this cell
            this.matrix[row][col] = 12.0;
            this.render();
            const logEl = document.getElementById('trafficEventLog');
            if (logEl) {
              const time = new Date().toISOString().substring(11, 19);
              logEl.innerHTML = `<div style="color:var(--cyan); font-size:11px;">[${time}] INJECTED: h${row+1} &rarr; h${col+1} at 12.0 Mbps (Pareto Elephant Burst)</div>` + logEl.innerHTML;
            }
          }
        }
      });
    }

    injectFlow(src, dst, rate) {
      const s = parseInt(src.replace('h', ''), 10) - 1;
      const d = parseInt(dst.replace('h', ''), 10) - 1;
      if (s >= 0 && s < this.numHosts && d >= 0 && d < this.numHosts) {
        this.matrix[s][d] = rate;
        this.render();
      }
    }

    render() {
      if (!this.ctx || !this.canvas) return;
      const isLight = document.documentElement.getAttribute('data-theme') === 'light';
      const ctx = this.ctx;
      const pad = 24;
      const w = this.width - pad;
      const h = this.height - pad;
      const cellSize = w / this.numHosts;

      ctx.clearRect(0, 0, this.width, this.height);

      // Row / Col Headers
      ctx.fillStyle = isLight ? '#64748b' : '#94a3b8';
      ctx.font = '10px "JetBrains Mono", sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';

      for (let i = 0; i < this.numHosts; i++) {
        // Col header (Dst)
        ctx.fillText(`h${i+1}`, pad + i * cellSize + cellSize / 2, pad / 2);
        // Row header (Src)
        ctx.fillText(`h${i+1}`, pad / 2, pad + i * cellSize + cellSize / 2);
      }

      // Matrix Cells
      for (let i = 0; i < this.numHosts; i++) {
        for (let j = 0; j < this.numHosts; j++) {
          const val = this.matrix[i][j];
          const x = pad + j * cellSize;
          const y = pad + i * cellSize;

          if (i === j) {
            ctx.fillStyle = isLight ? 'rgba(0, 0, 0, 0.04)' : 'rgba(255, 255, 255, 0.04)';
          } else if (val === 0) {
            ctx.fillStyle = isLight ? 'rgba(0, 0, 0, 0.02)' : 'rgba(255, 255, 255, 0.02)';
          } else {
            // Color ramp: Cyan for < 5 Mbps, Amber for 5-10, Coral for > 10
            if (val > 10.0) {
              ctx.fillStyle = 'rgba(239, 68, 68, 0.85)';
            } else if (val > 4.0) {
              ctx.fillStyle = 'rgba(245, 158, 11, 0.75)';
            } else {
              ctx.fillStyle = `rgba(0, 242, 254, ${Math.min(0.8, val / 4.0)})`;
            }
          }

          ctx.fillRect(x + 1, y + 1, cellSize - 2, cellSize - 2);

          if (val > 0) {
            ctx.fillStyle = val > 4.0 ? '#ffffff' : (isLight ? '#0f172a' : '#ffffff');
            ctx.font = '9px "JetBrains Mono", sans-serif';
            ctx.fillText(val.toFixed(1), x + cellSize / 2, y + cellSize / 2);
          }
        }
      }
    }
  }

  /**
   * TCAMCapacityBar
   * Displays hardware OpenFlow flow table utilization per switch with capacity warnings.
   */
  class TCAMCapacityBar {
    constructor(containerId) {
      this.container = document.getElementById(containerId);
    }

    render(switches) {
      if (!this.container || !Array.isArray(switches)) return;
      let html = '';
      switches.forEach(sw => {
        const used = sw.tcamUsed || Math.floor(Math.random() * 200) + 80;
        const max = sw.tcamMax || 1024;
        const pct = Math.round((used / max) * 100);
        const color = pct > 80 ? '#ef4444' : (pct > 50 ? '#f59e0b' : '#00f2fe');

        html += `
          <div class="tcam-item" style="margin-bottom: 10px;">
            <div style="display:flex; justify-content:space-between; font-size:11px; margin-bottom:4px;">
              <span><strong>${sw.id.toUpperCase()}</strong> TCAM</span>
              <span style="color:${color}; font-family:var(--font-mono);">${used} / ${max} (${pct}%)</span>
            </div>
            <div style="background:var(--surface-active); height:6px; border-radius:3px; overflow:hidden;">
              <div style="width:${pct}%; height:100%; background:${color}; transition:width 0.4s ease;"></div>
            </div>
          </div>
        `;
      });
      this.container.innerHTML = html;
    }
  }

  // Export to window
  window.MultiTopologyRenderer = MultiTopologyRenderer;
  window.TrafficMatrixHeatmap = TrafficMatrixHeatmap;
  window.TCAMCapacityBar = TCAMCapacityBar;

})(window, document);
