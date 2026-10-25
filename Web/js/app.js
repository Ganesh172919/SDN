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
    this.initTheme();
    this.initLightbox();

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
        this.closeAllModals();
      } else if (e.key >= '1' && e.key <= '7') {
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

  closeAllModals() {
    document.querySelectorAll('.modal-overlay.open').forEach(m => {
      m.classList.remove('open');
    });
  }

  activateTab(targetId, updateHash = true) {
    this.closeAllModals();
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
          rateEl.textContent = `Tx: ${totalRate} Mbps | Rx: ${totalRate} Mbps (simulated)`;
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
        elephantStatus.innerHTML = '<span class="badge-tag" style="background:rgba(255,255,255,0.08); color:#94a3b8;">INACTIVE / IDLE</span>';
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
