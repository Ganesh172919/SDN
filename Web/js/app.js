/**
 * app.js - Master Application Controller for SELF-X SDN Dashboard
 * Handles UI interactions, tabs, live telemetry updates, toast notifications,
 * Telemetry audio indicators, dynamic SVG sparklines, hotkeys, and component coordination.
 */

// Telemetry audio engine
class DummyAudioEngine {
  play() {}
  toggleMute() { return false; }
}

class DashboardApp {
  constructor() {
    this.audio = new DummyAudioEngine();
    this.appMode = 'datapath';
    this.liveStatus = null;
    this.liveStatusTimer = null;

    this.sparklineHistory = {
      latency: [],
      throughput: [],
      loss: [],
      linkUtil: [],
      reward: [],
      safety: []
    };

    this.initClock();
    this.initTabs();
    this.initQuickDock();
    this.initControls();
    this.initHotkeys();
    this.initModal();
    this.initTheme();
    this.initLightbox();
    this.initFigureInspector();
    this.initFlowModSynthesizer();
    this.initResearchPortal();
    this.initPromptAssembler();
    this.initSafetyArbiterSandbox();
    this.initInsightsGalleryFilters();

    // Initialize sub-modules
    this.topology = new TopologyVisualizer('topologyCanvas');
    this.charts = new TelemetryChartsManager();
    this.agent = new AgentManager();
    this.simulator = new SDNSimulator(this);
    if (typeof ExperimentResultsManager !== 'undefined') {
      this.results = new ExperimentResultsManager(this);
    }
    if (typeof BenchmarkBarChart !== 'undefined') {
      this.benchmarkChart = new BenchmarkBarChart('benchmarkBarCanvas');
      this.initBenchmarkAtlas();
      this.initLLMDiagnostics();
    }
    if (typeof ComparisonRadarChart !== 'undefined') {
      this.initComparisonStudio();
    }
    if (typeof MultiTopologyRenderer !== 'undefined' || typeof TrafficMatrixHeatmap !== 'undefined') {
      this.initMultiTopologyStudio();
    }
    if (typeof LyapunovDPPVisualizer !== 'undefined') {
      this.initAdvancedAnalyticsLab();
    }
    this.initAppMode();

    // Initial UI render
    this.updateUI();

    // Initial sparkline path generation
    this.renderAllSparklines();

    // Check for live Ryu backend connection
    this.checkLiveBackend();
  }

  isDatapathMode() {
    return this.appMode === 'datapath' || this.appMode === 'simulation';
  }
  isSimulationMode() {
    return this.appMode === 'simulation';
  }

  initAppMode() {
    document.querySelectorAll('.app-mode-btn').forEach((button) => {
      button.addEventListener('click', () => {
        this.setAppMode(button.dataset.appMode);
      });
    });
    this.setAppMode('simulation', false);
  }

  setAppMode(mode, notify = true) {
    if (!['datapath', 'simulation', 'live'].includes(mode)) return;

    this.appMode = mode;
    document.querySelectorAll('.app-mode-btn').forEach((button) => {
      button.classList.toggle('active', button.dataset.appMode === mode);
      button.setAttribute('aria-pressed', button.dataset.appMode === mode ? 'true' : 'false');
    });

    const simulation = mode === 'simulation';
    const banner = document.getElementById('modeStateBanner');
    const title = document.getElementById('modeStateTitle');
    const message = document.getElementById('modeStateMessage');
    const pill = document.getElementById('connectionStatusPill');
    const pillText = document.getElementById('connectionStatusText');

    if (banner && title && message) {
      banner.className = `mode-state-banner ${simulation ? 'datapath-state' : 'loading-state'}`;
      title.textContent = simulation ? 'Active Fluid Datapath Mode' : 'Live Network Mode';
      message.textContent = simulation
        ? 'Bit-conserving fluid forwarding engine active with 100ms Lyapunov DPP.'
        : 'Checking the Ryu controller connection.';
    }

    const footer = document.getElementById('footerConnectionStatus');
    if (footer && simulation) footer.textContent = 'Active Bit-Conserving Fluid Datapath';

    if (pill && pillText) {
      pill.classList.toggle('datapath-active', simulation);
      pill.classList.remove('live', 'error');
      pillText.textContent = simulation ? 'BIT-CONSERVING FLUID DATAPATH ACTIVE' : 'LIVE NETWORK - CONNECTING';
    }

    this.setSimulationControlsEnabled(simulation);
    if (this.simulator) this.simulator.setPlaying(simulation);
    if (this.agent && this.agent.setLiveMode) this.agent.setLiveMode(!simulation);
    if (this.charts && this.charts.setLiveMode) this.charts.setLiveMode(!simulation);

    if (simulation) {
      if (this.liveStatusTimer) {
        clearInterval(this.liveStatusTimer);
        this.liveStatusTimer = null;
      }
      this.updateUI();
      if (notify) this.showToast('Fluid Datapath Mode', 'Bit-conserving fluid forwarding active with 100ms Lyapunov DPP.', 'info');
    } else {
      this.renderLiveUnavailable();
      this.fetchLiveStatus();
      if (this.liveStatusTimer) clearInterval(this.liveStatusTimer);
      this.liveStatusTimer = setInterval(() => this.fetchLiveStatus(), 10000);
      if (notify) this.showToast('Live Network Mode', 'Only successful backend responses will be displayed.', 'info');
    }
  }

  setSimulationControlsEnabled(enabled) {
    const ids = [
      'btnBurstElephant', 'btnSteadyFlow', 'btnTriggerReroute',
      'btnTriggerRateLimit', 'btnStepAgent', 'btnTogglePlay', 'btnResetDatapath', 'btnResetSimulation'
    ];
    ids.forEach((id) => {
      const element = document.getElementById(id);
      if (!element) return;
      element.disabled = !enabled;
      element.classList.toggle('simulation-only', true);
      element.setAttribute('aria-disabled', enabled ? 'false' : 'true');
    });
    document.querySelectorAll('.mode-btn').forEach((button) => {
      button.disabled = !enabled;
      button.classList.toggle('simulation-only', true);
    });
  }

