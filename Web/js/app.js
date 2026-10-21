/**
 * app.js - Master Application Controller for SELF-X SDN Dashboard
 * Handles UI interactions, tabs, live telemetry updates, toast notifications,
 * Web Audio API synthesizer, dynamic SVG sparklines, hotkeys, and component coordination.
 */

// Audio synthesizer removed in compliance with project directives
class DummyAudioEngine {
  play() {}
  toggleMute() { return false; }
}

class DashboardApp {
  constructor() {
    this.audio = new DummyAudioEngine();
    this.appMode = 'simulation';
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
    this.initControls();
    this.initHotkeys();
    this.initModal();

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
    this.initAppMode();

    // Initial UI render
    this.updateUI();

    // Initial sparkline path generation
    this.renderAllSparklines();

    // Check for live Ryu backend connection
    this.checkLiveBackend();
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
    if (!['simulation', 'live'].includes(mode)) return;

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
      banner.className = `mode-state-banner ${simulation ? 'simulation-state' : 'loading-state'}`;
      title.textContent = simulation ? 'Simulation mode' : 'Live network mode';
      message.textContent = simulation
        ? 'Generated telemetry and actions are local to this browser.'
        : 'Loading controller status. No simulated values are used in this mode.';
    }

    if (pill && pillText) {
      pill.classList.toggle('simulating', simulation);
      pill.classList.remove('live', 'error');
      pillText.textContent = simulation ? 'SIMULATION MODE - GENERATED DATA' : 'LIVE NETWORK - CONNECTING';
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
      if (notify) this.showToast('Simulation Mode', 'Generated telemetry is active; no network requests are issued.', 'info');
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
      'btnTriggerRateLimit', 'btnStepAgent', 'btnTogglePlay', 'btnResetSimulation'
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
    ['metricLatencyDelta', 'metricThroughputDelta', 'metricLossDelta', 'metricLinkUtilDelta', 'metricRewardDelta'].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.innerHTML = '<span class="delta-chip" style="background: rgba(255, 255, 255, 0.08); color: var(--text-secondary);">Awaiting Data</span>';
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
      pill.classList.remove('simulating', 'live', 'error');
      pill.classList.add(state === 'connected' ? 'live' : state === 'error' ? 'error' : 'simulating');
    }
    if (pillText) pillText.textContent = state === 'connected'
      ? 'LIVE NETWORK - CONTROLLER CONNECTED'
      : state === 'error' ? 'LIVE NETWORK - DISCONNECTED' : 'LIVE NETWORK - LOADING';
  }

  playSound(type) {
    // Audio synthesizer removed in compliance with project directives
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
        html += `
          <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; padding: 1rem;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.6rem;">
              <h4 style="margin:0; font-size:0.9rem; color:#38bdf8;">${provider.toUpperCase()} Pilot</h4>
              <span class="badge-tag" style="background:rgba(16,185,129,0.15); color:#34d399;">${data.provenance || 'API Diagnostic'}</span>
            </div>
            <table class="detail-table" style="width:100%; font-size:0.75rem;">
              <tr><th>Target Model</th><td>${data.environment?.model || provider}</td></tr>
              <tr><th>Windows / Seeds</th><td>${data.cycles_per_condition_seed || 12} windows &bull; ${data.seeds?.length || 2} seeds</td></tr>
              <tr><th>Mean Latency</th><td>${a4.latency_ms ? a4.latency_ms.toFixed(2) + ' ms' : 'N/A'}</td></tr>
              <tr><th>Control Elapsed</th><td>${a4.control_elapsed_ms ? a4.control_elapsed_ms.toFixed(1) + ' ms' : 'N/A'}</td></tr>
              <tr><th>Decision Origins</th><td><code>${originStr}</code></td></tr>
              <tr><th>Fallback Windows</th><td>${a4.fallback_windows || 0}</td></tr>
              <tr><th>Safety Vetoes</th><td><span style="color:#34d399;">${a4.safety_vetoes || 0} (100% Compliant)</span></td></tr>
            </table>
          </div>
        `;
      }
      container.innerHTML = html || '<p style="color:var(--text-secondary); font-size:0.8rem;">No LLM diagnostic logs found.</p>';
    } catch (e) {
      container.innerHTML = `<p style="color:#f87171; font-size:0.8rem;">Unable to load LLM diagnostics: ${e.message}</p>`;
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
      // Ignore if user is typing in search input
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

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
      } else if (e.code === 'KeyM') {
        e.preventDefault();
        const btnSound = document.getElementById('btnSoundToggle');
        if (btnSound) btnSound.click();
      } else if (e.key === '?' || e.key === 'h' || e.key === 'H') {
        e.preventDefault();
        this.openShortcutsModal();
      } else if (e.code === 'Escape') {
        if (this.modalOverlay && this.modalOverlay.classList.contains('open')) {
          this.modalOverlay.classList.remove('open');
        }
      } else if (e.key >= '1' && e.key <= '6') {
        const tabBtns = document.querySelectorAll('.tab-btn');
        const idx = parseInt(e.key, 10) - 1;
        if (tabBtns[idx]) tabBtns[idx].click();
      }
    });

    const btnShortcuts = document.getElementById('btnShortcutsHelp');
    if (btnShortcuts) {
      btnShortcuts.addEventListener('click', () => {
        this.openShortcutsModal();
      });
    }
  }

  activateTab(targetId, updateHash = true) {
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    tabButtons.forEach(b => {
      if (b.getAttribute('data-tab') === targetId) {
        b.classList.add('active');
      } else {
        b.classList.remove('active');
      }
    });

    tabPanes.forEach(p => {
      if (p.id === targetId) {
        p.classList.add('active');
      } else {
        p.classList.remove('active');
      }
    });

    if (updateHash) {
      const hash = targetId.replace('tab-', '');
      try {
        history.replaceState(null, '', `#${hash}`);
      } catch (e) {}
    }

    // Refresh canvases immediately and after pane animation completes
    if (targetId === 'tab-topo' && this.topology) {
      this.topology.setupDPI();
      setTimeout(() => this.topology.setupDPI(), 60);
    } else if (targetId === 'tab-charts' && this.charts) {
      this.charts.renderAll();
      setTimeout(() => this.charts.renderAll(), 60);
    } else if (targetId === 'tab-ablation' && this.results) {
      this.results.onTabActivated();
      setTimeout(() => this.results.onTabActivated(), 60);
    }
  }

  checkHashRoute() {
    const hash = (window.location.hash || '').replace('#', '').toLowerCase();
    const map = {
      'topo': 'tab-topo',
      'topology': 'tab-topo',
      'agent': 'tab-agent',
      'cognition': 'tab-agent',
      'dag': 'tab-agent',
      'memory': 'tab-memory',
      'charts': 'tab-charts',
      'chart': 'tab-charts',
      'insights': 'tab-insights',
      'visualizations': 'tab-insights',
      'ablation': 'tab-ablation',
      'benchmarks': 'tab-ablation',
      'safety': 'tab-safety',
      'rules': 'tab-safety'
    };
    if (map[hash]) {
      this.activateTab(map[hash], false);
    }
  }

  initTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');

    tabButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        const targetId = btn.getAttribute('data-tab');
        this.playSound('click');
        this.activateTab(targetId, true);
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

  initControls() {
    // Inject Elephant Burst
    const btnBurst = document.getElementById('btnBurstElephant');
    if (btnBurst) {
      btnBurst.addEventListener('click', () => {
        if (!this.isSimulationMode()) return;
        this.playSound('burst');
        this.simulator.injectElephantBurst();
        this.showToast('Simulated Elephant Burst (12M)', 'Updated the local simulation only; no traffic was started.', 'warn');
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
        this.showToast('Simulated Steady Traffic', `Local steady-flow state is now ${active ? 'ACTIVE' : 'PAUSED'}. No traffic was started.`, 'info');
      });
    }

    // Manual Reroute
    const btnReroute = document.getElementById('btnTriggerReroute');
    if (btnReroute) {
      btnReroute.addEventListener('click', () => {
        if (!this.isSimulationMode()) return;
        this.playSound('reroute');
        this.simulator.manualReroute();
        this.showToast('Simulated Reroute', 'Updated the local simulation only; no network rule was sent.', 'info');
      });
    }

    // Manual Rate Limit
    const btnRateLimit = document.getElementById('btnTriggerRateLimit');
    if (btnRateLimit) {
      btnRateLimit.addEventListener('click', () => {
        if (!this.isSimulationMode()) return;
        this.playSound('click');
        this.simulator.manualRateLimit();
        this.showToast('Simulated Rate Limit', 'Updated the local simulation only; no meter was sent.', 'info');
      });
    }

    // Step Loop
    const btnStep = document.getElementById('btnStepAgent');
    if (btnStep) {
      btnStep.addEventListener('click', () => {
        if (!this.isSimulationMode()) return;
        this.playSound('step');
        this.simulator.step();
        this.showToast('Simulated Step', `Advanced the local simulation to cycle #${this.simulator.cycle}.`, 'info');
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
          this.showToast('Loop Paused', 'Simulation paused on current state.', 'info');
        }
      });
    }

    // Reset Simulation
    const btnReset = document.getElementById('btnResetSimulation');
    if (btnReset) {
      btnReset.addEventListener('click', () => {
        if (!this.isSimulationMode()) return;
        this.playSound('click');
        this.simulator.reset();
        this.showToast('Simulation Reset', 'Local simulation state, memory view, and cycle counters reset.', 'warn');
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
        this.showToast(`Condition ${mode} Activated`, `Switched simulation profile to ${mode}.`, 'success');
      });
    });
  }

  initModal() {
    this.modalOverlay = document.getElementById('nodeModalOverlay');
    this.modalClose = document.getElementById('btnModalClose');

    if (this.modalClose) {
      this.modalClose.addEventListener('click', () => {
        this.playSound('click');
        if (this.modalOverlay) this.modalOverlay.classList.remove('open');
      });
    }

    if (this.modalOverlay) {
      this.modalOverlay.addEventListener('click', (event) => {
        if (event.target === this.modalOverlay) {
          this.modalOverlay.classList.remove('open');
        }
      });
    }
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
              <td><kbd style="background:rgba(255,255,255,0.08); padding:3px 8px; border-radius:4px; font-family:var(--font-mono); border:1px solid rgba(255,255,255,0.2);">1 – 6</kbd></td>
              <td><strong>Switch Tabs</strong></td>
              <td>Jump to Agent DAG (1), Topo (2), Charts (3), Memory (4), Benchmarks (5), Rules (6)</td>
            </tr>
            <tr>
              <td><kbd style="background:rgba(255,255,255,0.08); padding:3px 8px; border-radius:4px; font-family:var(--font-mono); border:1px solid rgba(255,255,255,0.2);">M</kbd></td>
              <td><strong>Mute / Unmute</strong></td>
              <td>Toggle futuristic synthesizer SFX audio</td>
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
    const idEl = document.getElementById('nodeInspectorId');
    const statusEl = document.getElementById('nodeInspectorStatus');
    const rateEl = document.getElementById('nodeInspectorRate');
    const flowsEl = document.getElementById('nodeInspectorFlows');

    if (!idEl) return;

    if (node.type === 'switch') {
      idEl.textContent = `Switch ${node.id.toUpperCase()} (DPID: ${node.dpid})`;
      if (this.isSimulationMode()) {
        statusEl.textContent = 'SIMULATED / FLOWS ACTIVE';
        statusEl.className = 'badge-state ok';
        rateEl.textContent = `Tx: ${(typeof node.tx === 'number' ? node.tx.toFixed(1) : '0.0')} Mbps | Rx: ${(typeof node.rx === 'number' ? node.rx.toFixed(1) : '0.0')} Mbps (simulated)`;
        flowsEl.textContent = `${node.flows || 0} active flow entries (Table 0)`;
      } else {
        statusEl.textContent = 'UNVERIFIED / NO TELEMETRY';
        statusEl.className = 'badge-state error';
        rateEl.textContent = 'Tx: — | Rx: — (live telemetry unlinked)';
        flowsEl.textContent = 'Port telemetry not exposed by controller';
      }
    } else {
      idEl.textContent = `Host ${node.id.toUpperCase()} (${node.ip})`;
      statusEl.textContent = this.isSimulationMode() ? 'SIMULATED / ATTACHED' : 'UNVERIFIED / NO TELEMETRY';
      statusEl.className = 'badge-state ok';
      rateEl.textContent = `MAC: ${node.mac}`;
      flowsEl.textContent = 'Standard IP Stack';
    }

    this.openNodeModal(node);
  }

  openNodeModal(node) {
    if (!this.modalOverlay) return;

    const modalTitle = document.getElementById('modalTitle');
    const modalSubtitle = document.getElementById('modalSubtitle');
    const modalBody = document.getElementById('modalBody');

    if (node.type === 'switch') {
      modalTitle.textContent = `Switch ${node.id.toUpperCase()} — OpenFlow 1.3 Inspection`;
      if (this.isSimulationMode()) {
        modalSubtitle.textContent = `Datapath ID: ${node.dpid} | Browser Simulation Model`;
        modalBody.innerHTML = `
          <div style="margin-bottom:0.8rem; padding:0.5rem 0.8rem; background:rgba(245,158,11,0.1); border-left:3px solid #f59e0b; font-size:0.8rem; color:#fcd34d;">
            <strong>SIMULATION NOTICE:</strong> Port counters below are generated by the local browser discrete model for demonstration purposes. They do not represent live physical SDN switch counters.
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
    updateDeltaChip('metricLinkUtilDelta', utilVal, this.sparklineHistory.linkUtil, '%', false);
    updateDeltaChip('metricRewardDelta', rewVal, this.sparklineHistory.reward, 'pts', false);

    // Update elephant info status in Topo HUD
    const elephantStatus = document.getElementById('infoElephantStatus');
    if (elephantStatus) {
      if (!this.simulator.isElephantActive) {
        elephantStatus.innerHTML = '<span class="badge-tag" style="background:rgba(255,255,255,0.08); color:#94a3b8;">INACTIVE / IDLE</span>';
      } else if (this.simulator.isRerouted) {
        elephantStatus.innerHTML = '<span class="badge-tag accent-cyan">REROUTED VIA SEC (12M)</span>';
      } else {
        elephantStatus.innerHTML = '<span class="badge-tag" style="background:rgba(239,68,68,0.25); color:#f87171; border:1px solid rgba(239,68,68,0.5);">BURST ACTIVE ON PRIMARY</span>';
      }
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
      this.liveStatus = data;
      if (data.ryu_controller !== 'connected') {
        this.setLiveState('error', 'Controller is disconnected. Live metrics remain unavailable.', 'Live network disconnected');
        return;
      }
      const switchCount = Array.isArray(data.connected_switches) ? data.connected_switches.length : 0;
      this.setLiveState('connected', `Controller response received; ${switchCount} connected switch record(s). Metric cards remain empty because no live metric endpoint is exposed.`, 'Live network connected');
      this.playSound('success');
    } catch (e) {
      this.liveStatus = null;
      this.setLiveState('error', `Live status request failed: ${e.message}.`, 'Live network error');
    }
  }

  checkLiveBackend() {
    // The selected mode remains simulation until the user explicitly opts in.
  }
}

// Instantiate on DOM load
window.addEventListener('DOMContentLoaded', () => {
  window.app = new DashboardApp();
});
