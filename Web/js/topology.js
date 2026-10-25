/**
 * topology.js - Interactive HTML5 Canvas Network Topology Visualizer
 * Renders OpenFlow 1.3 switches (s1..s4), hosts (h1..h8), dual-bottleneck links,
 * animated particle comet trails, cyber-grid radar background, and live node tooltips.
 */

class TopologyVisualizer {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');

    this.width = this.canvas.width;
    this.height = this.canvas.height;
    this.animTime = 0;

    // High DPI scaling
    this.setupDPI();

    // Node layout definitions
    this.nodes = {
      // Switches (Linear chain s1 - s2 - s3 - s4)
      s1: { id: 's1', type: 'switch', label: 's1', x: 200, y: 260, dpid: '0000000000000001', rx: 4.2, tx: 4.2, flows: 2 },
      s2: { id: 's2', type: 'switch', label: 's2', x: 400, y: 260, dpid: '0000000000000002', rx: 7.8, tx: 7.8, flows: 4 },
      s3: { id: 's3', type: 'switch', label: 's3', x: 620, y: 260, dpid: '0000000000000003', rx: 7.8, tx: 7.8, flows: 4 },
      s4: { id: 's4', type: 'switch', label: 's4', x: 820, y: 260, dpid: '0000000000000004', rx: 4.2, tx: 4.2, flows: 2 },

      // Hosts (2 per switch)
      h1: { id: 'h1', type: 'host', label: 'h1', x: 130, y: 140, ip: '10.0.0.1', mac: '00:00:00:00:00:01' },
      h2: { id: 'h2', type: 'host', label: 'h2', x: 130, y: 380, ip: '10.0.0.2', mac: '00:00:00:00:00:02' },

      h3: { id: 'h3', type: 'host', label: 'h3', x: 400, y: 110, ip: '10.0.0.3', mac: '00:00:00:00:00:03' },
      h4: { id: 'h4', type: 'host', label: 'h4', x: 400, y: 410, ip: '10.0.0.4', mac: '00:00:00:00:00:04' },

      h5: { id: 'h5', type: 'host', label: 'h5', x: 620, y: 110, ip: '10.0.0.5', mac: '00:00:00:00:00:05' },
      h6: { id: 'h6', type: 'host', label: 'h6', x: 620, y: 410, ip: '10.0.0.6', mac: '00:00:00:00:00:06' },

      h7: { id: 'h7', type: 'host', label: 'h7', x: 890, y: 140, ip: '10.0.0.7', mac: '00:00:00:00:00:07' },
      h8: { id: 'h8', type: 'host', label: 'h8', x: 890, y: 380, ip: '10.0.0.8', mac: '00:00:00:00:00:08' },
    };

    // Links definition
    this.links = [
      // Host links
      { from: 'h1', to: 's1', bw: 100, util: 30, color: 'rgba(255, 255, 255, 0.12)' },
      { from: 'h2', to: 's1', bw: 100, util: 60, color: 'rgba(255, 255, 255, 0.12)' },
      { from: 'h3', to: 's2', bw: 100, util: 5, color: 'rgba(255, 255, 255, 0.12)' },
      { from: 'h4', to: 's2', bw: 100, util: 5, color: 'rgba(255, 255, 255, 0.12)' },
      { from: 'h5', to: 's3', bw: 100, util: 5, color: 'rgba(255, 255, 255, 0.12)' },
      { from: 'h6', to: 's3', bw: 100, util: 5, color: 'rgba(255, 255, 255, 0.12)' },
      { from: 'h7', to: 's4', bw: 100, util: 30, color: 'rgba(255, 255, 255, 0.12)' },
      { from: 'h8', to: 's4', bw: 100, util: 60, color: 'rgba(255, 255, 255, 0.12)' },

      // Inter-switch trunks
      { from: 's1', to: 's2', bw: 20, util: 45, type: 'trunk', label: '20 Mbps (2ms)' },
      { from: 's3', to: 's4', bw: 20, util: 45, type: 'trunk', label: '20 Mbps (2ms)' },

      // Core bottleneck dual links between s2 and s3
      { 
        id: 'core-primary', 
        from: 's2', 
        to: 's3', 
        bw: 10, 
        util: 48, 
        curvature: -35, 
        type: 'primary', 
        label: 'Primary: 10M, 5ms (Port 3)' 
      },
      { 
        id: 'core-secondary', 
        from: 's2', 
        to: 's3', 
        bw: 10, 
        util: 52, 
        curvature: 35, 
        type: 'secondary', 
        label: 'Secondary: 10M, 12ms (Port 4)' 
      }
    ];