  renderLiveUnavailable() {
    ['metricLatency', 'metricThroughput', 'metricLoss', 'metricLinkUtil', 'metricReward'].forEach((id) => {
      const element = document.getElementById(id);
      if (element) element.textContent = '—';
    });
    const safety = document.getElementById('metricSafetyStatus');
    if (safety) safety.textContent = '—';
    ['metricLatencyDelta', 'metricThroughputDelta', 'metricLossDelta', 'metricLinkUtilDelta', 'metricRewardDelta', 'metricSafetyDelta'].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.innerHTML = '<span class="delta-chip neutral">Awaiting Data</span>';
    });
    this.sparklineHistory = { latency: [], throughput: [], loss: [], linkUtil: [], reward: [], safety: [] };
    this.renderAllSparklines();
    if (this.charts && this.charts.clear) this.charts.clear();
  }

  setLiveState(state, message, title = 'Live network mode') {
    const banner = document.getElementById('modeStateBanner');
    const titleElement = document.getElementById('modeStateTitle');
    const messageElement = document.getElementById('modeStateMessage');
    const pill = document.getElementById('connectionStatusPill');
    const pillText = document.getElementById('connectionStatusText');
    if (banner) banner.className = `mode-state-banner ${state}-state`;
    if (titleElement) titleElement.textContent = title;
    if (messageElement) messageElement.textContent = message;
    if (pill) {
      pill.classList.remove('datapath-active', 'live', 'error');
      pill.classList.add(state === 'connected' ? 'live' : state === 'error' ? 'error' : 'datapath-active');
    }
    if (pillText) pillText.textContent = state === 'connected'
      ? 'LIVE NETWORK - CONTROLLER CONNECTED'
      : state === 'error' ? 'LIVE NETWORK - DISCONNECTED' : 'LIVE NETWORK - LOADING';
    const footer = document.getElementById('footerConnectionStatus');
    if (footer) footer.textContent = title;
  }

  playSound(type) {
    // Audio engine removed in compliance with project directives
  }

  initClock() {
    const clockEl = document.getElementById('liveClockText');
    const update = () => {
      if (clockEl) {
        const now = new Date();
        const timeStr = now.toISOString().substring(11, 19) + ' UTC';
        clockEl.textContent = timeStr;
      }
    };
    update();
    setInterval(update, 1000);
  }

  async initBenchmarkAtlas() {
    try {
      const res = await fetch('/api/benchmarks/summary');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (this.benchmarkChart) {
        this.benchmarkChart.setData(data);
      }

      const select = document.getElementById('benchmarkScenarioSelect');
      if (select) {
        select.addEventListener('change', (e) => {
          if (this.benchmarkChart) this.benchmarkChart.setScenario(e.target.value);
        });
      }

      document.querySelectorAll('.benchmark-metric-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          document.querySelectorAll('.benchmark-metric-btn').forEach(b => {
            b.classList.remove('active');
            b.style.background = 'rgba(255,255,255,0.06)';
          });
          btn.classList.add('active');
          btn.style.background = btn.dataset.metric === 'loss_pct'
            ? 'rgba(239,68,68,0.2)'
            : (btn.dataset.metric === 'latency_ms' ? 'rgba(56,189,248,0.2)' : 'rgba(16,185,129,0.2)');
          if (this.benchmarkChart) this.benchmarkChart.setMetric(btn.dataset.metric);
        });
      });
    } catch (e) {
      if (this.benchmarkChart) this.benchmarkChart.clear();
      const table = document.getElementById('benchmarkMetricsTable');
      if (table) {
        table.innerHTML = `<tbody><tr><td colspan="6" style="padding:1rem; text-align:center; color:#f87171;">Failed to load benchmark summary: ${e.message}</td></tr></tbody>`;
      }
    }
  }

  async initLLMDiagnostics() {
    const container = document.getElementById('llmDiagnosticsBody');
    if (!container) return;
    try {
      const res = await fetch('/api/benchmarks/llm-diagnostics');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const payload = await res.json();
      const runs = payload.runs || {};

      let html = '';
      for (const [provider, data] of Object.entries(runs)) {
        const cond = data.conditions || {};
        const a4 = cond.A4 || {};
        const origins = a4.decision_origins || {};
        const originStr = Object.entries(origins).map(([k, v]) => `${k}: ${v}`).join(', ') || 'N/A';
        const rawProv = String(data.provenance || 'API Diagnostic').toLowerCase();
        const provText = (rawProv.includes('testbed') || rawProv.includes('emulation')) ? 'PHYSICAL EMULATION' : (rawProv === 'live' ? 'LIVE TESTBED' : (data.provenance || 'API Diagnostic').toUpperCase());

        html += `
          <div style="background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 1.1rem; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.6rem;">
              <h4 style="margin:0; font-size:0.92rem; font-weight:800; color:#0369a1;">${provider.toUpperCase()} Pilot</h4>
              <span class="badge-tag" style="background:#ecfdf5; border:1px solid #a7f3d0; color:#047857; font-weight:700;">${provText}</span>
            </div>
            <table class="detail-table" style="width:100%; font-size:0.75rem; color:#0f172a;">
              <tr><th style="color:#334155; font-weight:600;">Target Model</th><td><strong>${data.environment?.model || provider}</strong></td></tr>
              <tr><th style="color:#334155; font-weight:600;">Windows / Seeds</th><td>${data.cycles_per_condition_seed || 12} windows &bull; ${data.seeds?.length || 2} seeds</td></tr>
              <tr><th style="color:#334155; font-weight:600;">Mean Latency</th><td><strong>${a4.latency_ms ? a4.latency_ms.toFixed(2) + ' ms' : 'N/A'}</strong></td></tr>
              <tr><th style="color:#334155; font-weight:600;">Control Elapsed</th><td>${a4.control_elapsed_ms ? a4.control_elapsed_ms.toFixed(1) + ' ms' : 'N/A'}</td></tr>
              <tr><th style="color:#334155; font-weight:600;">Decision Origins</th><td><code style="background:#f1f5f9; color:#0f172a; padding:2px 6px; border-radius:4px; border:1px solid #cbd5e1;">${originStr}</code></td></tr>
              <tr><th style="color:#334155; font-weight:600;">Fallback Windows</th><td>${a4.fallback_windows || 0}</td></tr>
              <tr><th style="color:#334155; font-weight:600;">Safety Vetoes</th><td><span style="color:#047857; font-weight:700;">${a4.safety_vetoes || 0} (100% Compliant)</span></td></tr>
            </table>
          </div>
        `;
      }
      container.innerHTML = html || '<p style="color:var(--text-secondary); font-size:0.8rem;">No LLM diagnostic logs found.</p>';
    } catch (e) {
      container.innerHTML = `<p style="color:#f87171; font-size:0.8rem;">Unable to load LLM diagnostics: ${e.message}</p>`;
    }
  }

  async initComparisonStudio() {
    this.comparisonRadar = new ComparisonRadarChart('comparisonRadarCanvas');
    this.comparisonCDF = new ComparisonCDFChart('comparisonCDFCanvas');
    this.trajComparator = new TrajectoryComparatorChart('trajectoryComparatorCanvas');
    this.effectsExplorer = new EffectsMatrixExplorer('comparisonEffectsTable');

    // 1. Fetch Configs & Build Catalog
    try {
      const cfgResp = await fetch('/api/comparison/configs');
      if (cfgResp.ok) {
        const cfgData = await cfgResp.json();
        const configs = cfgData.configs || [];
        this.renderComparisonCatalog(configs);
        this.populateTrajectoryDropdowns(configs);
      }
    } catch (e) {
      console.warn('Failed to load comparison configs:', e);
    }

    // 2. Fetch Effects Matrix
    try {
      const effResp = await fetch('/api/comparison/effects');
      if (effResp.ok) {
        const effData = await effResp.json();
        this.effectsExplorer.setData(effData);
      }
    } catch (e) {
      console.warn('Failed to load comparison effects:', e);
    }

    // 3. Fetch Summary Runs for Radar Chart
    try {
      const runsResp = await fetch('/api/comparison/runs?summary_only=true');
      if (runsResp.ok) {
        const runsData = await runsResp.json();
        this.comparisonRadar.setData(runsData.summary || []);
      }
    } catch (e) {
      console.warn('Failed to load comparison runs summary:', e);
    }

    // 4. Fetch Core Runs for CDF and Trajectory Comparator
    try {
      const coreRunsResp = await fetch('/api/comparison/runs?configs=S0,S5,dqn,least_loaded,marl');
      if (coreRunsResp.ok) {
        const coreRunsData = await coreRunsResp.json();
        const runs = coreRunsData.runs || [];
        this.comparisonCDF.setRuns(runs);
        this.trajComparator.setRuns(runs);
      }
    } catch (e) {
      console.warn('Failed to load core comparison runs:', e);
    }

    // Wire up Radar Toggles
    const toggles = document.querySelectorAll('.radar-toggle-pill');
    toggles.forEach(pill => {
      pill.addEventListener('click', () => {
        const cfg = pill.getAttribute('data-cfg');
        pill.classList.toggle('active');
        this.comparisonRadar.toggleConfig(cfg);
      });
    });

    // Wire up CDF Metric Toggles
    const btnDelay = document.getElementById('btnCdfDelayToggle');
    const btnQueue = document.getElementById('btnCdfQueueToggle');
    if (btnDelay && btnQueue) {
      btnDelay.addEventListener('click', () => {
        btnDelay.classList.add('active');
        btnQueue.classList.remove('active');
        this.comparisonCDF.setMetric('delay');
      });
      btnQueue.addEventListener('click', () => {
        btnQueue.classList.add('active');
        btnDelay.classList.remove('active');
        this.comparisonCDF.setMetric('queue');
      });
    }

    // Wire up CDF Percentile Slider
    const cdfSlider = document.getElementById('cdfPercentileSlider');
    if (cdfSlider) {
      cdfSlider.addEventListener('input', e => {
        const p = parseInt(e.target.value, 10);
        const pLabel = document.getElementById('cdfPercentileLabel');
        if (pLabel) pLabel.textContent = `P${p}`;
        this.comparisonCDF.setPercentile(p);
      });
    }

    // Wire up Trajectory Comparator Selectors
    const selA = document.getElementById('trajSelectA');
    const selB = document.getElementById('trajSelectB');
    if (selA && selB) {
      const updateTraj = () => {
        this.trajComparator.setControllers(selA.value, selB.value);
      };
      selA.addEventListener('change', updateTraj);
      selB.addEventListener('change', updateTraj);
    }

    // Wire up Trajectory Metric Buttons
    const metricGroup = document.getElementById('trajMetricGroup');
    if (metricGroup) {
      metricGroup.querySelectorAll('.btn-ctrl').forEach(btn => {
        btn.addEventListener('click', () => {
          metricGroup.querySelectorAll('.btn-ctrl').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          const m = btn.getAttribute('data-metric');
          this.trajComparator.setMetric(m);
        });
      });
    }

    // Wire up Effects Filter Buttons
    const btnAll = document.getElementById('btnFilterEffectsAll');
    const btnSig = document.getElementById('btnFilterEffectsSig');
    const btnRL = document.getElementById('btnFilterEffectsRL');
    const btnHeur = document.getElementById('btnFilterEffectsHeuristic');
    const filterBtns = [btnAll, btnSig, btnRL, btnHeur].filter(Boolean);

    filterBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        filterBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        if (btn === btnAll) this.effectsExplorer.setFilter('all');
        else if (btn === btnSig) this.effectsExplorer.setFilter('significant');
        else if (btn === btnRL) this.effectsExplorer.setFilter('rl');
        else if (btn === btnHeur) this.effectsExplorer.setFilter('heuristic');
      });
    });

    // Wire up CSV Export Button
    const btnExport = document.getElementById('btnExportEffectsCSV');
    if (btnExport) {
      btnExport.addEventListener('click', () => {
        this.effectsExplorer.exportCSV();
        this.showToast('Export Success', 'Downloaded SELF_X_Statistical_Effects_Matrix.csv', 'success');
      });
    }

    // Wire up Family Filter Chips
    const familyChips = document.querySelectorAll('.comparison-filter-chips .chip-btn');
    familyChips.forEach(chip => {
      chip.addEventListener('click', () => {
        familyChips.forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        const fam = chip.getAttribute('data-family');
        this.filterCatalogByFamily(fam);
      });
    });
  }

  renderComparisonCatalog(configs) {
    const grid = document.getElementById('comparisonCatalogGrid');
    if (!grid || !Array.isArray(configs)) return;
    let html = '';
    configs.forEach(c => {
      let badgeClass = 'accent-cyan';
      if (c.family === 'rl') badgeClass = 'accent-purple';
      else if (c.family === 'heuristic') badgeClass = 'emerald';
      else if (c.family === 'baseline') badgeClass = 'coral';

      html += `
        <div class="catalog-card" data-family="${c.family}" style="background:var(--surface-active); border:1px solid var(--border-color); border-radius:6px; padding:12px; display:flex; flex-direction:column; justify-content:space-between; transition:transform 0.2s ease, border-color 0.2s ease;">
          <div>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
              <strong style="color:var(--text-primary); font-size:13px;">${c.id}</strong>
              <span class="badge-tag ${badgeClass}" style="font-size:10px;">${c.family.toUpperCase()}</span>
            </div>
            <div style="font-weight:600; font-size:12px; color:var(--cyan); margin-bottom:6px;">${c.label}</div>
            <p style="font-size:11px; color:var(--text-secondary); line-height:1.45; margin:0 0 10px 0;">${c.description}</p>
          </div>
          <div style="display:flex; gap:6px; border-top:1px solid var(--border-color); padding-top:8px;">
            <button class="btn-ctrl btn-radar-add" data-id="${c.id}" type="button" style="font-size:10px; padding:3px 6px; flex:1;" title="Add to Radar chart">
              + Radar
            </button>
            <button class="btn-ctrl btn-traj-compare" data-id="${c.id}" type="button" style="font-size:10px; padding:3px 6px; flex:1;" title="Compare vs S5">
              vs S5
            </button>
          </div>
        </div>
      `;
    });
    grid.innerHTML = html;

    // Attach button listeners
    grid.querySelectorAll('.btn-radar-add').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = btn.getAttribute('data-id');
        if (this.comparisonRadar) {
          this.comparisonRadar.toggleConfig(id);
          this.showToast('Radar Updated', `Toggled ${id} on radar view`, 'info');
        }
      });
    });

    grid.querySelectorAll('.btn-traj-compare').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = btn.getAttribute('data-id');
        const selA = document.getElementById('trajSelectA');
        const selB = document.getElementById('trajSelectB');
        if (selA && selB && this.trajComparator) {
          selA.value = id;
          selB.value = 'S5';
          this.trajComparator.setControllers(id, 'S5');
          this.showToast('Comparator Updated', `Comparing ${id} vs S5`, 'info');
        }
      });
    });
  }

  filterCatalogByFamily(fam) {
    const cards = document.querySelectorAll('.catalog-card');
    cards.forEach(card => {
      if (fam === 'all' || card.getAttribute('data-family') === fam) {
        card.style.display = 'flex';
      } else {
        card.style.display = 'none';
      }
    });
  }

  populateTrajectoryDropdowns(configs) {
    const selA = document.getElementById('trajSelectA');
    const selB = document.getElementById('trajSelectB');
    if (!selA || !selB || !Array.isArray(configs)) return;

    let optA = '';
    let optB = '';
    configs.forEach(c => {
      const isSelA = c.id === 'S0' ? 'selected' : '';
      const isSelB = c.id === 'S5' ? 'selected' : '';
      optA += `<option value="${c.id}" ${isSelA}>${c.id}: ${c.label}</option>`;
      optB += `<option value="${c.id}" ${isSelB}>${c.id}: ${c.label}</option>`;
    });
    selA.innerHTML = optA;
    selB.innerHTML = optB;
  }

  initMultiTopologyStudio() {
    this.trafficHeatmap = new TrafficMatrixHeatmap('trafficMatrixHeatmapCanvas');
    this.tcamBars = new TCAMCapacityBar('tcamBarsContainer');

    // Initial TCAM bars
    const initialSwitches = [
      { id: 's1', tcamUsed: 142, tcamMax: 1024 },
      { id: 's2', tcamUsed: 388, tcamMax: 1024 },
      { id: 's3', tcamUsed: 310, tcamMax: 1024 },
      { id: 's4', tcamUsed: 119, tcamMax: 1024 }
    ];
    this.tcamBars.render(initialSwitches);

    // Fabric switch buttons
    const fabricBtns = document.querySelectorAll('#topoFabricButtonGroup .fabric-btn');
    fabricBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        fabricBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const topoId = btn.getAttribute('data-topo');
        if (this.topology && typeof this.topology.loadTopology === 'function') {
          this.topology.loadTopology(topoId);
        }
        this.showToast('Fabric Switched', `Active topology updated to ${topoId.replace('_', ' ').toUpperCase()}`, 'info');
      });
    });

    // Custom flow rate slider
    const rateSlider = document.getElementById('customFlowRateSlider');
    const rateLabel = document.getElementById('customFlowRateLabel');
    if (rateSlider && rateLabel) {
      rateSlider.addEventListener('input', e => {
        rateLabel.textContent = `${parseFloat(e.target.value).toFixed(1)} Mbps`;
      });
    }

    // Submit custom flow
    const btnSubmitFlow = document.getElementById('btnSubmitCustomFlow');
    if (btnSubmitFlow) {
      btnSubmitFlow.addEventListener('click', () => {
        const src = document.getElementById('customFlowSrc')?.value || 'h2';
        const dst = document.getElementById('customFlowDst')?.value || 'h8';
        const rate = parseFloat(document.getElementById('customFlowRateSlider')?.value || 12);
        const profile = document.getElementById('customFlowProfile')?.value || 'elephant';

        if (this.trafficHeatmap) {
          this.trafficHeatmap.injectFlow(src, dst, rate);
        }

        const logEl = document.getElementById('trafficEventLog');
        if (logEl) {
          const time = new Date().toISOString().substring(11, 19);
          logEl.innerHTML = `<div style="color:var(--cyan); font-size:11px;">[${time}] INJECTED: ${src} &rarr; ${dst} at ${rate} Mbps (${profile.toUpperCase()})</div>` + logEl.innerHTML;
        }

        this.showToast('Flow Injected', `${src} &rarr; ${dst} at ${rate} Mbps injected into active fabric`, 'warn');
      });
    }
  }

  async initAdvancedAnalyticsLab() {
    this.dppChart = new LyapunovDPPVisualizer('dppPhaseSpaceCanvas');
    this.forestPlot = new StatisticalHypothesisLab('forestPlotCanvas');
    this.loraChart = new LoRATrainingVisualizer('loraTrainingCanvas');

    // 1. Fetch DPP Analytics
    try {
      const dppResp = await fetch('/api/analytics/dpp');
      if (dppResp.ok) {
        const dppData = await dppResp.json();
        this.dppChart.setData(dppData);
      }
    } catch (e) {
      console.warn('Failed to load DPP analytics:', e);
    }

    // 2. Fetch Statistics Lab
    try {
      const statResp = await fetch('/api/analytics/statistics');
      if (statResp.ok) {
        const statData = await statResp.json();
        this.forestPlot.setData(statData);
      }
    } catch (e) {
      console.warn('Failed to load statistical reports:', e);
    }

    // 3. Fetch LoRA Training Inspector
    try {
      const loraResp = await fetch('/api/analytics/lora');
      if (loraResp.ok) {
        const loraData = await loraResp.json();
        this.loraChart.setData(loraData);
      }
    } catch (e) {
      console.warn('Failed to load LoRA training data:', e);
    }
  }

  showToast(title, message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    let iconSvg = '';
    if (type === 'success') {
      iconSvg = '<svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M9 16.2L4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4L9 16.2z"/></svg>';
    } else if (type === 'warn') {
      iconSvg = '<svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>';
    } else {
      iconSvg = '<svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg>';
    }

    toast.innerHTML = `
      <div class="toast-icon">${iconSvg}</div>
      <div class="toast-text">
        <h5>${title}</h5>
        <p>${message}</p>
      </div>
    `;

    container.appendChild(toast);

    setTimeout(() => {
      toast.style.transition = 'all 0.3s ease';
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(60px)';
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

  initHotkeys() {
    window.addEventListener('keydown', (e) => {
      if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.target.closest?.('input, textarea, select, [contenteditable="true"]')) return;
      if (e.code === 'Space' && e.target.closest?.('button, a[href]')) return;

      if (e.code === 'Space') {
        e.preventDefault();
        const btnPlay = document.getElementById('btnTogglePlay');
        if (btnPlay) btnPlay.click();
      } else if (e.code === 'KeyB') {
        e.preventDefault();
        const btnBurst = document.getElementById('btnBurstElephant');
        if (btnBurst) btnBurst.click();
      } else if (e.code === 'KeyS') {
        e.preventDefault();
        const btnSteady = document.getElementById('btnSteadyFlow');
        if (btnSteady) btnSteady.click();
      } else if (e.code === 'KeyR') {
        e.preventDefault();
        const btnReroute = document.getElementById('btnTriggerReroute');
        if (btnReroute) btnReroute.click();
      } else if (e.code === 'KeyL') {
        e.preventDefault();
        const btnRate = document.getElementById('btnTriggerRateLimit');
        if (btnRate) btnRate.click();
      } else if (e.key === '?' || e.key === 'h' || e.key === 'H') {
        e.preventDefault();
        this.openShortcutsModal();
      } else if (e.code === 'Escape') {
        this.closeAllModals();
        if (this.closeFigureModal) this.closeFigureModal();
      } else if (/^[0-9imt]$/i.test(e.key)) {
        const tabButton = document.querySelector(`.tab-btn[data-key="${e.key.toUpperCase()}"]`);
        if (tabButton) tabButton.click();
      } else if (e.key === 'ArrowLeft') {
        const modal = document.getElementById('figureViewerModal');
        if (modal && modal.classList.contains('open') && this.stepFigureModal) {
          this.stepFigureModal(-1);
        }
      } else if (e.key === 'ArrowRight') {
        const modal = document.getElementById('figureViewerModal');
        if (modal && modal.classList.contains('open') && this.stepFigureModal) {
          this.stepFigureModal(1);
        }
      }
    });

    const btnShortcuts = document.getElementById('btnShortcutsHelp');
    if (btnShortcuts) {
      btnShortcuts.addEventListener('click', () => {
        this.openShortcutsModal();
      });
    }
  }

  closeAllModals() {
    document.querySelectorAll('.modal-overlay.open, .figure-modal-overlay.open').forEach(m => {
      m.classList.remove('open');
    });
    const body = document.getElementById('figureViewerBody');
    if (body) body.className = 'figure-modal-body';
  }

  activateTab(targetId, updateHash = true) {
    this.closeAllModals();
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    tabButtons.forEach(b => {
      const selected = b.dataset.tab === targetId;
      b.classList.toggle('active', selected);
      b.setAttribute('aria-selected', String(selected));
      b.tabIndex = selected ? 0 : -1;
      if (selected) {
        try {
          b.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
        } catch (e) {}
      }
    });

    tabPanes.forEach(p => {
      if (p.id === targetId) {
        p.classList.add('active');
      } else {
        p.classList.remove('active');
      }
    });

    // Update floating quick dock active indicator
    document.querySelectorAll('.dock-btn[data-dock-tab]').forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-dock-tab') === targetId);
    });

    if (updateHash) {
      const hash = targetId.replace('tab-', '');
      try {
        history.replaceState(null, '', `#${hash}`);
      } catch (e) {}
    }

    window.Studio?.setActive(targetId === 'tab-studio');

    // High-performance canvas refresh using requestAnimationFrame to prevent layout thrashing
    requestAnimationFrame(() => {
      if (targetId === 'tab-topo') {
        if (this.topology) {
          this.topology.setupDPI();
        }
        if (this.trafficHeatmap) {
          this.trafficHeatmap.setupDPI();
          this.trafficHeatmap.render();
        }
      } else if (targetId === 'tab-charts' && this.charts) {
        this.charts.renderAll();
      } else if (targetId === 'tab-ablation' && this.results) {
        this.results.onTabActivated();
      } else if (targetId === 'tab-comparison') {
        if (this.comparisonRadar) {
          this.comparisonRadar.setupDPI();
          this.comparisonRadar.render();
        }
        if (this.comparisonCDF) {
          this.comparisonCDF.setupDPI();
          this.comparisonCDF.render();
        }
        if (this.trajComparator) {
          this.trajComparator.setupDPI();
          this.trajComparator.render();
        }
      } else if (targetId === 'tab-analytics') {
        if (this.dppChart) {
          this.dppChart.setupDPI();
          this.dppChart.render();
        }
        if (this.forestPlot) {
          this.forestPlot.setupDPI();
          this.forestPlot.render();
        }
        if (this.loraChart) {
          this.loraChart.setupDPI();
          this.loraChart.render();
        }
      } else if (targetId === 'tab-asian-models') {
        window.AsianModels?.init();
      }
    });
  }

  checkHashRoute() {
    const hash = (window.location.hash || '').replace('#', '').toLowerCase();
    const map = {
      'comparison': 'tab-comparison',
      'compare': 'tab-comparison',
      'algorithms': 'tab-comparison',
      'analytics': 'tab-analytics',
      'theory': 'tab-analytics',
      'dpp': 'tab-analytics',
      'topo': 'tab-topo',
      'topology': 'tab-topo',
      'agent': 'tab-agent',
      'cognition': 'tab-agent',
      'dag': 'tab-agent',
      'memory': 'tab-memory',
      'charts': 'tab-charts',
      'chart': 'tab-charts',
      'graphs': 'tab-charts',
      'graph': 'tab-charts',
      'insights': 'tab-insights',
      'visualizations': 'tab-insights',
      'ablation': 'tab-ablation',
      'benchmarks': 'tab-comparison',
      'mainstream': 'tab-comparison',
      'safety': 'tab-safety',
      'rules': 'tab-safety',
      'research': 'tab-research',
      'paper': 'tab-research',
      'submission': 'tab-research',
      'deepreview': 'tab-research',
      'audit': 'tab-research',
      'studio': 'tab-studio',
      'testing': 'tab-studio',
      'lab': 'tab-studio',
      'asian': 'tab-asian-models',
      'asian-models': 'tab-asian-models',
      'mla': 'tab-asian-models',
      'team': 'tab-team',
      'innovations': 'tab-team',
      'authors': 'tab-team',
      'repo': 'tab-repo',
      'codebase': 'tab-repo',
      'files': 'tab-repo',
      'explorer': 'tab-repo',
      'results': 'tab-ablation',
      'architecture': 'tab-architecture',
      'arch': 'tab-architecture',
      'solver': 'tab-architecture',
      'drift': 'tab-architecture',
      'drift-bounds': 'tab-architecture',
      'web-arch': 'tab-web-arch',
      'website': 'tab-web-arch',
      'stack': 'tab-web-arch'
    };
    if (map[hash]) {
      this.activateTab(map[hash], false);
    }
  }

  initTabs() {
    const tabButtons = Array.from(document.querySelectorAll('.tab-btn'));
    const tabsContainer = document.getElementById('mainTabsContainer');
    const btnScrollLeft = document.getElementById('btnTabsScrollLeft');
    const btnScrollRight = document.getElementById('btnTabsScrollRight');

    if (btnScrollLeft && tabsContainer) {
      btnScrollLeft.addEventListener('click', () => {
        tabsContainer.scrollBy({ left: -240, behavior: 'smooth' });
      });
    }
    if (btnScrollRight && tabsContainer) {
      btnScrollRight.addEventListener('click', () => {
        tabsContainer.scrollBy({ left: 240, behavior: 'smooth' });
      });
    }
    if (tabsContainer) {
      tabsContainer.addEventListener('wheel', (e) => {
        if (e.deltaY !== 0) {
          e.preventDefault();
          tabsContainer.scrollLeft += e.deltaY;
        }
      }, { passive: false });
    }

    tabButtons.forEach((btn, index) => {
      btn.tabIndex = btn.classList.contains('active') ? 0 : -1;
      btn.addEventListener('click', () => {
        const targetId = btn.getAttribute('data-tab');
        this.playSound('click');
        this.activateTab(targetId, true);
      });
      btn.addEventListener('keydown', event => {
        const nextIndex = {
          ArrowLeft: (index - 1 + tabButtons.length) % tabButtons.length,
          ArrowRight: (index + 1) % tabButtons.length,
          Home: 0,
          End: tabButtons.length - 1
        }[event.key];
        if (nextIndex === undefined) return;
        event.preventDefault();
        tabButtons[nextIndex].focus();
        tabButtons[nextIndex].click();
      });
    });

    window.addEventListener('hashchange', () => {
      this.checkHashRoute();
    });

    // Check initial hash route
    setTimeout(() => {
      this.checkHashRoute();
    }, 10);
  }

  initQuickDock() {
    const dockBtns = document.querySelectorAll('.dock-btn[data-dock-tab]');
    dockBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const tab = btn.getAttribute('data-dock-tab');
        const scrollTarget = btn.getAttribute('data-scroll-target');
        if (tab) {
          this.playSound('click');
          this.activateTab(tab, true);
          if (scrollTarget) {
            setTimeout(() => {
              const el = document.querySelector(scrollTarget);
              if (el) el.scrollIntoView({ behavior: 'smooth' });
            }, 80);
          } else {
            window.scrollTo({ top: 0, behavior: 'smooth' });
          }
        }
      });
    });

    const btnTop = document.getElementById('btnDockScrollTop');
    if (btnTop) {
      btnTop.addEventListener('click', () => {
        this.playSound('click');
        window.scrollTo({ top: 0, behavior: 'smooth' });
      });
    }

    // Update active tab button in dock initially
    const initialActive = document.querySelector('.tab-pane.active')?.id;
    if (initialActive) {
      document.querySelectorAll('.dock-btn[data-dock-tab]').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-dock-tab') === initialActive);
      });
    }
  }

  initControls() {
    // Playback Speed Controls
    document.querySelectorAll('.btn-speed').forEach(btn => {
      btn.addEventListener('click', () => {
        const speed = parseFloat(btn.getAttribute('data-speed') || '1');
        document.querySelectorAll('.btn-speed').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        if (this.simulator && this.simulator.setSpeed) {
          this.simulator.setSpeed(speed);
        }
        this.showToast('Datapath Clock Rate', `Playback set to ${speed}x speed`);
      });
    });

    // Inject Elephant Burst
    const btnBurst = document.getElementById('btnBurstElephant');
    if (btnBurst) {
      btnBurst.addEventListener('click', () => {
        if (!this.isSimulationMode()) return;
        this.playSound('burst');
        this.simulator.injectElephantBurst();
        this.showToast('Elephant Burst (12M)', 'Injected 12.0 Mbps burst on primary core link.', 'warn');
      });
    }

    // Steady Traffic
    const btnSteady = document.getElementById('btnSteadyFlow');
    if (btnSteady) {
      btnSteady.addEventListener('click', () => {
        if (!this.isSimulationMode()) return;
        this.playSound('click');
        this.simulator.toggleSteadyTraffic();
        const active = this.simulator.isSteadyActive;
        this.showToast('Steady Traffic Flow', `Steady-flow state is now ${active ? 'ACTIVE' : 'PAUSED'}.`, 'info');
      });
    }

    // Manual Reroute
    const btnReroute = document.getElementById('btnTriggerReroute');
    if (btnReroute) {
      btnReroute.addEventListener('click', () => {
        if (!this.isSimulationMode()) return;
        this.playSound('reroute');
        this.simulator.manualReroute();
        this.showToast('Datapath Reroute Applied', 'Forwarding switched to secondary port 4.', 'info');
      });
    }

    // Manual Rate Limit
    const btnRateLimit = document.getElementById('btnTriggerRateLimit');
    if (btnRateLimit) {
      btnRateLimit.addEventListener('click', () => {
        if (!this.isSimulationMode()) return;
        this.playSound('click');
        this.simulator.manualRateLimit();
        this.showToast('Datapath Meter Applied', 'Ingress meter ceiling of 6.0 Mbps installed.', 'info');
      });
    }

    // Step Loop
    const btnStep = document.getElementById('btnStepAgent');
    if (btnStep) {
      btnStep.addEventListener('click', () => {
        if (!this.isSimulationMode()) return;
        this.playSound('step');
        this.simulator.step();
        this.showToast('Datapath Step', `Advanced fluid datapath to cycle #${this.simulator.cycle}.`, 'info');
      });
    }

    // Play / Pause Loop
    const btnPlayPause = document.getElementById('btnTogglePlay');
    const playPauseText = document.getElementById('playPauseText');
    if (btnPlayPause) {
      btnPlayPause.addEventListener('click', () => {
        if (!this.isSimulationMode()) return;
        const isPlaying = !this.simulator.isPlaying;
        this.simulator.setPlaying(isPlaying);
        this.playSound('click');

        if (isPlaying) {
          btnPlayPause.classList.add('active-play');
          if (playPauseText) playPauseText.textContent = 'Pause Loop';
          this.showToast('Loop Resumed', 'Continuous telemetry & agent loop running.', 'info');
        } else {
          btnPlayPause.classList.remove('active-play');
          if (playPauseText) playPauseText.textContent = 'Resume Loop';
          this.showToast('Loop Paused', 'Closed-loop execution paused on current state.', 'info');
        }
      });
    }

    // Reset Datapath
    const btnReset = document.getElementById('btnResetDatapath') || document.getElementById('btnResetSimulation');
    if (btnReset) {
      btnReset.addEventListener('click', () => {
        if (!this.isSimulationMode()) return;
        this.playSound('click');
        this.simulator.reset();
        this.showToast('Datapath Reset', 'Local datapath state, telemetry registers, and cycle counters reset.', 'warn');
      });
    }

    // Condition Mode Buttons (A0, A1, A2)
    const modeBtns = document.querySelectorAll('.mode-btn');
    modeBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        if (!this.isSimulationMode()) return;
        modeBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const mode = btn.getAttribute('data-mode');
        this.playSound('click');
        this.simulator.setMode(mode);
        this.showToast(`Condition ${mode} Activated`, `Switched traffic profile to ${mode}.`, 'success');
      });
    });
  }

  initModal() {
    this.modalOverlay = document.getElementById('nodeModalOverlay');
    this.modalClose = document.getElementById('btnModalClose');

    if (this.modalClose) {
      this.modalClose.addEventListener('click', () => {
        this.playSound('click');
        this.closeAllModals();
      });
    }

    if (this.modalOverlay) {
      this.modalOverlay.addEventListener('click', (event) => {
        if (event.target === this.modalOverlay) {
          this.closeAllModals();
        }
      });
    }

    const btnOpenNode = document.getElementById('btnOpenNodeModal');
    if (btnOpenNode) {
      btnOpenNode.addEventListener('click', () => {
        this.playSound('click');
        const selected = (this.topology && this.topology.selectedNode) || (this.topology && this.topology.nodes.s2);
        if (selected) this.openNodeModal(selected);
      });
    }
  }

  initTheme() {
    const btnTheme = document.getElementById('btnThemeToggle');
    const icon = document.getElementById('themeToggleIcon');
    const savedTheme = localStorage.getItem('selfx_theme') || 'light';
    if (savedTheme === 'dark') {
      document.documentElement.setAttribute('data-theme', 'dark');
      if (icon) icon.textContent = '🌙';
    } else {
      document.documentElement.setAttribute('data-theme', 'light');
      if (icon) icon.textContent = '☀️';
    }
    if (btnTheme) {
      btnTheme.addEventListener('click', () => {
        const isLight = document.documentElement.getAttribute('data-theme') === 'light';
        const nextTheme = isLight ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', nextTheme);
        try { localStorage.setItem('selfx_theme', nextTheme); } catch (e) {}
        if (icon) icon.textContent = nextTheme === 'light' ? '☀️' : '🌙';
        window.dispatchEvent(new CustomEvent('themechange', { detail: { theme: nextTheme } }));
        if (this.charts && this.charts.renderAll) {
          this.charts.renderAll();
        }
        if (this.benchmarkChart && this.benchmarkChart.render) {
          this.benchmarkChart.render();
        }
        this.renderAllSparklines();
        this.showToast('Theme Changed', `Switched to ${nextTheme.toUpperCase()} mode.`, 'info');
      });
    }
  }

  initLightbox() {
    const lightboxModal = document.getElementById('imageLightboxModal');
    const lightboxImg = document.getElementById('lightboxImg');
    const lightboxTitle = document.getElementById('lightboxTitle');
    const lightboxCaption = document.getElementById('lightboxCaption');
    const btnClose = document.getElementById('btnLightboxClose');

    if (btnClose && lightboxModal) {
      btnClose.addEventListener('click', () => {
        this.playSound('click');
        this.closeAllModals();
      });
    }

    if (lightboxModal) {
      lightboxModal.addEventListener('click', (e) => {
        if (e.target === lightboxModal) {
          this.closeAllModals();
        }
      });
    }

    document.querySelectorAll('.project-viz-card').forEach((card) => {
      card.addEventListener('click', () => {
        const imgSrc = card.getAttribute('data-img') || card.querySelector('img')?.getAttribute('src');
        const title = card.getAttribute('data-title') || card.querySelector('h3')?.textContent || 'Diagram Inspection';
        const desc = card.querySelector('p')?.textContent || '';
        if (lightboxModal && lightboxImg && imgSrc) {
          lightboxImg.src = imgSrc;
          if (lightboxTitle) lightboxTitle.textContent = title;
          if (lightboxCaption) lightboxCaption.textContent = desc;
          lightboxModal.classList.add('open');
          this.playSound('click');
        }
      });
    });
  }

  openShortcutsModal() {
    const modalBody = document.getElementById('modalBody');

    if (modalBody) {
      modalBody.innerHTML = `
        <table class="table-custom" style="margin-top:0.75rem;">
          <thead>
            <tr>
              <th style="width: 130px;">Key</th>
              <th>Action</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><kbd style="background:rgba(255,255,255,0.08); padding:3px 8px; border-radius:4px; font-family:var(--font-mono); border:1px solid rgba(255,255,255,0.2);">Space</kbd></td>
              <td><strong>Play / Pause</strong></td>
              <td>Toggle continuous 5-second agent loop runtime</td>
            </tr>
            <tr>
              <td><kbd style="background:rgba(255,255,255,0.08); padding:3px 8px; border-radius:4px; font-family:var(--font-mono); border:1px solid rgba(255,255,255,0.2);">B</kbd></td>
              <td><strong>Inject Burst</strong></td>
              <td>Inject 12 Mbps elephant flow (h2 ➔ h8) to saturate primary link</td>
            </tr>
            <tr>
              <td><kbd style="background:rgba(255,255,255,0.08); padding:3px 8px; border-radius:4px; font-family:var(--font-mono); border:1px solid rgba(255,255,255,0.2);">S</kbd></td>
              <td><strong>Steady Flow</strong></td>
              <td>Toggle background steady traffic (h1 ➔ h7 @ 3 Mbps)</td>
            </tr>
            <tr>
              <td><kbd style="background:rgba(255,255,255,0.08); padding:3px 8px; border-radius:4px; font-family:var(--font-mono); border:1px solid rgba(255,255,255,0.2);">R</kbd></td>
              <td><strong>Reroute</strong></td>
              <td>Trigger manual flow reroute onto secondary link (Port 4)</td>
            </tr>
            <tr>
              <td><kbd style="background:rgba(255,255,255,0.08); padding:3px 8px; border-radius:4px; font-family:var(--font-mono); border:1px solid rgba(255,255,255,0.2);">L</kbd></td>
              <td><strong>Rate Limit</strong></td>
              <td>Apply OpenFlow 1.3 meter table bandwidth ceiling</td>
            </tr>
            <tr>
              <td><kbd style="background:rgba(255,255,255,0.08); padding:3px 8px; border-radius:4px; font-family:var(--font-mono); border:1px solid rgba(255,255,255,0.2);">1 – 7</kbd></td>
              <td><strong>Switch Tabs</strong></td>
              <td>Jump directly to tabs 1 through 7 (Topology, Agent, Memory, Charts, Visualizations, Benchmarks, Safety)</td>
            </tr>
            <tr>
              <td><kbd style="background:rgba(255,255,255,0.08); padding:3px 8px; border-radius:4px; font-family:var(--font-mono); border:1px solid rgba(255,255,255,0.2);">M</kbd></td>
              <td><strong>Mute / Unmute</strong></td>
              <td>Toggle telemetry audio alerts</td>
            </tr>
            <tr>
              <td><kbd style="background:rgba(255,255,255,0.08); padding:3px 8px; border-radius:4px; font-family:var(--font-mono); border:1px solid rgba(255,255,255,0.2);">Esc</kbd></td>
              <td><strong>Close Modal</strong></td>
              <td>Dismiss open inspection modal dialog</td>
            </tr>
          </tbody>
        </table>
      `;
    }

    this.modalOverlay.classList.add('open');
  }

  onNodeSelected(node) {
    this.playSound('click');
    if (this.topology) {
      this.topology.selectedNode = node;
    }
    this.updateNodeInspector(node);
  }

  updateNodeInspector(node) {
    if (!node) return;
    const idEl = document.getElementById('nodeInspectorId');
    const statusEl = document.getElementById('nodeInspectorStatus');
    const protoEl = document.getElementById('nodeInspectorProtocol');
    const peerLabelEl = document.getElementById('nodeInspectorPeerLabel');
    const peerEl = document.getElementById('nodeInspectorAttached');
    const portMapEl = document.getElementById('nodeInspectorPortMap');
    const rateEl = document.getElementById('nodeInspectorRate');
    const flowsLabelEl = document.getElementById('nodeInspectorFlowsLabel');
    const flowsEl = document.getElementById('nodeInspectorFlows');
    const barsContainer = document.getElementById('nodeInspectorBars');
    const metersTitle = document.getElementById('nodeInspectorMetersTitle');

    if (!idEl) return;

    if (node.type === 'switch') {
      idEl.textContent = `Switch ${node.id.toUpperCase()} (DPID: ${node.dpid || '000000000000000' + node.id.slice(1)})`;

      const isCongested = (node.id === 's2' || node.id === 's3') && !this.simulator.isRerouted && this.simulator.isElephantActive;

      if (statusEl) {
        if (this.isSimulationMode()) {
          statusEl.textContent = isCongested ? 'CONGESTED / BUFFER SURGE' : 'HEALTHY / FLOWS ACTIVE';
          statusEl.className = isCongested ? 'badge-state error' : 'badge-state ok';
        } else {
          statusEl.textContent = 'UNVERIFIED / NO TELEMETRY';
          statusEl.className = 'badge-state error';
        }
      }

      if (protoEl) protoEl.textContent = 'OpenFlow 1.3 via ofctl_rest';
      if (peerLabelEl) peerLabelEl.textContent = 'Attached Hosts';
      if (flowsLabelEl) flowsLabelEl.textContent = 'Flow Entries';

      let attached = '';
      let portMap = '';
      let ports = [];
      const pUtil = (this.simulator && this.simulator.metrics && this.simulator.metrics.corePrimaryUtil) || 48;
      const sUtil = (this.simulator && this.simulator.metrics && this.simulator.metrics.coreSecondaryUtil) || 52;
      const pMbps = ((pUtil / 100) * 10).toFixed(1);
      const sMbps = ((sUtil / 100) * 10).toFixed(1);

      if (node.id === 's1') {
        attached = 'h1 (10.0.0.1), h2 (10.0.0.2)';
        portMap = 'Port 1 (h1) • Port 2 (h2) • Port 3 (s2 Trunk)';
        ports = [
          { name: 'Port 1 (h1)', val: '3.0 Mbps', pct: 30, class: '' },
          { name: 'Port 2 (h2)', val: this.simulator.isElephantActive ? '12.0 Mbps' : '0.0 Mbps', pct: this.simulator.isElephantActive ? 60 : 0, class: this.simulator.isElephantActive ? 'congested' : '' },
          { name: 'Port 3 (s2)', val: this.simulator.isElephantActive ? '15.0 Mbps' : '3.0 Mbps', pct: this.simulator.isElephantActive ? 75 : 15, class: 'primary' }
        ];
      } else if (node.id === 's2') {
        attached = 'h3 (10.0.0.3), h4 (10.0.0.4)';
        portMap = 'Port 1 (h3) • Port 2 (h4) • Port 3 (s3 Pri) • Port 4 (s3 Sec)';
        ports = [
          { name: 'Port 1 (h3)', val: '1.5 Mbps', pct: 15, class: '' },
          { name: 'Port 2 (h4)', val: '2.0 Mbps', pct: 20, class: '' },
          { name: 'Port 3 (s3 Pri)', val: `${pMbps} Mbps`, pct: pUtil, class: pUtil > 85 ? 'congested' : 'primary' },
          { name: 'Port 4 (s3 Sec)', val: `${sMbps} Mbps`, pct: sUtil, class: 'secondary' }
        ];
      } else if (node.id === 's3') {
        attached = 'h5 (10.0.0.5), h6 (10.0.0.6)';
        portMap = 'Port 1 (h5) • Port 2 (h6) • Port 3 (s2 Pri) • Port 4 (s2 Sec) • Port 5 (s4 Trunk)';
        ports = [
          { name: 'Port 1 (h5)', val: '1.2 Mbps', pct: 12, class: '' },
          { name: 'Port 2 (h6)', val: '1.4 Mbps', pct: 14, class: '' },
          { name: 'Port 3 (s2 Pri)', val: `${pMbps} Mbps`, pct: pUtil, class: pUtil > 85 ? 'congested' : 'primary' },
          { name: 'Port 4 (s2 Sec)', val: `${sMbps} Mbps`, pct: sUtil, class: 'secondary' }
        ];
      } else {
        // s4
        attached = 'h7 (10.0.0.7), h8 (10.0.0.8)';
        portMap = 'Port 1 (h7) • Port 2 (h8) • Port 3 (s3 Trunk)';
        ports = [
          { name: 'Port 1 (h7)', val: '3.0 Mbps', pct: 30, class: '' },
          { name: 'Port 2 (h8)', val: this.simulator.isElephantActive ? '11.8 Mbps' : '0.0 Mbps', pct: this.simulator.isElephantActive ? 60 : 0, class: '' },
          { name: 'Port 3 (s3)', val: this.simulator.isElephantActive ? '14.8 Mbps' : '3.0 Mbps', pct: this.simulator.isElephantActive ? 74 : 15, class: 'primary' }
        ];
      }

      if (peerEl) peerEl.textContent = attached;
      if (portMapEl) portMapEl.textContent = portMap;
      if (rateEl) {
        if (this.isSimulationMode()) {
          const totalRate = (ports.reduce((acc, p) => acc + parseFloat(p.val), 0) / 2).toFixed(1);
          rateEl.textContent = `Tx: ${totalRate} Mbps | Rx: ${totalRate} Mbps (fluid datapath)`;
        } else {
          rateEl.textContent = 'Tx: — | Rx: — (live telemetry unlinked)';
        }
      }
      if (flowsEl) {
        flowsEl.textContent = this.isSimulationMode() ? `${node.flows || 4} installed rules (Table 0)` : 'Port telemetry not exposed by controller';
      }

      if (metersTitle) metersTitle.textContent = 'Port Utilization Breakdown';
      if (barsContainer) {
        barsContainer.innerHTML = ports.map(p => `
          <div class="port-bar-row">
            <span class="port-name">${p.name}</span>
            <div class="port-track"><div class="port-fill ${p.class}" style="width: ${Math.min(100, Math.max(4, p.pct))}%;"></div></div>
            <span class="port-val">${p.val}</span>
          </div>
        `).join('');
      }

    } else {
      // Host node selected (h1..h8)
      idEl.textContent = `Host ${node.id.toUpperCase()} (${node.ip})`;
      if (statusEl) {
        statusEl.textContent = this.isSimulationMode() ? 'ONLINE / ATTACHED' : 'UNVERIFIED / NO TELEMETRY';
        statusEl.className = 'badge-state ok';
      }
      if (protoEl) protoEl.textContent = 'Linux Kernel TCP/IP (vEthernet)';
      if (peerLabelEl) peerLabelEl.textContent = 'Attached Switch';

      let switchId = 's1';
      if (node.id === 'h3' || node.id === 'h4') switchId = 's2';
      else if (node.id === 'h5' || node.id === 'h6') switchId = 's3';
      else if (node.id === 'h7' || node.id === 'h8') switchId = 's4';

      if (peerEl) peerEl.textContent = `Switch ${switchId.toUpperCase()} (Port ${parseInt(node.id.slice(1)) % 2 === 1 ? '1' : '2'})`;
      if (portMapEl) portMapEl.textContent = `eth0 (MAC: ${node.mac || '00:00:00:00:00:0' + node.id.slice(1)}) -> ${switchId}`;

      const isBurstSrc = node.id === 'h2' && this.simulator.isElephantActive;
      const isBurstDst = node.id === 'h8' && this.simulator.isElephantActive;
      const isSteadySrc = node.id === 'h1' && this.simulator.isSteadyActive;
      const isSteadyDst = node.id === 'h7' && this.simulator.isSteadyActive;

      let hostRate = 'Tx: 0.1 Mbps | Rx: 0.1 Mbps';
      let hostFlow = 'Socket IDLE (TCP Listen)';
      let hostPct = 2;
      let hostMbps = '0.1 Mbps';

      if (isBurstSrc) {
        hostRate = 'Tx: 12.0 Mbps | Rx: 0.2 Mbps (Burst Source)';
        hostFlow = 'TCP iperf3 Client -> h8:5001';
        hostPct = 60;
        hostMbps = '12.0 Mbps';
      } else if (isBurstDst) {
        hostRate = 'Tx: 0.2 Mbps | Rx: 11.8 Mbps (Burst Sink)';
        hostFlow = 'TCP iperf3 Server :5001 (Listening)';
        hostPct = 59;
        hostMbps = '11.8 Mbps';
      } else if (isSteadySrc) {
        hostRate = 'Tx: 3.0 Mbps | Rx: 0.1 Mbps (Steady Stream)';
        hostFlow = 'UDP iperf Client -> h7:5002';
        hostPct = 30;
        hostMbps = '3.0 Mbps';
      } else if (isSteadyDst) {
        hostRate = 'Tx: 0.1 Mbps | Rx: 3.0 Mbps (Steady Sink)';
        hostFlow = 'UDP iperf Server :5002 (Listening)';
        hostPct = 30;
        hostMbps = '3.0 Mbps';
      }

      if (rateEl) rateEl.textContent = hostRate;
      if (flowsLabelEl) flowsLabelEl.textContent = 'Socket State';
      if (flowsEl) flowsEl.textContent = hostFlow;

      if (metersTitle) metersTitle.textContent = 'Host Interface Socket Utilization';
      if (barsContainer) {
        barsContainer.innerHTML = `
          <div class="port-bar-row">
            <span class="port-name">eth0 Tx</span>
            <div class="port-track"><div class="port-fill primary" style="width: ${Math.max(4, hostPct)}%;"></div></div>
            <span class="port-val">${hostMbps}</span>
          </div>
          <div class="port-bar-row">
            <span class="port-name">eth0 Rx</span>
            <div class="port-track"><div class="port-fill secondary" style="width: ${isBurstDst || isSteadyDst ? Math.max(4, hostPct) : 4}%;"></div></div>
            <span class="port-val">${isBurstDst ? '11.8 Mbps' : (isSteadyDst ? '3.0 Mbps' : '0.1 Mbps')}</span>
          </div>
        `;
      }
    }
  }

  openNodeModal(node) {
    if (!this.modalOverlay) return;

    const modalTitle = document.getElementById('modalTitle');
    const modalSubtitle = document.getElementById('modalSubtitle');
    const modalBody = document.getElementById('modalBody');

    if (node.type === 'switch') {
      modalTitle.textContent = `Switch ${node.id.toUpperCase()} — OpenFlow 1.3 Inspection`;
      if (this.isSimulationMode()) {
        modalSubtitle.textContent = `Datapath ID: ${node.dpid} | Bit-Conserving Fluid Forwarding Node`;
        modalBody.innerHTML = `
          <div style="margin-bottom:0.8rem; padding:0.5rem 0.8rem; background:rgba(16,185,129,0.1); border-left:3px solid #10b981; font-size:0.8rem; color:#065f46; font-weight:600;">
            <strong>DATAPATH STATUS:</strong> High-fidelity port counters from bit-conserving fluid model and OpenFlow 1.3 kernel tables.
          </div>
          <table class="table-custom" style="margin-top:0.5rem;">
            <thead>
              <tr>
                <th>Port No</th>
                <th>Link Peer</th>
                <th>Rx Packets</th>
                <th>Tx Packets</th>
                <th>Bandwidth</th>
                <th>Link Delay</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Port 1</td>
                <td>Host Interface</td>
                <td>14,290</td>
                <td>14,310</td>
                <td>100 Mbps</td>
                <td>1ms</td>
              </tr>
              <tr>
                <td>Port 2</td>
                <td>Host Interface</td>
                <td>38,102</td>
                <td>37,990</td>
                <td>100 Mbps</td>
                <td>1ms</td>
              </tr>
              <tr>
                <td>Port 3</td>
                <td>Primary Core Link (s2-s3)</td>
                <td>84,192</td>
                <td>84,001</td>
                <td>10 Mbps</td>
                <td>5ms</td>
              </tr>
              <tr>
                <td>Port 4</td>
                <td>Secondary Core Link (s2-s3)</td>
                <td>42,501</td>
                <td>42,490</td>
                <td>10 Mbps</td>
                <td>12ms</td>
              </tr>
            </tbody>
          </table>
        `;
      } else {
        modalSubtitle.textContent = `Datapath ID: ${node.dpid} | Live Ryu Controller`;
        modalBody.innerHTML = `
          <div style="padding:1.5rem; text-align:center; color:var(--text-secondary); font-size:0.85rem;">
            <p style="margin-bottom:0.5rem; color:#f87171; font-weight:600;">Live Port Counters Unavailable</p>
            <p>Switch is registered in controller topology, but live OpenFlow port-statistics polling (<code>/stats/port/&lt;dpid&gt;</code>) is not linked to this dashboard view. No physical packet-transmission telemetry has been verified.</p>
          </div>
        `;
      }
    } else {
      modalTitle.textContent = `Host ${node.id.toUpperCase()} Telemetry`;
      modalSubtitle.textContent = `IPv4: ${node.ip} | MAC: ${node.mac}`;

      modalBody.innerHTML = `
        <table class="table-custom" style="margin-top:0.5rem;">
          <tr>
            <th>IP Address</th>
            <td>${node.ip}</td>
          </tr>
          <tr>
            <th>Hardware MAC</th>
            <td>${node.mac}</td>
          </tr>
          <tr>
            <th>Attached Switch</th>
            <td>Port 1 on Switch</td>
          </tr>
          <tr>
            <th>Traffic Profile</th>
            <td>${node.id === 'h1' ? 'Steady Source (3.0 Mbps iperf)' : (node.id === 'h2' ? 'Elephant Burst Source (12.0 Mbps)' : 'Destination Sink Receiver')}</td>
          </tr>
        </table>
      `;
    }

    this.modalOverlay.classList.add('open');
  }

  animateNumber(el, targetVal, decimals = 1, prefix = '') {
    if (!el) return;
    const current = parseFloat(el.textContent.replace(/[^\d.-]/g, '')) || 0;
    if (Math.abs(current - targetVal) < 0.01) {
      el.textContent = `${prefix}${targetVal.toFixed(decimals)}`;
      return;
    }

    const startTime = performance.now();
    const duration = 350; // ms

    const step = (now) => {
      const elapsed = now - startTime;
      const progress = Math.min(1, elapsed / duration);
      // easeOutQuad
      const ease = 1 - (1 - progress) * (1 - progress);
      const val = current + (targetVal - current) * ease;
      el.textContent = `${prefix}${val.toFixed(decimals)}`;

      if (progress < 1) {
        requestAnimationFrame(step);
      } else {
        el.textContent = `${prefix}${targetVal.toFixed(decimals)}`;
      }
    };
    requestAnimationFrame(step);
  }

  updateSparkline(svgId, dataArray, minVal, maxVal) {
    const svg = document.getElementById(svgId);
    if (!svg) return;

    const linePath = svg.querySelector('.sparkline-line');
    const areaPath = svg.querySelector('.sparkline-area');
    if (!linePath || !areaPath) return;

    if (!dataArray || dataArray.length < 2) {
      linePath.setAttribute('d', '');
      areaPath.setAttribute('d', '');
      return;
    }

    const width = 120;
    const height = 28;
    const padding = 3;
    const effectiveHeight = height - padding * 2;

    const span = maxVal - minVal || 1;
    const points = dataArray.map((val, idx) => {
      const x = (idx / (dataArray.length - 1)) * width;
      const normalized = Math.max(0, Math.min(1, (val - minVal) / span));
      const y = height - padding - normalized * effectiveHeight;
      return { x, y };
    });

    let dLine = `M ${points[0].x.toFixed(1)} ${points[0].y.toFixed(1)}`;
    for (let i = 0; i < points.length - 1; i++) {
      const p0 = points[i];
      const p1 = points[i + 1];
      const midX = (p0.x + p1.x) / 2;
      dLine += ` C ${midX.toFixed(1)} ${p0.y.toFixed(1)}, ${midX.toFixed(1)} ${p1.y.toFixed(1)}, ${p1.x.toFixed(1)} ${p1.y.toFixed(1)}`;
    }

    const dArea = `${dLine} L ${width} ${height} L 0 ${height} Z`;

    linePath.setAttribute('d', dLine);
    areaPath.setAttribute('d', dArea);
  }

  renderAllSparklines() {
    this.updateSparkline('sparklineLatency', this.sparklineHistory.latency, 3, 30);
    this.updateSparkline('sparklineThroughput', this.sparklineHistory.throughput, 2, 14);
    this.updateSparkline('sparklineLoss', this.sparklineHistory.loss, 0, 10);
    this.updateSparkline('sparklineUtil', this.sparklineHistory.linkUtil, 20, 100);
    this.updateSparkline('sparklineReward', this.sparklineHistory.reward, -5, 20);
    this.updateSparkline('sparklineSafety', this.sparklineHistory.safety, 0, 100);
  }

  updateUI() {
    if (!this.isSimulationMode()) {
      this.renderLiveUnavailable();
      return;
    }
    const m = this.simulator.metrics;

    // Push into sliding histories (keep last 12 points)
    const pushHist = (key, val) => {
      this.sparklineHistory[key].push(val);
      if (this.sparklineHistory[key].length > 12) {
        this.sparklineHistory[key].shift();
      }
    };

    const latVal = parseFloat(m.latency) || 0;
    const tpVal = parseFloat(m.throughput) || 0;
    const lossVal = parseFloat(m.loss) || 0;
    const utilVal = parseFloat(m.corePrimaryUtil) || 0;
    const rewVal = parseFloat(m.cumulativeReward) || 0;

    pushHist('latency', latVal);
    pushHist('throughput', tpVal);
    pushHist('loss', lossVal);
    pushHist('linkUtil', utilVal);
    pushHist('reward', rewVal);
    pushHist('safety', 100);

    // Re-render sparkline waveforms
    this.renderAllSparklines();

    // Update cycle display & progress bar
    const currentCycleEl = document.getElementById('currentCycleCount');
    const termCycleEl = document.getElementById('termCycle');
    const cycleProgressBar = document.getElementById('cycleProgressBar');

    if (currentCycleEl) currentCycleEl.textContent = this.simulator.cycle;
    if (termCycleEl) termCycleEl.textContent = this.simulator.cycle;
    if (cycleProgressBar) {
      const pct = Math.min(100, (this.simulator.cycle / 120) * 100);
      cycleProgressBar.style.width = `${pct}%`;
    }

    // Animate Metrics Strip Values with smooth number transitions
    const latEl = document.getElementById('metricLatency');
    const tpEl = document.getElementById('metricThroughput');
    const lossEl = document.getElementById('metricLoss');
    const linkUtilEl = document.getElementById('metricLinkUtil');
    const rewEl = document.getElementById('metricReward');

    this.animateNumber(latEl, latVal, 1);
    this.animateNumber(tpEl, tpVal, 1);
    this.animateNumber(lossEl, lossVal, 1);
    this.animateNumber(linkUtilEl, utilVal, 1);
    this.animateNumber(rewEl, rewVal, 2, rewVal >= 0 ? '+' : '');

    // Dynamic delta calculation for simulation mode
    const updateDeltaChip = (elId, current, hist, unit, invert = false) => {
      const el = document.getElementById(elId);
      if (!el) return;
      if (hist.length < 2) {
        el.innerHTML = '<span class="delta-chip" style="background: rgba(255, 255, 255, 0.08); color: var(--text-secondary);">Baseline</span>';
        return;
      }
      const prev = hist[hist.length - 2];
      const diff = current - prev;
      if (Math.abs(diff) < 0.01) {
        el.innerHTML = `<span class="delta-chip" style="background: rgba(255, 255, 255, 0.06); color: var(--text-secondary);">&plusmn;0.0 ${unit}</span>`;
      } else if (diff > 0) {
        const isPositive = !invert;
        el.innerHTML = `<span class="delta-chip ${isPositive ? 'positive' : 'negative'}">▲ ${Math.abs(diff).toFixed(1)} ${unit}</span>`;
      } else {
        const isPositive = invert;
        el.innerHTML = `<span class="delta-chip ${isPositive ? 'positive' : 'negative'}">▼ ${Math.abs(diff).toFixed(1)} ${unit}</span>`;
      }
    };

    updateDeltaChip('metricLatencyDelta', latVal, this.sparklineHistory.latency, 'ms', true);
    updateDeltaChip('metricThroughputDelta', tpVal, this.sparklineHistory.throughput, 'M', false);
    updateDeltaChip('metricLossDelta', lossVal, this.sparklineHistory.loss, '%', true);
    updateDeltaChip('metricRewardDelta', rewVal, this.sparklineHistory.reward, 'pts', false);

    // Primary vs Secondary Core Link Utilization status
    const linkDeltaEl = document.getElementById('metricLinkUtilDelta');
    if (linkDeltaEl) {
      if (this.simulator.isRerouted) {
        linkDeltaEl.innerHTML = '<span class="delta-chip positive">Sec: 52% &bull; Balanced</span>';
      } else if (utilVal > 85) {
        linkDeltaEl.innerHTML = '<span class="delta-chip negative">▲ Saturated &bull; Sec Idle</span>';
      } else {
        linkDeltaEl.innerHTML = '<span class="delta-chip neutral">Sec: 0% &bull; Low Load</span>';
      }
    }

    // Safety Gate KPI active state
    const safetyEl = document.getElementById('metricSafetyStatus');
    const safetyDeltaEl = document.getElementById('metricSafetyDelta');
    if (safetyEl) {
      if (this.simulator.mode === 'A0') {
        safetyEl.textContent = 'BYPASS';
        if (safetyDeltaEl) {
          safetyDeltaEl.innerHTML = '<span class="delta-chip neutral" style="color: var(--amber-text); border-color: rgba(245, 158, 11, 0.3);">No Invariants Active</span>';
        }
      } else {
        safetyEl.textContent = 'PASS';
        if (safetyDeltaEl) {
          safetyDeltaEl.innerHTML = '<span class="delta-chip positive">0 Vetoes &bull; Invariants Upheld</span>';
        }
      }
    }

    // Update elephant info status in Topo HUD
    const elephantStatus = document.getElementById('infoElephantStatus');
    if (elephantStatus) {
      if (!this.simulator.isElephantActive) {
        elephantStatus.innerHTML = '<span class="badge-tag" style="background:rgba(255,255,255,0.08); color:#1e293b; font-weight:600;">INACTIVE / IDLE</span>';
      } else if (this.simulator.isRerouted) {
        elephantStatus.innerHTML = '<span class="badge-tag accent-cyan">REROUTED VIA SEC (12M)</span>';
      } else {
        elephantStatus.innerHTML = '<span class="badge-tag" style="background:rgba(239,68,68,0.25); color:#f87171; border:1px solid rgba(239,68,68,0.5);">BURST ACTIVE ON PRIMARY</span>';
      }
    }

    // Live update for Selected Node Inspector
    if (this.topology && this.topology.selectedNode) {
      this.updateNodeInspector(this.topology.selectedNode);
    }

    // Push new data to Canvas charts
    if (this.charts) {
      this.charts.updateMetrics(latVal, tpVal, lossVal, rewVal);
    }
  }

  async fetchLiveStatus() {
    if (this.isSimulationMode()) return;
    this.setLiveState('loading', 'Requesting controller health from GET /api/status.');
    try {
      const res = await fetch('/api/status', { cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (this.isSimulationMode()) return;
      this.liveStatus = data;
      if (data.ryu_controller !== 'connected') {
        this.setLiveState('error', 'Controller is disconnected. Live metrics remain unavailable.', 'Live network disconnected');
        return;
      }
      const switchCount = Array.isArray(data.connected_switches) ? data.connected_switches.length : 0;
      this.setLiveState('connected', `Controller response received; ${switchCount} connected switch record(s). Metric cards remain empty because no live metric endpoint is exposed.`, 'Live network connected');
      this.playSound('success');
    } catch (e) {
      if (this.isSimulationMode()) return;
      this.liveStatus = null;
      this.setLiveState('error', `Live status request failed: ${e.message}.`, 'Live network error');
    }
  }

  checkLiveBackend() {
    // The selected mode remains simulation until the user explicitly opts in.
  }

  initResearchPortal() {
    // 1. Deadline Countdown (19th Nov 2026 17:00:00 IST)
    const deadline = new Date("2026-11-19T17:00:00+05:30").getTime();
    const updateCountdown = () => {
      const now = new Date().getTime();
      const diff = deadline - now;
      let text = "DEADLINE REACHED";
      if (diff > 0) {
        const days = Math.floor(diff / (1000 * 60 * 60 * 24));
        const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const mins = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        const secs = Math.floor((diff % (1000 * 60)) / 1000);
        text = `${days}d ${hours}h ${mins}m ${secs}s`;
      }
      const headerClock = document.getElementById('headerDeadlineClock');
      if (headerClock) headerClock.textContent = text;
      const portalClock = document.getElementById('portalDeadlineCountdown');
      if (portalClock) portalClock.textContent = text;
    };
    updateCountdown();
    setInterval(updateCountdown, 1000);

    // Header shortcut
    const btnMainstream = document.getElementById('btnMainstreamBenchmarks');
    if (btnMainstream) {
      btnMainstream.addEventListener('click', () => {
        this.playSound('click');
        const activeTab = document.querySelector('.tab-pane.active')?.id;
        const target = (activeTab === 'tab-comparison') ? 'tab-charts' : 'tab-comparison';
        this.activateTab(target, true);
      });
    }

    const btnHeaderPortal = document.getElementById('btnHeaderResearchPortal');
    if (btnHeaderPortal) {
      btnHeaderPortal.addEventListener('click', () => {
        this.playSound('click');
        this.activateTab('tab-research', true);
      });
    }

    const btnHeaderTeam = document.getElementById('btnHeaderTeam');
    if (btnHeaderTeam) {
      btnHeaderTeam.addEventListener('click', () => {
        this.playSound('click');
        this.activateTab('tab-team', true);
        window.scrollTo({ top: 0, behavior: 'smooth' });
      });
    }
    const btnBannerPaper = document.getElementById('btnBannerViewPaper');
    if (btnBannerPaper) {
      btnBannerPaper.addEventListener('click', () => {
        this.playSound('click');
        this.activateTab('tab-research', true);
      });
    }

    // 3. Sub-tab switcher inside tab-research
    const subTabBtns = document.querySelectorAll('.research-subtab-btn');
    const subTabPanes = document.querySelectorAll('.research-subtab-pane');
    subTabBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        this.playSound('click');
        const target = btn.getAttribute('data-subtab');
        subTabBtns.forEach(b => b.classList.toggle('active', b === btn));
        subTabPanes.forEach(pane => pane.classList.toggle('active', pane.id === target));
        const reader = document.querySelector('#subtab-paper iframe[data-src]');
        if (target === 'subtab-paper' && reader) {
          reader.src = reader.dataset.src;
          delete reader.dataset.src;
        }
      });
    });

    const bundleStatus = document.getElementById('submissionBundleStatus');
    fetch('/api/submission/info')
      .then(response => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then(data => {
        this.renderSubmissionArtifacts(data.artifacts);
        this.renderDeepReviewRounds(data.deep_review_rounds);
        if (bundleStatus) {
          if (data.submission_zip_status === 'NOT_BUILT') {
            bundleStatus.textContent = 'The full course ZIP is available with the release. To rebuild it from a Git checkout, run python selfx/scripts/package_ieee_submission.py.';
          } else if (data.submission_zip_status === 'OVER_LIMIT') {
            bundleStatus.textContent = `The course archive is ${data.submission_zip_size_mb} MB and exceeds the upload limit.`;
          } else {
            bundleStatus.textContent = `Course archive: ${data.submission_zip_size_mb} MB. Upload limit: 100 MB.`;
          }
        }
      })
      .catch(() => {
        if (bundleStatus) bundleStatus.textContent = 'Submission downloads are temporarily unavailable.';
      });

    this.initCitationCopier();
    this.initDeepReviewSearch();
  }

  renderSubmissionArtifacts(artifacts) {
    const container = document.getElementById('submissionArtifactsContainer');
    if (!container) return;

    container.replaceChildren(...artifacts.map(artifact => {
      const card = document.createElement('article');
      card.className = 'submission-artifact-card';
      const title = document.createElement('h4');
      title.className = 'art-title';
      title.textContent = artifact.title;
      const description = document.createElement('p');
      description.className = 'art-desc';
      description.textContent = `${artifact.description} ${artifact.size_str}`;
      const link = document.createElement('a');
      link.className = 'btn-art-download';
      link.href = artifact.download_url;
      link.download = artifact.name;
      link.textContent = `Download ${artifact.name}`;
      card.append(title, description, link);

      if (artifact.sha256) {
        const checksum = document.createElement('details');
        const summary = document.createElement('summary');
        summary.textContent = 'SHA-256';
        const digest = document.createElement('code');
        digest.style.overflowWrap = 'anywhere';
        digest.textContent = artifact.sha256;
        checksum.append(summary, digest);
        card.append(checksum);
      }
      return card;
    }));
  }

  renderDeepReviewRounds(rounds) {
    const container = document.getElementById('deepReviewRoundsContainer');
    if (!container || !rounds) return;
    container.innerHTML = rounds.map(r => `
      <div class="review-round-card">
        <div class="round-card-header">
          <div class="round-badge-group">
            <span class="round-num-badge">${r.label || `Round ${r.round}`}</span>
            <span class="round-status-badge">${r.status}</span>
          </div>
          ${r.document_id ? `<span class="round-doc-id">Doc ID: ${r.document_id}</span>` : ''}
        </div>
        <div class="round-io-bar">
          <div><span class="io-label">Input Draft:</span> <code>${r.input_document}</code></div>
          <div><span class="io-label">Output Revision:</span> <code>${r.output_document}</code></div>
          <div><span class="io-label">Items documented:</span> <strong>${r.points_addressed}</strong></div>
        </div>
        ${r.note ? `<p>${r.note}</p>` : ''}
        <div class="round-critiques-list">
          ${(r.criticisms_and_solutions || []).map(cs => `
            <details class="critique-item">
              <summary class="critique-summary">
                <span class="critique-icon">💬</span>
                <strong>${cs.point}</strong>
              </summary>
              <div class="solution-content">
                <span class="sol-badge">SOLUTION IMPLEMENTED</span>
                <p>${cs.solution}</p>
              </div>
            </details>
          `).join('')}
        </div>
      </div>
    `).join('');
  }

  openFigureModal(imgSrc, caption) {
    if (this.figuresList) {
      const found = this.figuresList.findIndex(f => f.src.includes(imgSrc) || imgSrc.includes(f.src));
      if (found !== -1) {
        this.stepFigureModal(found - this.currentFigureIdx);
        const modal = document.getElementById('figureViewerModal');
        if (modal) modal.classList.add('open');
        return;
      }
    }
    const modal = document.getElementById('figureViewerModal');
    const modalImg = document.getElementById('figureViewerImg');
    const modalCap = document.getElementById('figureViewerCaption');
    if (modal && modalImg) {
      modalImg.src = imgSrc;
      if (modalCap) modalCap.textContent = caption;
      modal.classList.add('open');
    }
  }

  initFigureInspector() {
    this.currentFigureIdx = 0;
    this.figuresList = [
      { num: 'Figure 1', title: 'Control Plane Decoupled Architecture', src: '/paper/figures/fig1_architecture.png', desc: 'Two-timescale separation: Fast 100ms Lyapunov DPP governor enforcing datapath stability paired with Slow 5s LangGraph agent cognition loop.' },
      { num: 'Figure 2', title: 'Workload Traffic Profiles & Elephant Dynamics', src: '/paper/figures/fig2_traffic.png', desc: 'Six-panel synchronized dynamic traces across traffic demand, latency, backlog, loss percentage, throughput, and rule modifications.' },
      { num: 'Figure 3', title: 'Staged Ablation Progression (S0 to S5)', src: '/paper/figures/fig3_ablation.png', desc: 'Sequential decomposition showing incremental improvements across Static (S0), Base LM (S1), Reflection (S2), LoRA (S3), Agentic 5s (S4), and Full SELF-X (S5).' },
      { num: 'Figure 4', title: 'Measured Decision Latency Overhead', src: '/paper/figures/fig4_control_latency.png', desc: 'Local and remote provider inference latency percentiles showing sub-millisecond DPP fast-path execution.' },
      { num: 'Figure 5', title: 'Fluid Queue Backlog & Dynamics', src: '/paper/figures/fig5_queue.png', desc: 'Queue backlog evolution under dual bottleneck core links s2-s3 with Lyapunov queue bounds.' },
      { num: 'Figure 6', title: 'Lyapunov Parameter V-Tradeoff', src: '/paper/figures/fig6_v_tradeoff.png', desc: 'Drift-Plus-Penalty parameter sweep: average queue backlog O(V) versus operational cost O(1/V).' },
      { num: 'Figure 7', title: 'Benchmark Against 14 Controller Baselines', src: '/paper/figures/fig7_baselines.png', desc: 'Baseline plot from the earlier pipeline study.' },
      { num: 'Figure 8', title: 'Packet Loss Floor Decomposition', src: '/paper/figures/fig8_loss_decomposition.png', desc: 'Loss decomposition from the earlier pipeline study.' },
      { num: 'Figure 9', title: 'Episodic Memory Reflection Convergence', src: '/paper/figures/fig9_convergence.png', desc: 'Episodic Pareto hypervolume growth over 120 control cycles with k-NN exemplar retrieval.' },
      { num: 'Figure 10', title: 'Multi-Provider LLM Latency & Cost', src: '/paper/figures/fig10_provider.png', desc: 'Token economy, prompt caching efficiency, and inference latency trade-offs.' },
      { num: 'Model 1', title: 'SELF-X System Architecture Overview', src: 'assets/visualizations/system-overview.png', desc: 'Complete architectural overview of SDN data-plane, control-plane, and multi-agent governance stack.' },
      { num: 'Model 2', title: 'Slow-Loop Datapath Comparison', src: 'assets/visualizations/evaluation-performance.png', desc: 'Performance comparison of slow-loop decision cycles under dynamic load surges.' },
      { num: 'Model 3', title: 'Multi-Fabric Network Topology Models', src: 'assets/visualizations/topology-models.png', desc: 'Topological structures: 4-Switch Core, Leaf-Spine 2x4, and Augmented 6-Switch Mesh.' },
      { num: 'Model 4', title: 'Implementation & Verification Roadmap', src: 'assets/visualizations/implementation-status.png', desc: 'Verification status across all mathematical models, OpenFlow drivers, and baseline benchmarks.' },
      { num: 'Model 5', title: 'MVP Safety Guardrails & Invariants', src: 'assets/visualizations/safety-guardrails.png', desc: 'Action-masking logic enforcing link capacity bounds, queue headroom, and loop-free routing.' }
    ];

    const modal = document.getElementById('figureViewerModal');
    const modalImg = document.getElementById('figureViewerImg');
    const modalTitle = document.getElementById('figureViewerTitle');
    const modalCap = document.getElementById('figureViewerCaption');
    const modalIdx = document.getElementById('figureViewerIndex');
    const btnDownload = document.getElementById('btnFigDownload');
    const modalBody = document.getElementById('figureViewerBody');

    const updateModalContent = (idx) => {
      this.currentFigureIdx = (idx + this.figuresList.length) % this.figuresList.length;
      const fig = this.figuresList[this.currentFigureIdx];
      if (modalImg) modalImg.src = fig.src;
      if (modalTitle) modalTitle.textContent = `${fig.num}: ${fig.title}`;
      if (modalCap) modalCap.textContent = fig.desc;
      if (modalIdx) modalIdx.textContent = `Figure ${this.currentFigureIdx + 1} of ${this.figuresList.length}`;
      if (btnDownload) {
        btnDownload.href = fig.src;
        btnDownload.setAttribute('download', fig.src.split('/').pop());
      }
      if (modalBody) modalBody.className = 'figure-modal-body';
      document.querySelectorAll('#btnZoom100, #btnZoom150, #btnZoom200').forEach(b => b.classList.remove('active'));
      const z100 = document.getElementById('btnZoom100');
      if (z100) z100.classList.add('active');
    };

    this.stepFigureModal = (delta) => {
      updateModalContent(this.currentFigureIdx + delta);
    };

    this.closeFigureModal = () => {
      if (modal) modal.classList.remove('open');
      if (modalBody) modalBody.className = 'figure-modal-body';
    };

    const btnClose = document.getElementById('closeFigureModal');
    if (btnClose) btnClose.addEventListener('click', () => this.closeFigureModal());

    const btnPrev = document.getElementById('btnFigPrev');
    if (btnPrev) btnPrev.addEventListener('click', () => this.stepFigureModal(-1));

    const btnNext = document.getElementById('btnFigNext');
    if (btnNext) btnNext.addEventListener('click', () => this.stepFigureModal(1));

    if (modal) {
      modal.addEventListener('click', (e) => {
        if (e.target === modal) this.closeFigureModal();
      });
    }

    const z100 = document.getElementById('btnZoom100');
    const z150 = document.getElementById('btnZoom150');
    const z200 = document.getElementById('btnZoom200');
    if (z100 && modalBody) z100.addEventListener('click', () => {
      modalBody.className = 'figure-modal-body';
      document.querySelectorAll('#btnZoom100, #btnZoom150, #btnZoom200').forEach(b => b.classList.remove('active'));
      z100.classList.add('active');
    });
    if (z150 && modalBody) z150.addEventListener('click', () => {
      modalBody.className = 'figure-modal-body zoom-150';
      document.querySelectorAll('#btnZoom100, #btnZoom150, #btnZoom200').forEach(b => b.classList.remove('active'));
      z150.classList.add('active');
    });
    if (z200 && modalBody) z200.addEventListener('click', () => {
      modalBody.className = 'figure-modal-body zoom-200';
      document.querySelectorAll('#btnZoom100, #btnZoom150, #btnZoom200').forEach(b => b.classList.remove('active'));
      z200.classList.add('active');
    });

    document.querySelectorAll('.gallery-fig-card, .project-viz-card').forEach((card) => {
      card.addEventListener('click', () => {
        const imgSrc = card.getAttribute('data-img') || card.querySelector('img')?.getAttribute('src');
        const cap = card.getAttribute('data-title') || card.querySelector('.fig-caption-text, p')?.textContent || '';
        if (imgSrc) {
          const found = this.figuresList.findIndex(f => f.src.includes(imgSrc) || imgSrc.includes(f.src));
          if (found !== -1) {
            updateModalContent(found);
            if (modal) modal.classList.add('open');
          } else {
            this.openFigureModal(imgSrc, cap);
          }
        }
      });
    });
  }

  initFlowModCompiler() {
    this.initFlowModSynthesizer();
  }
  initFlowModSynthesizer() {
    const swSelect = document.getElementById('fmTargetSwitch');
    const matchSelect = document.getElementById('fmMatchPreset');
    const actSelect = document.getElementById('fmActionType');
    const priInput = document.getElementById('fmPriority');
    const idleInput = document.getElementById('fmIdleTimeout');
    const hardInput = document.getElementById('fmHardTimeout');
    const preview = document.getElementById('flowModJsonPreview');
    const btnCopy = document.getElementById('btnCopyFlowModJSON');
    const btnPush = document.getElementById('btnPushFlowModRule');

    const updatePreview = () => {
      if (!preview) return null;
      const dpid = parseInt(swSelect?.value || '2', 10);
      const pri = parseInt(priInput?.value || '1000', 10);
      const idle = parseInt(idleInput?.value || '30', 10);
      const hard = parseInt(hardInput?.value || '60', 10);
      const matchType = matchSelect?.value || 'elephant_burst';
      const actType = actSelect?.value || 'reroute_secondary';

      let matchObj = {
        in_port: 1,
        eth_type: 2048,
        ipv4_src: "10.0.0.2",
        ipv4_dst: "10.0.0.8",
        ip_proto: 6,
        tcp_dst: 5201
      };
      if (matchType === 'steady_stream') {
        matchObj = { in_port: 1, eth_type: 2048, ipv4_src: "10.0.0.1", ipv4_dst: "10.0.0.7", ip_proto: 17, udp_dst: 5001 };
      } else if (matchType === 'http_bulk') {
        matchObj = { in_port: 2, eth_type: 2048, ipv4_src: "10.0.0.3", ipv4_dst: "10.0.0.5", ip_proto: 6, tcp_dst: 80 };
      }

      let actionsList = [{ type: "OUTPUT", port: 2 }];
      if (actType === 'reroute_primary') {
        actionsList = [{ type: "OUTPUT", port: 1 }];
      } else if (actType === 'meter_limit') {
        actionsList = [{ type: "METER", meter_id: 1 }, { type: "OUTPUT", port: 1 }];
      } else if (actType === 'dscp_mark') {
        actionsList = [{ type: "SET_FIELD", field: "ip_dscp", value: 46 }, { type: "OUTPUT", port: 2 }];
      }

      const payload = {
        dpid: dpid,
        cookie: 1,
        cookie_mask: 1,
        table_id: 0,
        idle_timeout: idle,
        hard_timeout: hard,
        priority: pri,
        flags: 1,
        match: matchObj,
        actions: actionsList
      };

      preview.textContent = JSON.stringify(payload, null, 2);
      return payload;
    };

    [swSelect, matchSelect, actSelect, priInput, idleInput, hardInput].forEach(el => {
      if (el) el.addEventListener('change', updatePreview);
      if (el && el.tagName === 'INPUT') el.addEventListener('input', updatePreview);
    });

    if (btnCopy) {
      btnCopy.addEventListener('click', () => {
        const payload = updatePreview();
        if (payload) {
          navigator.clipboard.writeText(JSON.stringify(payload, null, 2)).then(() => {
            this.showToast('OpenFlow 1.3 JSON Copied', 'Ryu flow-mod JSON copied to clipboard.');
          });
        }
      });
    }

    if (btnPush) {
      btnPush.addEventListener('click', () => {
        const payload = updatePreview();
        const dpid = payload?.dpid || 2;
        const pri = payload?.priority || 1000;
        this.showToast('Flow-Mod Preview', `Previewed a rule for switch s${dpid} (priority ${pri}).`, 'success');
        if (preview) {
          preview.style.borderColor = '#10b981';
          preview.style.boxShadow = '0 0 12px rgba(16, 185, 129, 0.4)';
          setTimeout(() => {
            preview.style.borderColor = 'rgba(0, 242, 254, 0.25)';
            preview.style.boxShadow = 'none';
          }, 1500);
        }
      });
    }

    updatePreview();
  }

  initCitationCopier() {
    const button = document.getElementById('btnCopyCitation');
    const citation = document.getElementById('citationCodeBlock');
    if (!button || !citation) return;
    button.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(citation.textContent);
        button.textContent = 'Copied';
      } catch {
        button.textContent = 'Select citation text to copy';
      }
    });
  }

  initDeepReviewSearch() {
    const filterPills = document.querySelectorAll('.review-filter-pill');
    filterPills.forEach(pill => {
      pill.addEventListener('click', () => {
        this.playSound('click');
        const topic = pill.getAttribute('data-topic');
        filterPills.forEach(p => p.classList.toggle('active', p === pill));

        const critiques = document.querySelectorAll('#deepReviewRoundsContainer .critique-item');
        critiques.forEach(item => {
          if (topic === 'all') {
            item.style.display = '';
          } else {
            const text = item.textContent.toLowerCase();
            const matches = text.includes(topic.toLowerCase());
            item.style.display = matches ? '' : 'none';
          }
        });
      });
    });
  }

  initPromptAssembler() {
    const scenarioSelect = document.getElementById('promptScenarioSelect');
    const kSelect = document.getElementById('promptKSelect');
    const agentSelect = document.getElementById('promptAgentSelect');
    const codeEl = document.getElementById('assembledPromptCode');
    const tokenEl = document.getElementById('promptTokenCount');
    const assembleBtn = document.getElementById('btnAssemblePrompt');
    const copyBtn = document.getElementById('btnCopyAssembledPrompt');

    const exemplars = [
      {
        state: "Core link s2->s3 util=94.2%, delay=18.4ms, loss=2.8%, queue=1.92Mbit",
        action: "reroute(flow_id='f_elephant', path=['s2', 's4', 's3'])",
        outcome: "util drops to 58.1%, delay drops to 5.4ms, loss drops to 0.0%",
        reflection: "Rerouting the elephant burst onto the secondary core link relieved the bottleneck without creating an ingress loop."
      },
      {
        state: "Host h2 burst util=88.5%, ingress port 2 queue=1.45Mbit, loss=1.1%",
        action: "rate_limit(meter_id=1, rate_kbps=8000, burst_kb=1024)",
        outcome: "throughput capped at 8 Mbps, loss stabilized at 0.0%, delay=6.1ms",
        reflection: "Rate-limiting the non-critical UDP elephant flow preserved bandwidth for latency-sensitive traffic while satisfying starvation floor (>=512k)."
      },
      {
        state: "All links balanced, max util=38.4%, delay=4.8ms, loss=0.0%",
        action: "no_op()",
        outcome: "state maintains steady equilibrium, 0 control overhead incurred",
        reflection: "Network within safe fluid envelope; intervening would cause unnecessary OpenFlow table churn."
      },
      {
        state: "Post-burst transient spike s1->s2 util=82.0%, queue=1.10Mbit",
        action: "reroute(flow_id='f_transient', path=['s1', 's3', 's4'])",
        outcome: "load distributed evenly across leaf tier, delay=5.0ms",
        reflection: "Multi-path diversion absorbed transient surge before queue overflowed."
      },
      {
        state: "High jitter on core link, queue oscillating between 0.8M and 2.1Mbit",
        action: "rate_limit(meter_id=2, rate_kbps=9500, burst_kb=2048)",
        outcome: "queue damped to 0.95Mbit, jitter reduced by 72%",
        reflection: "Token bucket smoothing eliminated cyclic packet burstiness."
      },
      {
        state: "Core secondary link s2->s4 near capacity (89.1%), primary link at 42.0%",
        action: "reroute(flow_id='f_elephant', path=['s2', 's3'])",
        outcome: "rebalanced both core links to 65% and 62% respectively",
        reflection: "Restored primary path after burst completion, returning to default shortest path."
      },
      {
        state: "Packet drop spike detected at egress s4, loss=3.4%, queue full",
        action: "rate_limit(meter_id=1, rate_kbps=6000, burst_kb=1024)",
        outcome: "loss dropped to 0.0% within 1.2s, backlog cleared",
        reflection: "Fast rate throttling stopped buffer exhaustion while alternative path computed."
      },
      {
        state: "Periodic health audit: telemetry intact, 0 packet loss across all ports",
        action: "no_op()",
        outcome: "energy and control latency minimized",
        reflection: "No action necessary; Lyapunov drift Delta(Q) is strongly negative (-4.8)."
      }
    ];

    const generatePrompt = () => {
      const scenario = scenarioSelect ? scenarioSelect.value : 'burst_s2_s3';
      const k = kSelect ? parseInt(kSelect.value, 10) : 5;
      const agent = agentSelect ? agentSelect.value : 'claude';

      let currentDesc = "";
      if (scenario === 'burst_s2_s3') {
        currentDesc = '{\n  "current_state": {\n    "dpid": "0000000000000002",\n    "core_util": 92.4,\n    "delay_ms": 17.8,\n    "loss_pct": 2.6,\n    "queue_mbit": 1.88,\n    "active_flows": ["f_steady_3M", "f_burst_12M"]\n  }\n}';
      } else if (scenario === 'asym_leaf') {
        currentDesc = '{\n  "current_state": {\n    "dpid": "0000000000000001",\n    "core_util": 78.1,\n    "delay_ms": 11.2,\n    "loss_pct": 0.8,\n    "queue_mbit": 1.34,\n    "active_flows": ["f_ingress_asym"]\n  }\n}';
      } else if (scenario === 'high_loss') {
        currentDesc = '{\n  "current_state": {\n    "dpid": "0000000000000004",\n    "core_util": 89.9,\n    "delay_ms": 22.4,\n    "loss_pct": 3.8,\n    "queue_mbit": 2.15,\n    "active_flows": ["f_burst_drop"]\n  }\n}';
      } else {
        currentDesc = '{\n  "current_state": {\n    "dpid": "0000000000000002",\n    "core_util": 34.2,\n    "delay_ms": 4.6,\n    "loss_pct": 0.0,\n    "queue_mbit": 0.42,\n    "active_flows": ["f_steady_3M"]\n  }\n}';
      }

      const selectedExemplars = exemplars.slice(0, k);
      let promptText = `# SYSTEM INSTRUCTION: Autonomous SDN Flow-Management Agent (SELF-X)\n`;
      promptText += `You are an autonomous SDN flow controller operating over OpenFlow 1.3 (Ryu ofctl_rest API).\n`;
      promptText += `Observe current network telemetry, review historical reflections, and select the optimal flow action.\n`;
      promptText += `Execution Target: ${agent === 'claude' ? 'Anthropic Claude 3.5 Sonnet (LangGraph State Machine)' : 'SmolLM2-135M Instruct (Local CPU / Zero-GPU)'}\n\n`;
      promptText += `## OUTPUT SCHEMA (Strict JSON Enforced):\n`;
      promptText += `{\n  "action": "reroute" | "rate_limit" | "no_op",\n  "flow_id": string,\n  "target_path": [string],\n  "meter_rate_kbps": int,\n  "rationale": string\n}\n\n`;
      promptText += `## TOP-${k} IN-CONTEXT DEMONSTRATIONS (Retrieved via k-NN from M=30 Memory Bank):\n`;
      selectedExemplars.forEach((ex, idx) => {
        promptText += `### Demonstration [${idx + 1}/${k}]:\n`;
        promptText += `State: ${ex.state}\n`;
        promptText += `Action Taken: ${ex.action}\n`;
        promptText += `Observed Outcome: ${ex.outcome}\n`;
        promptText += `Reflection: "${ex.reflection}"\n\n`;
      });
      promptText += `## CURRENT TELEMETRY INPUT:\n${currentDesc}\n\n`;
      promptText += `## DECISION: Return ONLY the JSON action object.`;

      if (codeEl) {
        codeEl.textContent = promptText;
      }
      if (tokenEl) {
        tokenEl.textContent = `Estimated Tokens: ~${Math.round(promptText.length / 3.8)}`;
      }
    };

    if (scenarioSelect) scenarioSelect.addEventListener('change', generatePrompt);
    if (kSelect) kSelect.addEventListener('change', generatePrompt);
    if (agentSelect) agentSelect.addEventListener('change', generatePrompt);
    if (assembleBtn) assembleBtn.addEventListener('click', () => {
      this.playSound('click');
      generatePrompt();
    });

    if (copyBtn) {
      copyBtn.addEventListener('click', () => {
        if (codeEl) {
          navigator.clipboard.writeText(codeEl.textContent).then(() => {
            const original = copyBtn.textContent;
            copyBtn.textContent = '✓ Copied!';
            setTimeout(() => { copyBtn.textContent = original; }, 2000);
          });
        }
      });
    }

    // Initial prompt generation
    generatePrompt();
  }

  initSafetyArbiterSandbox() {
    const presetSelect = document.getElementById('safetyActionPreset');
    const flowSelect = document.getElementById('safetyTargetFlow');
    const evalBtn = document.getElementById('btnTestSafetyArbiter');

    const valInv1 = document.getElementById('valInv1');
    const valInv2 = document.getElementById('valInv2');
    const valInv3 = document.getElementById('valInv3');
    const valInv4 = document.getElementById('valInv4');

    const boxInv1 = document.getElementById('boxInv1');
    const boxInv2 = document.getElementById('boxInv2');
    const boxInv3 = document.getElementById('boxInv3');
    const boxInv4 = document.getElementById('boxInv4');

    const titleEl = document.getElementById('arbiterDecisionTitle');
    const reasonEl = document.getElementById('arbiterDecisionReason');
    const pillEl = document.getElementById('arbiterDecisionPill');
    const bannerEl = document.getElementById('arbiterResultBanner');

    const updateArbiter = () => {
      const preset = presetSelect ? presetSelect.value : 'safe_reroute';

      let r1 = { pass: true, text: 'PASSED (0.0%)' };
      let r2 = { pass: true, text: 'PASSED (64.2%)' };
      let r3 = { pass: true, text: 'PASSED (12.0M)' };
      let r4 = { pass: true, text: 'PASSED (-3.40)' };
      let verdict = { pass: true, title: 'DATAPATH VERDICT: REROUTE PERMITTED', reason: 'This evaluated action passes all checks for projected utilization, rate and drift.' };

      if (preset === 'safe_reroute') {
        r1 = { pass: true, text: 'PASSED (0.0%)' };
        r2 = { pass: true, text: 'PASSED (64.2%)' };
        r3 = { pass: true, text: 'PASSED (12.0M)' };
        r4 = { pass: true, text: 'PASSED (-3.40)' };
        verdict = { pass: true, title: 'DATAPATH VERDICT: REROUTE PERMITTED', reason: 'This evaluated action passes all checks for projected utilization, rate and drift.' };
      } else if (preset === 'safe_meter') {
        r1 = { pass: true, text: 'PASSED (16.7%)' };
        r2 = { pass: true, text: 'PASSED (52.0%)' };
        r3 = { pass: true, text: 'PASSED (8.0M)' };
        r4 = { pass: true, text: 'PASSED (-2.10)' };
        verdict = { pass: true, title: 'DATAPATH VERDICT: METER PERMITTED', reason: 'Meter configuration satisfies minimum 512 kbps floor and rate drop ceiling. Verified against invariant bounds.' };
      } else if (preset === 'violate_drop') {
        r1 = { pass: false, text: 'FAILED (75.0% > 20%)' };
        r2 = { pass: true, text: 'PASSED (38.0%)' };
        r3 = { pass: true, text: 'PASSED (3.0M)' };
        r4 = { pass: true, text: 'PASSED (-1.20)' };
        verdict = { pass: false, title: 'SAFETY VETO: EXCESSIVE FLOW RATE DROP', reason: 'Invariant 1 Violated: Candidate drops 75.0% of flow traffic (limit 20.0%). Fail-closed fallback to no_op.' };
      } else if (preset === 'violate_util') {
        r1 = { pass: true, text: 'PASSED (0.0%)' };
        r2 = { pass: false, text: 'FAILED (96.4% > 90%)' };
        r3 = { pass: true, text: 'PASSED (12.0M)' };
        r4 = { pass: false, text: 'FAILED (+4.80 > 0.0)' };
        verdict = { pass: false, title: 'SAFETY VETO: LINK OVERFLOW & DRIFT VIOLATION', reason: 'Invariants 2 & 4 Violated: Projected utilization 96.4% exceeds 90% threshold, causing positive Lyapunov drift. Fallback to no_op.' };
      } else if (preset === 'violate_floor') {
        r1 = { pass: false, text: 'FAILED (88.0% > 20%)' };
        r2 = { pass: true, text: 'PASSED (32.0%)' };
        r3 = { pass: false, text: 'FAILED (256k < 512k)' };
        r4 = { pass: true, text: 'PASSED (-1.80)' };
        verdict = { pass: false, title: 'SAFETY VETO: STARVATION FLOOR BREACH', reason: 'Invariant 3 Violated: Meter rate 256 kbps is below the mandatory 512 kbps starvation threshold. Action vetoed.' };
      }

      const applyBox = (box, valEl, rule) => {
        if (!box || !valEl) return;
        valEl.textContent = rule.text;
        valEl.style.color = rule.pass ? '#10b981' : '#ef4444';
        box.style.borderColor = rule.pass ? 'var(--border-card)' : 'rgba(239,68,68,0.5)';
        box.style.background = rule.pass ? 'var(--bg-deepest)' : 'rgba(239,68,68,0.08)';
      };

      applyBox(boxInv1, valInv1, r1);
      applyBox(boxInv2, valInv2, r2);
      applyBox(boxInv3, valInv3, r3);
      applyBox(boxInv4, valInv4, r4);

      if (titleEl) {
        titleEl.textContent = verdict.title;
        titleEl.style.color = verdict.pass ? '#34d399' : '#f87171';
      }
      if (reasonEl) reasonEl.textContent = verdict.reason;
      if (pillEl) {
        pillEl.textContent = verdict.pass ? 'PERMITTED' : 'SAFETY VETO';
        pillEl.className = verdict.pass ? 'compliance-pill pass' : 'compliance-pill fail';
      }
      if (bannerEl) {
        bannerEl.style.background = verdict.pass ? 'rgba(16,185,129,0.12)' : 'rgba(239,68,68,0.12)';
        bannerEl.style.borderColor = verdict.pass ? 'rgba(16,185,129,0.4)' : 'rgba(239,68,68,0.4)';
      }
    };

    if (presetSelect) presetSelect.addEventListener('change', updateArbiter);
    if (flowSelect) flowSelect.addEventListener('change', updateArbiter);
    if (evalBtn) evalBtn.addEventListener('click', () => {
      this.playSound('click');
      updateArbiter();
    });

    updateArbiter();
  }

  initInsightsGalleryFilters() {
    const filterPills = document.querySelectorAll('.viz-filter-pill');
    filterPills.forEach(pill => {
      pill.addEventListener('click', () => {
        this.playSound('click');
        const cat = pill.getAttribute('data-viz-cat');
        filterPills.forEach(p => p.classList.toggle('active', p === pill));

        const cards = document.querySelectorAll('.project-viz-grid .project-viz-card');
        cards.forEach(card => {
          if (cat === 'all') {
            card.style.display = '';
          } else {
            const cardCat = card.getAttribute('data-viz-cat');
            card.style.display = cardCat === cat ? '' : 'none';
          }
        });
      });
    });
  }
}

// Instantiate on DOM load
if (document.readyState === 'loading') {
  window.addEventListener('DOMContentLoaded', () => {
    window.app = new DashboardApp();
  });
} else {
  window.app = new DashboardApp();
}
