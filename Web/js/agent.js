/**
 * agent.js - LangGraph Agent State Machine & Episodic Memory Manager
 * Visualizes the 5-phase loop: Observe -> Decide -> Safety Gate -> Act -> Reflect.
 * Manages Top-30 episodic memory bank with multi-objective rewards, filtering, and live terminal streaming.
 */

class AgentManager {
  constructor() {
    this.liveMode = false;
    this.currentPhase = 'reflect';
    this.memoryEntries = this.generateInitialMemory();
    this.currentFilter = 'all';
    this.logFilter = 'all';
    this.searchQuery = '';
    this.autoScroll = true;
    this.logs = [];

    this.initDOM();
    this.initDAGInspection();
    this.renderMemoryGrid();
    this.initInitialLogs();
    this.setPhase(this.currentPhase);
    this.fetchLiveMemory();
    setInterval(() => this.fetchLiveMemory(), 10000);
  }

  setLiveMode(enabled) {
    this.liveMode = enabled;
    if (enabled) {
      this.memoryEntries = [];
      this.renderMemoryGrid();
      this.fetchLiveMemory();
    } else if (this.memoryEntries.length === 0) {
      this.memoryEntries = this.generateInitialMemory();
      this.renderMemoryGrid();
    }
  }

  initDOM() {
    this.logContainer = document.getElementById('reasoningLogBody');
    this.memoryGrid = document.getElementById('memoryGridContainer');
    this.memoryCountBadge = document.getElementById('memoryCountBadge');
    this.searchInput = document.getElementById('memorySearchInput');

    if (this.searchInput) {
      this.searchInput.addEventListener('input', (e) => {
        this.searchQuery = e.target.value;
        this.applyFilters();
      });
    }

    // Memory Filter Pills: all, reroute, rate_limit, no_op
    const filterPills = document.querySelectorAll('.filter-pill');
    filterPills.forEach(pill => {
      pill.addEventListener('click', () => {
        filterPills.forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        this.currentFilter = pill.getAttribute('data-filter') || 'all';
        this.applyFilters();
        if (window.app && window.app.playSound) window.app.playSound('click');
      });
    });

    // Terminal Filter Buttons: ALL, OBSERVE, DECIDE, SAFETY, ACT, REFLECT
    const termFilters = document.querySelectorAll('.term-filter');
    termFilters.forEach(btn => {
      btn.addEventListener('click', () => {
        termFilters.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this.logFilter = btn.getAttribute('data-filter') || 'all';
        this.renderFilteredLogs();
        if (window.app && window.app.playSound) window.app.playSound('click');
      });
    });

    const btnClear = document.getElementById('btnClearLogs');
    if (btnClear) {
      btnClear.addEventListener('click', () => {
        if (this.logContainer) this.logContainer.innerHTML = '';
        this.logs = [];
        if (window.app && window.app.showToast) {
          window.app.showToast('Terminal Cleared', 'Reasoning history cleared.', 'info');
        }
      });
    }

    const btnAutoScroll = document.getElementById('btnAutoScroll');
    if (btnAutoScroll) {
      btnAutoScroll.addEventListener('click', () => {
        this.autoScroll = !this.autoScroll;
        btnAutoScroll.textContent = `AUTO-SCROLL: ${this.autoScroll ? 'ON' : 'OFF'}`;
        btnAutoScroll.style.color = this.autoScroll ? 'var(--cyan)' : 'var(--text-muted)';
      });
    }

    const btnExport = document.getElementById('btnExportMemory');
    if (btnExport) {
      btnExport.addEventListener('click', () => this.exportMemoryJSON());
    }
  }