    // Packet flow particles
    this.particles = [];
    this.selectedNode = this.nodes.s2;
    this.hoveredNode = null;
    this.mousePos = { x: 0, y: 0 };
    this.isElephantRerouted = true;
    this.isElephantActive = true;
    this.isSteadyActive = true;

    this.initEvents();
    this.initParticles();
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  setupDPI() {
    const dpr = window.devicePixelRatio || 1;
    const rect = this.canvas.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return;
    this.canvas.width = rect.width * dpr;
    this.canvas.height = rect.height * dpr;
    this.dpr = dpr;
    this.scale = Math.min(rect.width / 980, rect.height / 520);
    this.offsetX = (rect.width - 980 * this.scale) / 2;
    this.offsetY = (rect.height - 520 * this.scale) / 2;
    this.width = rect.width;
    this.height = rect.height;
  }

  initEvents() {
    window.addEventListener('resize', () => this.setupDPI());
    window.addEventListener('themechange', () => this.setupDPI());

    this.canvas.addEventListener('mousemove', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const rawX = e.clientX - rect.left;
      const rawY = e.clientY - rect.top;
      const scale = this.scale || 1;
      const offX = this.offsetX || 0;
      const offY = this.offsetY || 0;
      const x = (rawX - offX) / scale;
      const y = (rawY - offY) / scale;
      this.mousePos = { x, y };

      let found = null;
      for (const key in this.nodes) {
        const node = this.nodes[key];
        const dist = Math.hypot(node.x - x, node.y - y);
        if (dist <= 26) {
          found = node;
          break;
        }
      }
      this.hoveredNode = found;
      this.canvas.style.cursor = found ? 'pointer' : 'crosshair';
    });

