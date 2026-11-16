# SELF-X Frontend Visualisation Studio: Architecture & Canvas Engine Guide

> **Production Guide to High-Performance Canvas 2D Telemetry & Visual Analytics**  
> *Modules: `Web/js/topology_studio.js`, `Web/js/comparison_viz.js`, `Web/js/advanced_analytics.js`*  
> *Component Guide — EC466: Software Defined Networks | Team ID: SDN_07 | IIIT Dharwad*  
> *Document Version: 2.4.0-Production*

---

## 📌 Table of Contents
1. [Executive Summary & Core Visual Principles](#executive-summary--core-visual-principles)
2. [Rendering Pipeline & Performance Optimizations](#rendering-pipeline--performance-optimizations)
3. [Multi-Topology Studio Engine (`topology_studio.js`)](#multi-topology-studio-engine-topology_studiojs)
   - [Fabric Coordinate Geometry & Tiered Projection](#fabric-coordinate-geometry--tiered-projection)
   - [Link Saturation Gradients & Dynamic Color Interpolation](#link-saturation-gradients--dynamic-color-interpolation)
   - [Animated Flow Particle Physics Simulation](#animated-flow-particle-physics-simulation)
   - [Interactive Hit-Testing & Switch Inspection](#interactive-hit-testing--switch-inspection)
   - [8x8 Traffic Matrix Heatmap](#8x8-traffic-matrix-heatmap)
   - [Hardware TCAM Capacity Bar](#hardware-tcam-capacity-bar)
4. [Algorithm Comparison Studio Engine (`comparison_viz.js`)](#algorithm-comparison-studio-engine-comparison_vizjs)
   - [7-Axis Comparison Radar Chart](#7-axis-comparison-radar-chart)
   - [Empirical CDF Distribution Engine & Percentile Scrubber](#empirical-cdf-distribution-engine--percentile-scrubber)
   - [180s Head-to-Head Trajectory Comparator & Difference Ribbon](#180s-head-to-head-trajectory-comparator--difference-ribbon)
   - [Audited Effects Matrix Explorer & CSV Exporter](#audited-effects-matrix-explorer--csv-exporter)
5. [Advanced Theory & Analytics Lab (`advanced_analytics.js`)](#advanced-theory--analytics-lab-advanced_analyticsjs)
   - [Lyapunov Drift-Plus-Penalty Phase Space & V-Sweep Visualizer](#lyapunov-drift-plus-penalty-phase-space--v-sweep-visualizer)
   - [Statistical Hypothesis Lab (Paired Seeds Forest Plot & Diamond)](#statistical-hypothesis-lab-paired-seeds-forest-plot--diamond)
   - [SmolLM2-135M LoRA Adapter Training Visualizer](#smollm2-135m-lora-adapter-training-visualizer)
6. [Lifecycle Management, DOM Coordination & Memory Safety](#lifecycle-management-dom-coordination--memory-safety)

---

## 🎨 Executive Summary & Core Visual Principles

The SELF-X web visualizer is engineered to deliver zero-lag, 60 FPS interactive telemetric visual analytics without relying on heavy frontend frameworks (such as React, Vue, or Angular) or bloated charting libraries. The entire visualization layer is built using **native HTML5 Canvas 2D Context** and lightweight ES6 modules.

### Visual Architecture Overview

```
+-----------------------------------------------------------------------------------------+
|                                VISUALIZATION STUDIO ARCHITECTURE                        |
|                                                                                         |
|  [ User Interactions: Mouse Move, Click, Tab Switch, Slider Drag, Controller Toggle ]   |
|                                          |                                              |
|                                          v                                              |
|  +-----------------------------------------------------------------------------------+  |
|  | Event Coordinator & HiDPI Viewport Manager (app.js)                                |  |
|  | - Window Device Pixel Ratio Scaling (window.devicePixelRatio = 2x/3x)              |  |
|  | - ResizeObserver Canvas Backing Buffer Rescaling                                   |  |
|  | - RequestAnimationFrame Loop Synchronization (Delta Time Clamping)                |  |
|  +-----------------------------------------------------------------------------------+  |
|                                          |                                              |
|         +--------------------------------+--------------------------------+             |
|         |                                |                                |             |
|         v                                v                                v             |
|  +----------------------+      +----------------------+      +----------------------+   |
|  | MultiTopologyStudio  |      | ComparisonVizStudio  |      | AdvancedAnalyticsLab |   |
|  | (topology_studio.js) |      | (comparison_viz.js)  |      | (advanced_analytics) |   |
|  |                      |      |                      |      |                      |   |
|  | - Fabric Coordinate  |      | - 7-Axis Polar Radar |      | - Lyapunov DPP Phase |   |
|  |   Tier Projection    |      | - Dual ECDF Engine   |      |   Space Trajectory   |   |
|  | - Link Saturation    |      | - 180s Trajectory    |      | - Forest Plot & 95%  |   |
|  |   Color Gradients    |      |   Difference Ribbon  |      |   Confidence Diamond |   |
|  | - Flow Particle Sim  |      | - Effects Matrix     |      | - LoRA Loss Curve &  |   |
|  | - 8x8 Traffic Matrix |      |   CSV Exporter       |      |   Gradient Norms     |   |
|  | - TCAM Gauge Bar     |      |                      |      |                      |   |
|  +----------------------+      +----------------------+      +----------------------+   |
+-----------------------------------------------------------------------------------------+
```

---

## ⚡ Rendering Pipeline & Performance Optimizations

### 1. HiDPI Canvas Crispness (Device Pixel Ratio Scaling)
Standard HTML5 canvas elements render blurry text and fuzzy lines on Retina, 4K, and high-DPI displays. All visualizers implement automatic backing-store scaling:

```javascript
function setupHiDPICanvas(canvas) {
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    
    // Scale the physical pixel backing store
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    
    // Lock the CSS layout size
    canvas.style.width = `${rect.width}px`;
    canvas.style.height = `${rect.height}px`;
    
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    return { ctx, width: rect.width, height: rect.height };
}
```

### 2. RequestAnimationFrame Throttling & Delta Clamping
To prevent particle physics runaway when the browser tab is backgrounded, animation loops clamp elapsed delta time:
$$\Delta t_{\text{clamped}} = \min(\Delta t_{\text{actual}}, 0.1\,\text{s})$$

---

## 🌐 Multi-Topology Studio Engine (`topology_studio.js`)

### Fabric Coordinate Geometry & Tiered Projection
The `MultiTopologyRenderer` dynamically computes layout coordinates based on switch roles and tiers:

1. **Linear Tandem (4 Switches)**:
   - Switches $s_1 \to s_2 \to s_3 \to s_4$ arranged horizontally across $Y = 0.5 \cdot H$.
   - Primary path ($s_2 \to s_3$) top curved arc; secondary path bottom curved arc.
   - Hosts clustered around ingress ($s_1$) and egress ($s_4$).
2. **Leaf-Spine 2x4 Data Center Fabric**:
   - Spine Tier: 2 spine switches placed at $Y = 0.25 \cdot H$, $X \in \{0.35 \cdot W, 0.65 \cdot W\}$.
   - Leaf Tier: 4 leaf switches placed at $Y = 0.65 \cdot H$, $X \in \{0.15 \cdot W, 0.38 \cdot W, 0.62 \cdot W, 0.85 \cdot W\}$.
   - Bisectional Links: Complete bipartite cross-connect between every spine and leaf switch.
   - Hosts: Distributed below leaf switches ($Y = 0.88 \cdot H$).
3. **Augmented 6-Switch Mesh**:
   - Hexagonal or planar polygon projection with inter-core bypass links to test out-of-distribution routing.

### Link Saturation Gradients & Dynamic Color Interpolation
Links are rendered with dynamic stroke widths and color gradients representing instantaneous link utilization:
$$\rho = \frac{\text{Current Throughput (Mbps)}}{\text{Link Capacity (Mbps)}}$$

- $\rho \le 0.50$: Emerald Green (`#10b981`)
- $0.50 < \rho \le 0.85$: Amber Warning (`#f59e0b`)
- $\rho > 0.85$: Crimson Overload (`#ef4444`)

```javascript
function getLinkColor(utilization) {
    if (utilization < 0.5) return '#10b981';
    if (utilization < 0.85) return '#f59e0b';
    return '#ef4444';
}
```

### Animated Flow Particle Physics Simulation
To visualize packet flow dynamics:
- Each active flow emits particles traveling along the computed shortest or rerouted path.
- Particle positions update via:
  $$p(t + \Delta t) = (p(t) + v \cdot \Delta t) \pmod 1$$
- Particle velocity $v$ scales proportionally with flow rate, providing immediate visual feedback when an elephant flow is throttled or rerouted.

### Interactive Hit-Testing & Switch Inspection
- Built-in mouse raycaster matches screen $(X, Y)$ against switch bounding circles ($r = 24\,\text{px}$).
- On hover, switches glow with a neon aura (`shadowBlur = 15`).
- On click, displays an inspection popover showing OpenFlow DPID, active port queue depth, and installed flow table rules.

### 8x8 Traffic Matrix Heatmap
The `TrafficMatrixHeatmap` component renders an interactive $8 \times 8$ matrix (hosts $h_1 \dots h_8$):
- Cell color intensity maps logarithmically to instantaneous bandwidth (kbps).
- Clicking a cell triggers real-time packet burst simulation between selected source and destination hosts.

### Hardware TCAM Capacity Bar
Visualizes Table 0 OpenFlow rule occupancy:
- Capacity limit: 1,024 flow entries.
- Displays safe threshold (< 700 rules, green), warning threshold (700-900 rules, orange), and critical saturation (> 900 rules, red).

---

## 📈 Algorithm Comparison Studio Engine (`comparison_viz.js`)

### 7-Axis Comparison Radar Chart
The `ComparisonRadarChart` projects 7 key network performance metrics into polar space:

```
                      1. Mean Latency
                            ^
                            |
   7. Convergence Speed     |      2. Tail Latency (P95)
              \             |             /
                \           |           /
                  \         |         /
  6. TCAM Churn ----+-------+-------+---- 3. Packet Loss
                  /         |         \
                /           |           \
              /             |             \
      5. Mean Queue         |         4. Goodput
                            v
```

#### Polar Projection Mathematics
For each axis $i \in \{0, \dots, 6\}$:
$$\theta_i = i \cdot \frac{2\pi}{7} - \frac{\pi}{2}$$
$$x_i = c_x + R \cdot \tilde{v}_i \cdot \cos(\theta_i), \quad y_i = c_y + R \cdot \tilde{v}_i \cdot \sin(\theta_i)$$
where $\tilde{v}_i \in [0, 1]$ is the normalized metric value. Directional metrics (Latency, Loss, Queue, Churn) are inverted so that the outer perimeter always represents optimal performance.

### Empirical CDF Distribution Engine & Percentile Scrubber
The `ComparisonCDFChart` computes and displays empirical cumulative distribution functions:
$$F_X(x) = \frac{1}{N} \sum_{k=1}^N \mathbf{1}_{X_k \le x}$$

- Dual toggle: **Packet Delay CDF** vs **Queue Occupancy CDF**.
- **Interactive Scrubber**: Draggable vertical threshold line dynamically displays $P_{50}, P_{90}, P_{95}, P_{99}$ percentiles across all enabled controllers simultaneously.

### 180s Head-to-Head Trajectory Comparator & Difference Ribbon
The `TrajectoryComparatorChart` displays continuous time-series curves over the 180-second benchmark run:
- Plots baseline controller (e.g. `S0` Static Default) vs evaluated controller (e.g. `S5` SELF-X).
- **Difference Ribbon**: Fills the polygon between curves with semi-transparent green (when SELF-X outperforms baseline) or red (when baseline outperforms), providing immediate visual proof of elephant flow mitigation at $T = 30\,\text{s}$.

### Audited Effects Matrix Explorer & CSV Exporter
The `EffectsMatrixExplorer` presents a sortable table detailing all 13 comparison pairs against `S0`:
- Displays $\Delta$ Delay, $\Delta$ Goodput, $\Delta$ Loss, $\Delta$ Queue, $\Delta$ Reward with 95% bootstrap confidence intervals.
- Client-side CSV generator converts the rendered dataset into RFC 4180-compliant CSV files for immediate download.

---

## 🔬 Advanced Theory & Analytics Lab (`advanced_analytics.js`)

### Lyapunov Drift-Plus-Penalty Phase Space & V-Sweep Visualizer
The `LyapunovDPPVisualizer` illustrates the formal mathematical stability proof:
1. **Phase Space Plot**: Maps queue backlog $Q(t)$ against drift-plus-penalty objective:
   $$\Delta L(Q(t)) + V \cdot g(t)$$
   Visualizes the convergence trajectory spiraling inward toward the stable attractor state.
2. **Analytical Backlog Bound**: Plots the theoretical ceiling:
   $$Q_{\text{bound}} = \frac{B + V \cdot C_{\max}}{\epsilon}$$
   showing that 100% of empirical intervals fall safely below the bound.
3. **$V$-Parameter Sweep Curve**: Displays the trade-off curve between queuing delay and control churn as $V$ varies from $0.1$ to $50.0$.

### Statistical Hypothesis Lab (Paired Seeds Forest Plot & Diamond)
The `StatisticalHypothesisLab` visualizes the paired Student's t-test ($t=14.41$, $p < 0.0001$, Cohen's $d = 4.557$):
- **Forest Plot**: Renders individual horizontal difference bars with 95% confidence whiskers for each of the 10 matched random seeds.
- **Summary Diamond**: Plots the pooled meta-analytic effect size at the bottom; the entire diamond lies strictly to the left of the zero-effect line ($\Delta = 0$), demonstrating statistically significant latency reduction across all seeds.

### SmolLM2-135M LoRA Adapter Training Visualizer
The `LoRATrainingVisualizer` visualizes parameter-efficient fine-tuning:
- Dual-Y axes: Left axis plots cross-entropy training loss ($2.45 \to 0.14$); right axis plots gradient norm ($1.42 \to 0.09$).
- Displays promotion gate threshold indicating where the model passed stress evaluation and was hot-swapped into the datapath.

---

## 🔄 Lifecycle Management, DOM Coordination & Memory Safety

### Tab Navigation Coordination
The web UI organizes capabilities into clean tabs:
- `#tab-dashboard`: Real-time telemetry, Cytoscape switch layout, Chart.js time-series.
- `#tab-comparison`: 14-controller radar, CDF scrubber, trajectory comparator, effects matrix.
- `#tab-topo`: Multi-topology switcher, link saturation, 8x8 traffic matrix, TCAM meters.
- `#tab-analytics`: Formal theory lab, Lyapunov phase space, Forest plot, LoRA training curves.

### Memory Leak Prevention
- When tabs are hidden, their respective `requestAnimationFrame` loops are paused.
- Off-screen canvas buffers are cleared before redrawing to prevent memory bloat over extended continuous runs.

---
*Authored by Team SDN_07 — EC466: Software Defined Networks | IIIT Dharwad*