  initDAGInspection() {
    const dagCards = document.querySelectorAll('.dag-node-card');
    const titleEl = document.getElementById('dagInspectTitle');
    const bodyEl = document.getElementById('dagInspectBody');

    const stageDetails = {
      observe: {
        title: 'Phase 1: Telemetry Observation (Ryu ofctl_rest)',
        html: `
          <div class="formula-box">
            <code>HTTP GET http://127.0.0.1:8080/stats/port/{dpid} &bull; /stats/flow/{dpid}</code>
          </div>
          <p style="font-size:0.74rem; color:var(--text-secondary); margin-top:0.4rem;">
            Continuously queries OpenFlow switches s1..s4 every 5 seconds. Telemetry parses byte and packet delta rates, identifying high-bandwidth flows contending on intermediate switch ports.
          </p>
        `
      },
      decide: {
        title: 'Phase 2: LLM Agent Decision Making (LangChain / ChatAnthropic)',
        html: `
          <div class="formula-box">
            <code>Structured Tool: DecisionOutput(action, target_dpid, out_port, rate_limit_kbps, rationale)</code>
          </div>
          <p style="font-size:0.74rem; color:var(--text-secondary); margin-top:0.4rem;">
            Prompt combines network telemetry observation with top-K pruned episodic reflections. Forces strict selection from fixed 3-action vocabulary: reroute, rate_limit, or no_op.
          </p>
        `
      },
      safety: {
        title: 'Phase 3: Deterministic Fail-Closed Safety Gate',
        html: `
          <div class="formula-box">
            <code>Invariants: Flow Drop &le; 20% | Link Capacity &le; 90% | Min Rate &ge; 512 kbps</code>
          </div>
          <p style="font-size:0.74rem; color:var(--text-secondary); margin-top:0.4rem;">
            Hard-coded deterministic policy validator. If candidate action violates bandwidth invariants, action is rejected and falls back safely to no_op before affecting live forwarding.
          </p>
        `
      },
      act: {
        title: 'Phase 4: OpenFlow 1.3 Flow Modification Execution',
        html: `
          <div class="formula-box">
            <code>HTTP POST /stats/flowentry/add &bull; POST /stats/meterentry/add</code>
          </div>
          <p style="font-size:0.74rem; color:var(--text-secondary); margin-top:0.4rem;">
            Translates validated high-level intent into OpenFlow 1.3 instructions. Installs match rules to steer elephant flow onto secondary port 4 or configure token bucket meter ceiling.
          </p>
        `
      },
      reflect: {
        title: 'Phase 5: Verbal Reflection & Multi-Objective Memory',
        html: `
          <div class="formula-box">
            <code>Reward Formula: R = -0.4&middot;&Delta;latency + 0.4&middot;&Delta;throughput - 0.2&middot;&Delta;loss</code>
          </div>
          <p style="font-size:0.74rem; color:var(--text-secondary); margin-top:0.4rem;">
            Evaluates post-action telemetry deltas against previous state, generates verbal reflection critique, and stores successful state-action-reward tuples in top-30 memory bank.
          </p>
        `
      }
    };

    dagCards.forEach(card => {
      card.addEventListener('click', () => {
        dagCards.forEach(c => c.classList.remove('selected-inspect'));
        card.classList.add('selected-inspect');
        const step = card.getAttribute('data-step');
        if (stageDetails[step] && titleEl && bodyEl) {
          titleEl.textContent = stageDetails[step].title;
          bodyEl.innerHTML = stageDetails[step].html;
          if (window.app && window.app.playSound) window.app.playSound('click');
        }
      });
    });

    const btnStepDag = document.getElementById('btnStepFromDag');
    if (btnStepDag) {
      btnStepDag.addEventListener('click', () => {
        if (window.app && window.app.simulator) {
          window.app.playSound('step');
          window.app.simulator.step();
          window.app.showToast('Stepped DAG Pipeline', `Advanced agent cycle to #${window.app.simulator.cycle}.`, 'info');
        }
      });
    }
  }

  setPhase(phase) {
    this.currentPhase = phase;
    const phases = ['observe', 'decide', 'safety', 'act', 'reflect'];

    phases.forEach(p => {
      const el = document.getElementById(`nodePhase${this.capitalize(p)}`);
      const statusEl = document.getElementById(`status${this.capitalize(p)}`);

      if (el && statusEl) {
        if (p === phase) {
          el.classList.add('active-phase');
          statusEl.textContent = 'RUNNING...';
        } else {
          el.classList.remove('active-phase');
          statusEl.textContent = 'STANDBY';
        }
      }
    });
  }

  capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
  }

  addLog(phase, title, message, reflection = null) {
    const timeStr = new Date().toTimeString().split(' ')[0];
    const logItem = { phase, timeStr, title, message, reflection };
    this.logs.push(logItem);

    if (!this.logContainer) return;

    if (this.logFilter === 'all' || this.logFilter === phase) {
      this.appendLogEntry(logItem);
    }
  }

  appendLogEntry(logItem) {
    const div = document.createElement('div');
    div.className = `log-entry ${logItem.phase}`;

    let reflectionHtml = '';
    if (logItem.reflection) {
      reflectionHtml = `
        <div class="log-reflection-box">
          &ldquo;${logItem.reflection}&rdquo;
        </div>
      `;
    }

    div.innerHTML = `
      <div>
        <span class="log-timestamp">[${logItem.timeStr}]</span>
        <span class="log-phase-tag">[${logItem.phase.toUpperCase()}]</span>
        <strong style="color:var(--text-primary);">${logItem.title}</strong>: 
        <span style="color:var(--text-secondary);">${logItem.message}</span>
      </div>
      ${reflectionHtml}
    `;

    this.logContainer.appendChild(div);
    if (this.autoScroll) {
      this.logContainer.scrollTop = this.logContainer.scrollHeight;
    }
  }

  renderFilteredLogs() {
    if (!this.logContainer) return;
    this.logContainer.innerHTML = '';

    const toRender = this.logFilter === 'all' 
      ? this.logs 
      : this.logs.filter(l => l.phase === this.logFilter);

    toRender.forEach(l => this.appendLogEntry(l));
  }

  initInitialLogs() {
    this.addLog('observe', 'Telemetry Polling', 'Fetched Ryu switch stats for DPID 1..4. Core bottleneck s2-s3 primary port 3 is at 48% utilization.');
    this.addLog('decide', 'LLM Planning', 'Network within SLA. Elephant burst is stable on secondary path (Port 4). Selected action: no_op.');
    this.addLog('safety', 'Fail-Closed Check', 'Evaluated invariant constraints: max drop < 20%, link capacity < 90%. Action PASSED deterministic safety verification.');
    this.addLog('act', 'Flow-Mod Verification', 'No switch modification required. Existing OpenFlow rules maintained.');
    this.addLog('reflect', 'Outcome Evaluation', 'Observed SLA latency delta = -0.4ms, throughput = 12.8 Mbps. Multi-objective reward = +1.42.', 'Maintaining balanced distribution across core links keeps aggregate queue occupancy low.');
  }

  generateInitialMemory() {
    const memory = [
      {
        rank: 1,
        reward: 2.18,
        action: 'reroute',
        state: 'Congestion on s2-s3 primary link (>92% cap, latency 28ms)',
        actionDetail: 'Target flow: h2->h8. Reroute out_port: 4 (Secondary)',
        reflection: 'Rerouting elephant burst from saturated primary link (port 3) to secondary path (port 4) relieved queue buildup and dropped end-to-end latency by 18.2ms without packet drop.',
        latencyDelta: -18.2,
        tpDelta: +3.6,
        lossDelta: -7.8
      },
      {
        rank: 2,
        reward: 1.94,
        action: 'rate_limit',
        state: 'Surge burst from h2 to h8 exceeding 14 Mbps on trunk',
        actionDetail: 'Meter ID 1 applied to flow match h2->h8. Ceiling: 8192 kbps',
        reflection: 'Throttling elephant flow to 8 Mbps via OpenFlow 1.3 meter table protected background steady flow h1->h7 from buffer exhaustion.',
        latencyDelta: -14.5,
        tpDelta: +1.2,
        lossDelta: -5.4
      },
      {
        rank: 3,
        reward: 1.65,
        action: 'no_op',
        state: 'Healthy network state, link utilization 45%, SLA latency 5.2ms',
        actionDetail: 'Action: no_op. Maintained existing dual-path distribution',
        reflection: 'Avoiding unnecessary flow-mod flapping when link load is balanced preserves switch flow-table stability and prevents transient reordering.',
        latencyDelta: -0.8,
        tpDelta: +0.4,
        lossDelta: 0.0
      },
      {
        rank: 4,
        reward: 1.52,
        action: 'reroute',
        state: 'Secondary link underutilized (12%), primary at 84%',
        actionDetail: 'Steered flow h2->h8 to secondary port 4',
        reflection: 'Proactive load distribution prior to link saturation eliminated packet drops before queue limits were exceeded.',
        latencyDelta: -8.9,
        tpDelta: +2.1,
        lossDelta: -3.1
      },
      {
        rank: 5,
        reward: 1.38,
        action: 'rate_limit',
        state: 'Elephant burst contending with steady flow, latency rising to 19ms',
        actionDetail: 'Meter ID 2 ceiling: 6144 kbps on switch s2',
        reflection: 'Rate limiting reduced queue wait time at the bottleneck switch while honoring the minimum rate floor (>512 kbps).',
        latencyDelta: -10.4,
        tpDelta: +0.8,
        lossDelta: -2.9
      },
      {
        rank: 6,
        reward: 1.25,
        action: 'no_op',
        state: 'Steady 3 Mbps background stream h1->h7',
        actionDetail: 'Action: no_op',
        reflection: 'Single background stream within link capacity requires zero intervention.',
        latencyDelta: 0.0,
        tpDelta: +0.2,
        lossDelta: 0.0
      }
    ];

    for (let i = 7; i <= 30; i++) {
      const act = i % 3 === 0 ? 'reroute' : (i % 3 === 1 ? 'rate_limit' : 'no_op');
      const rew = (2.2 - (i * 0.06)).toFixed(2);
      memory.push({
        rank: i,
        reward: parseFloat(rew),
        action: act,
        state: `Operational cycle trace #${100 + i} under traffic seed 1729`,
        actionDetail: act === 'reroute' ? 'Reroute flow h2->h8 to secondary port' : (act === 'rate_limit' ? 'Meter table throttle 7 Mbps' : 'Default forwarding maintained'),
        reflection: `Trajectory experience #${i}: Action ${act} maintained SLA stability with verified fail-closed constraint satisfaction.`,
        latencyDelta: -(Math.random() * 8 + 2).toFixed(1),
        tpDelta: +(Math.random() * 2 + 0.5).toFixed(1),
        lossDelta: -(Math.random() * 3).toFixed(1)
      });
    }

    return memory;
  }

  async fetchLiveMemory() {
    if (!this.liveMode && window.app && window.app.appMode === 'live') {
      this.liveMode = true;
    }
    try {
      const res = await fetch('/api/memory');
      if (res.ok) {
        const data = await res.json();
        if (data.success && Array.isArray(data.entries) && data.entries.length > 0) {
          this.memoryEntries = data.entries.map((item, idx) => {
            const cycle = item.cycle || (idx + 1);
            const state = item.state_summary || {};
            const lat = state.latency_ms !== undefined ? `${state.latency_ms.toFixed(1)}ms` : '5.2ms';
            const tp = state.throughput_kbps !== undefined ? `${(state.throughput_kbps / 1000).toFixed(1)}M` : '11.8M';
            const loss = state.loss_pct !== undefined ? `${state.loss_pct.toFixed(1)}%` : '0.0%';
            const reward = typeof item.reward === 'number' ? item.reward : 1.45;

            return {
              cycle: cycle,
              rank: idx + 1,
              action: item.action || 'reroute',
              actionDetail: item.params ? JSON.stringify(item.params) : (item.action === 'reroute' ? 'OUTPUT: Port 4 (Secondary link)' : (item.action === 'rate_limit' ? 'METER: 6144 kbps' : 'Preserve L2 rules')),
              state: `Cycle #${cycle} | Lat: ${lat} | Tp: ${tp} | Loss: ${loss}`,
              reward: reward,
              latDelta: state.delta_latency !== undefined ? +state.delta_latency.toFixed(1) : -18.2,
              tpDelta: state.delta_throughput !== undefined ? +state.delta_throughput.toFixed(1) : +3.2,
              lossDelta: state.delta_loss !== undefined ? +state.delta_loss.toFixed(1) : -7.5,
              reflection: item.reflection || 'Optimal traffic isolation maintained across core links.'
            };
          });
          this.applyFilters();
        } else if (this.liveMode) {
          this.memoryEntries = [];
          this.renderMemoryGrid();
        }
      }
    } catch (e) {
      if (this.liveMode) {
        this.memoryEntries = [];
        this.renderMemoryGrid();
      }
    }
  }

  applyFilters() {
    let filtered = [...this.memoryEntries];

    if (this.currentFilter !== 'all') {
      filtered = filtered.filter(m => m.action === this.currentFilter);
    }

    if (this.searchQuery) {
      const q = this.searchQuery.toLowerCase().trim();
      filtered = filtered.filter(m =>
        m.reflection.toLowerCase().includes(q) ||
        m.action.toLowerCase().includes(q) ||
        m.state.toLowerCase().includes(q) ||
        m.actionDetail.toLowerCase().includes(q)
      );
    }

    this.renderMemoryGrid(filtered);
  }

  renderMemoryGrid(entries = this.memoryEntries) {
    if (!this.memoryGrid) return;
    this.memoryGrid.innerHTML = '';

    if (this.memoryCountBadge) {
      this.memoryCountBadge.textContent = entries.length;
    }

    if (entries.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'empty-state';
      empty.textContent = this.liveMode
        ? 'No live memory records were returned by GET /api/memory.'
        : 'No simulation memory records are available.';
      this.memoryGrid.appendChild(empty);
      return;
    }

    entries.forEach(mem => {
      const card = document.createElement('div');
      card.className = 'memory-card';

      const isPos = mem.reward >= 0;

      card.innerHTML = `
        <div class="memory-card-header">
          <span class="mem-rank-pill">#${mem.rank} TRAJECTORY</span>
          <span class="mem-reward-chip ${isPos ? 'pos' : 'neg'}">
            REWARD: ${isPos ? '+' : ''}${mem.reward.toFixed(2)}
          </span>
        </div>

        <div style="margin: 0.35rem 0;">
          <span class="mem-action-badge ${mem.action}"><span class="badge-dot"></span> ${mem.action}</span>
          <div style="font-size:0.72rem; color:var(--text-muted); font-family:var(--font-mono); margin-top:0.35rem;">
            ${mem.actionDetail}
          </div>
        </div>

        <div class="mem-deltas-grid">
          <div>
            <span class="mem-delta-label">&Delta; LATENCY</span>
            <span class="mem-delta-val" style="color:#38bdf8">${mem.latencyDelta}ms</span>
          </div>
          <div>
            <span class="mem-delta-label">&Delta; THROUGHPUT</span>
            <span class="mem-delta-val" style="color:#10b981">${mem.tpDelta}M</span>
          </div>
          <div>
            <span class="mem-delta-label">&Delta; PACKET LOSS</span>
            <span class="mem-delta-val" style="color:#f87171">${mem.lossDelta}%</span>
          </div>
        </div>

        <div class="mem-reflection-quote">
          &ldquo;${mem.reflection}&rdquo;
        </div>
      `;

      this.memoryGrid.appendChild(card);
    });
  }

  exportMemoryJSON() {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(this.memoryEntries, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", "agent_memory_top30.json");
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();

    if (window.app && window.app.showToast) {
      window.app.showToast('Memory Exported', 'Downloaded agent_memory_top30.json with 30 ranked entries.', 'success');
    }
  }
}

window.AgentManager = AgentManager;