    this.canvas.addEventListener('click', () => {
      if (this.hoveredNode) {
        this.selectedNode = this.hoveredNode;
        if (window.app && window.app.onNodeSelected) {
          window.app.onNodeSelected(this.selectedNode);
        }
      }
    });
  }

  initParticles() {
    this.particles = [];
    for (let i = 0; i < 40; i++) {
      this.particles.push({
        progress: Math.random(),
        speed: 0.0035 + Math.random() * 0.003,
        flow: Math.random() > 0.45 ? 'steady' : 'elephant'
      });
    }
  }

  setElephantRerouted(rerouted) {
    this.isElephantRerouted = rerouted;
    const pLink = this.links.find(l => l.id === 'core-primary');
    const sLink = this.links.find(l => l.id === 'core-secondary');
    if (pLink && sLink) {
      if (rerouted) {
        pLink.util = 48; // Synchronized with simulator corePrimaryUtil
        sLink.util = 52; // Synchronized with simulator coreSecondaryUtil
      } else {
        pLink.util = 96; // Overloaded!
        sLink.util = 0;
      }
    }
  }

  setLinkUtilization(primaryUtil, secondaryUtil, rerouted) {
    if (rerouted !== undefined) this.isElephantRerouted = !!rerouted;
    const pLink = this.links.find(l => l.id === 'core-primary');
    const sLink = this.links.find(l => l.id === 'core-secondary');
    if (pLink) pLink.util = Math.round(primaryUtil);
    if (sLink) sLink.util = Math.round(secondaryUtil);
  }

  drawCyberGrid() {
    const ctx = this.ctx;
    ctx.save();
    ctx.strokeStyle = 'rgba(56, 189, 248, 0.04)';
    ctx.lineWidth = 1;

    const gridSize = 40;
    const baseW = 980;
    const baseH = 520;
    for (let x = 0; x <= baseW; x += gridSize) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, baseH);
      ctx.stroke();
    }
    for (let y = 0; y <= baseH; y += gridSize) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(baseW, y);
      ctx.stroke();
    }

    // Corner crosshairs
    ctx.fillStyle = 'rgba(56, 189, 248, 0.45)';
    ctx.font = '8px "JetBrains Mono", monospace';
    ctx.fillText('DPID_TOPOLOGY_LAYER // OF1.3', 14, 18);
    ctx.restore();
  }

  drawLink(link) {
    const from = this.nodes[link.from];
    const to = this.nodes[link.to];
    if (!from || !to) return;

    this.ctx.save();
    this.ctx.beginPath();

    let strokeStyle = 'rgba(148, 163, 184, 0.3)';
    let lineWidth = 2;

    if (link.type === 'primary') {
      lineWidth = 3.5;
      strokeStyle = link.util > 85 ? '#ef4444' : '#00f2fe';
    } else if (link.type === 'secondary') {
      lineWidth = 3.5;
      strokeStyle = link.util > 85 ? '#ef4444' : (link.util > 0 ? '#c084fc' : 'rgba(168, 85, 247, 0.35)');
    } else if (link.type === 'trunk') {
      lineWidth = 3;
      strokeStyle = 'rgba(99, 102, 241, 0.7)';
    }

    this.ctx.strokeStyle = strokeStyle;
    this.ctx.lineWidth = lineWidth;

    if (link.curvature) {
      const midX = (from.x + to.x) / 2;
      const midY = (from.y + to.y) / 2 + link.curvature;
      this.ctx.moveTo(from.x, from.y);
      this.ctx.quadraticCurveTo(midX, midY, to.x, to.y);

      // Glow on active links
      if (link.util > 0) {
        this.ctx.shadowColor = strokeStyle;
        this.ctx.shadowBlur = 8;
      }
      this.ctx.stroke();
      this.ctx.shadowBlur = 0;

      // Draw link label with pill background
      const text = `${link.label} [${Math.round(link.util)}%]`;
      this.ctx.font = 'bold 9px "JetBrains Mono", monospace';
      const textWidth = this.ctx.measureText(text).width;
      const labelY = midY + (link.curvature < 0 ? -12 : 20);

      this.ctx.fillStyle = 'rgba(10, 14, 23, 0.9)';
      this.ctx.fillRect(midX - textWidth / 2 - 5, labelY - 10, textWidth + 10, 15);
      this.ctx.strokeStyle = link.util > 85
        ? 'rgba(239, 68, 68, 0.5)'
        : (link.type === 'secondary' ? 'rgba(168, 85, 247, 0.5)' : 'rgba(56, 189, 248, 0.4)');
      this.ctx.strokeRect(midX - textWidth / 2 - 5, labelY - 10, textWidth + 10, 15);

      this.ctx.fillStyle = link.util > 85
        ? '#fca5a5'
        : (link.type === 'secondary' ? '#e9d5ff' : '#ffffff');
      this.ctx.textAlign = 'center';
      this.ctx.fillText(text, midX, labelY);

    } else {
      this.ctx.moveTo(from.x, from.y);
      this.ctx.lineTo(to.x, to.y);
      this.ctx.stroke();

      if (link.label) {
        const midX = (from.x + to.x) / 2;
        const midY = (from.y + to.y) / 2 - 10;
        this.ctx.font = '9px "JetBrains Mono", monospace';
        this.ctx.fillStyle = 'rgba(203, 213, 225, 0.75)';
        this.ctx.textAlign = 'center';
        this.ctx.fillText(link.label, midX, midY);
      }
    }

    this.ctx.restore();
  }

  drawParticles() {
    this.ctx.save();
    for (const p of this.particles) {
      p.progress += p.speed;
      if (p.progress > 1) p.progress = 0;

      let pathCoords = null;
      if (p.flow === 'steady' && this.isSteadyActive) {
        pathCoords = this.getPathCoordinates('steady', p.progress);
        this.ctx.fillStyle = '#00f2fe';
        this.ctx.shadowColor = '#00f2fe';
        this.ctx.shadowBlur = 10;
      } else if (p.flow === 'elephant' && this.isElephantActive) {
        pathCoords = this.getPathCoordinates(this.isElephantRerouted ? 'elephant-secondary' : 'elephant-primary', p.progress);
        this.ctx.fillStyle = this.isElephantRerouted ? '#10b981' : '#ef4444';
        this.ctx.shadowColor = this.isElephantRerouted ? '#10b981' : '#ef4444';
        this.ctx.shadowBlur = 14;
      }

      if (pathCoords) {
        this.ctx.beginPath();
        const radius = p.flow === 'elephant' ? 4.5 : 2.5;
        this.ctx.arc(pathCoords.x, pathCoords.y, radius, 0, Math.PI * 2);
        this.ctx.fill();
      }
    }
    this.ctx.restore();
  }

  getPathCoordinates(flowType, t) {
    const s1 = this.nodes.s1, s2 = this.nodes.s2, s3 = this.nodes.s3, s4 = this.nodes.s4;
    let startHost = this.nodes.h1;
    let endHost = this.nodes.h7;
    let curvature = 0;

    if (flowType.startsWith('elephant')) {
      startHost = this.nodes.h2;
      endHost = this.nodes.h8;
      curvature = flowType === 'elephant-secondary' ? 35 : -35;
    } else {
      curvature = -35;
    }

    if (t < 0.15) {
      const u = t / 0.15;
      return { x: startHost.x + (s1.x - startHost.x) * u, y: startHost.y + (s1.y - startHost.y) * u };
    } else if (t < 0.35) {
      const u = (t - 0.15) / 0.20;
      return { x: s1.x + (s2.x - s1.x) * u, y: s1.y + (s2.y - s1.y) * u };
    } else if (t < 0.65) {
      const u = (t - 0.35) / 0.30;
      const midX = (s2.x + s3.x) / 2;
      const midY = (s2.y + s3.y) / 2 + curvature;
      const x = (1 - u) * (1 - u) * s2.x + 2 * (1 - u) * u * midX + u * u * s3.x;
      const y = (1 - u) * (1 - u) * s2.y + 2 * (1 - u) * u * midY + u * u * s3.y;
      return { x, y };
    } else if (t < 0.85) {
      const u = (t - 0.65) / 0.20;
      return { x: s3.x + (s4.x - s3.x) * u, y: s3.y + (s4.y - s3.y) * u };
    } else {
      const u = (t - 0.85) / 0.15;
      return { x: s4.x + (endHost.x - s4.x) * u, y: s4.y + (endHost.y - s4.y) * u };
    }
  }

  drawNode(node) {
    const isSelected = this.selectedNode === node;
    const isHovered = this.hoveredNode === node;
    const ctx = this.ctx;

    ctx.save();

    if (node.type === 'switch') {
      const size = 42;

      // Outer animated halo ring
      const pulseSize = size + 10 + Math.sin(this.animTime * 0.05) * 4;
      ctx.beginPath();
      ctx.arc(node.x, node.y, pulseSize / 2, 0, Math.PI * 2);
      ctx.strokeStyle = isSelected ? 'rgba(0, 242, 254, 0.45)' : 'rgba(56, 189, 248, 0.18)';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 4]);
      ctx.stroke();
      ctx.setLineDash([]);

      // Main Switch Body (Curved rect)
      ctx.beginPath();
      ctx.roundRect ? ctx.roundRect(node.x - size / 2, node.y - size / 2, size, size, 8) : ctx.rect(node.x - size / 2, node.y - size / 2, size, size);

      const grad = ctx.createLinearGradient(node.x - size / 2, node.y - size / 2, node.x + size / 2, node.y + size / 2);
      grad.addColorStop(0, '#162235');
      grad.addColorStop(1, '#0b111e');
      ctx.fillStyle = grad;
      ctx.fill();

      ctx.strokeStyle = isSelected ? '#00f2fe' : (isHovered ? '#38bdf8' : '#2563eb');
      ctx.lineWidth = isSelected ? 3 : 2;
      if (isSelected) {
        ctx.shadowColor = '#00f2fe';
        ctx.shadowBlur = 18;
      }
      ctx.stroke();
      ctx.shadowBlur = 0;

      // Switch Title
      ctx.font = 'bold 13px "Outfit", sans-serif';
      ctx.fillStyle = '#ffffff';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(node.label.toUpperCase(), node.x, node.y - 2);

      // OF1.3 Subtitle
      ctx.font = '8px "JetBrains Mono", monospace';
      ctx.fillStyle = isSelected ? '#00f2fe' : '#38bdf8';
      ctx.fillText('OF1.3', node.x, node.y + 11);

      // Below label
      ctx.font = '9px "JetBrains Mono", monospace';
      ctx.fillStyle = 'rgba(203, 213, 225, 0.85)';
      ctx.fillText(node.id === 's2' || node.id === 's3' ? 'CORE SWITCH' : 'EDGE SWITCH', node.x, node.y + size / 2 + 14);

    } else {
      // Draw Host Node (Circle)
      const radius = 20;

      // Host glow halo
      ctx.beginPath();
      ctx.arc(node.x, node.y, radius + 4, 0, Math.PI * 2);
      ctx.fillStyle = isSelected ? 'rgba(16, 185, 129, 0.35)' : 'rgba(16, 185, 129, 0.12)';
      ctx.fill();

      // Main host circle
      ctx.beginPath();
      ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
      const hostGrad = ctx.createRadialGradient(node.x, node.y, 2, node.x, node.y, radius);
      hostGrad.addColorStop(0, '#10b981');
      hostGrad.addColorStop(1, '#047857');
      ctx.fillStyle = hostGrad;
      ctx.fill();

      ctx.strokeStyle = isSelected ? '#34d399' : (isHovered ? '#10b981' : '#059669');
      ctx.lineWidth = isSelected ? 2.5 : 1.5;
      if (isSelected) {
        ctx.shadowColor = '#10b981';
        ctx.shadowBlur = 14;
      }
      ctx.stroke();
      ctx.shadowBlur = 0;

      // Host label
      ctx.font = 'bold 10px "Plus Jakarta Sans", sans-serif';
      ctx.fillStyle = '#ffffff';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(node.id, node.x, node.y);

      // IP label below
      ctx.font = '9px "JetBrains Mono", monospace';
      ctx.fillStyle = 'rgba(203, 213, 225, 0.85)';
      ctx.fillText(node.ip, node.x, node.y + radius + 11);
    }

    ctx.restore();
  }

  drawHoverTooltip() {
    if (!this.hoveredNode) return;
    const node = this.hoveredNode;
    const ctx = this.ctx;

    ctx.save();
    const tooltipW = 160;
    const tooltipH = 50;
    const posX = Math.min(980 - tooltipW - 10, node.x + 25);
    const posY = Math.max(10, node.y - 30);

    // Glass backdrop
    ctx.fillStyle = 'rgba(10, 14, 23, 0.95)';
    ctx.strokeStyle = 'rgba(56, 189, 248, 0.45)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect ? ctx.roundRect(posX, posY, tooltipW, tooltipH, 6) : ctx.rect(posX, posY, tooltipW, tooltipH);
    ctx.fill();
    ctx.stroke();

    ctx.font = 'bold 10px "Outfit", sans-serif';
    ctx.fillStyle = '#ffffff';
    ctx.textAlign = 'left';
    ctx.fillText(`${node.type === 'switch' ? 'SWITCH ' + node.id.toUpperCase() : 'HOST ' + node.id.toUpperCase()}`, posX + 10, posY + 16);

    ctx.font = '8.5px "JetBrains Mono", monospace';
    ctx.fillStyle = 'rgba(148, 163, 184, 0.95)';
    if (node.type === 'switch') {
      ctx.fillText(`DPID: ${node.dpid.slice(-6)} | Port Tx/Rx: ~7M`, posX + 10, posY + 31);
      ctx.fillText(`Flow Table Entries: ${node.flows}`, posX + 10, posY + 43);
    } else {
      ctx.fillText(`IP: ${node.ip}`, posX + 10, posY + 31);
      ctx.fillText(`MAC: ${node.mac}`, posX + 10, posY + 43);
    }

    ctx.restore();
  }

  animate() {
    this.animTime += 1;
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    this.ctx.save();
    this.ctx.scale(this.dpr, this.dpr);
    this.ctx.translate(this.offsetX || 0, this.offsetY || 0);
    this.ctx.scale(this.scale || 1, this.scale || 1);

    // Draw background cyber grid
    this.drawCyberGrid();

    // Draw all links
    for (const link of this.links) {
      this.drawLink(link);
    }

    // Draw packet particles
    this.drawParticles();

    // Draw nodes
    for (const key in this.nodes) {
      this.drawNode(this.nodes[key]);
    }

    // Draw hover tooltip
    this.drawHoverTooltip();

    this.ctx.restore();

    requestAnimationFrame(this.animate);
  }
}

window.TopologyVisualizer = TopologyVisualizer;
