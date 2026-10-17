/**
 * results.js - Integration with Public Read-Only Results APIs for SELF-X
 * Handles:
 *   - Fetching validated saved experiment runs from GET /api/results
 *   - Managing loading, error, empty, and populated states
 *   - Displaying run status, stage, provenance, and summary metrics
 *   - Rendering metric time series (latency, throughput, loss, reward)
 *   - Comparing completed A0/A1/A2 runs via GET /api/results/compare
 *   - User-triggered manual refresh
 *   - Strict data integrity: preserving unavailable metrics, distinguishing provenance,
 *     never presenting failed/incomplete runs as successful, safe DOM rendering.
 */

class ExperimentResultsManager {
  constructor(app) {
    this.app = app;
    this.runs = [];
    this.selectedRunId = null;
    this.selectedRunSummary = null;
    this.selectedRunMetrics = null;
    this.selectedRunTrace = null;
    this.comparisonResults = null;
    this.isLoading = false;
    this.error = null;

    // Charts for selected run time series
    this.chartLatency = null;
    this.chartThroughput = null;
    this.chartLoss = null;
    this.chartReward = null;

    // Filter state for run selector
    this.stageFilter = 'all';

    this.initElements();
    this.initCharts();
    this.initEvents();

    // Initial fetch of saved experiment results
    this.fetchResults(false);
  }

  initElements() {
    this.loadingEl = document.getElementById('resultsLoadingState');
    this.errorEl = document.getElementById('resultsErrorState');
    this.errorMessageEl = document.getElementById('resultsErrorMessage');
    this.emptyEl = document.getElementById('resultsEmptyState');
    this.populatedEl = document.getElementById('resultsPopulatedState');
    this.runsListEl = document.getElementById('resultsRunsList');
    this.runsCountBadge = document.getElementById('resultsCountBadge');
    this.refreshBtn = document.getElementById('btnRefreshResults');
    this.retryBtn = document.getElementById('btnRetryResults');

    // Run detail elements
    this.detailContainer = document.getElementById('selectedRunDetail');
    this.detailRunId = document.getElementById('detailRunId');
    this.detailStage = document.getElementById('detailStage');
    this.detailStatus = document.getElementById('detailStatus');
    this.detailProvenance = document.getElementById('detailProvenance');
    this.detailCreated = document.getElementById('detailCreated');
    this.detailDuration = document.getElementById('detailDuration');
    this.detailGitCommit = document.getElementById('detailGitCommit');
    this.detailTopology = document.getElementById('detailTopology');
    this.detailWorkload = document.getElementById('detailWorkload');
    this.detailErrorNotice = document.getElementById('detailErrorNotice');
    this.detailErrorMessage = document.getElementById('detailErrorMessage');

    // KPI Summary elements
    this.kpiLatency = document.getElementById('resKpiLatency');
    this.kpiThroughput = document.getElementById('resKpiThroughput');
    this.kpiLoss = document.getElementById('resKpiLoss');
    this.kpiReward = document.getElementById('resKpiReward');

    // Comparison elements
    this.comparisonSection = document.getElementById('resultsComparisonSection');
    this.comparisonCardsContainer = document.getElementById('resultsComparisonCards');
    this.comparisonTableBody = document.getElementById('resultsComparisonTableBody');
    this.comparisonNotice = document.getElementById('resultsComparisonNotice');

    // Trace elements
    this.traceSection = document.getElementById('resultsTraceSection');
    this.traceTableBody = document.getElementById('resultsTraceTableBody');
    this.traceCountBadge = document.getElementById('resultsTraceCountBadge');
  }

  initCharts() {
    if (typeof MiniLineChart === 'undefined') return;

    this.chartLatency = new MiniLineChart('runChartLatency', {
      lineColor: '#38bdf8',
      fillColor: 'rgba(56, 189, 248, 0.22)',
      unit: 'ms',
      minY: 0
    });

    this.chartThroughput = new MiniLineChart('runChartThroughput', {
      lineColor: '#10b981',
      fillColor: 'rgba(16, 185, 129, 0.22)',
      unit: 'kbps',
      minY: 0
    });

    this.chartLoss = new MiniLineChart('runChartLoss', {
      lineColor: '#ef4444',
      fillColor: 'rgba(239, 68, 68, 0.22)',
      unit: '%',
      minY: 0,
      maxY: 100
    });

    this.chartReward = new MiniLineChart('runChartReward', {
      lineColor: '#a855f7',
      fillColor: 'rgba(168, 85, 247, 0.22)',
      unit: '',
      minY: null
    });
  }

  initEvents() {
    if (this.refreshBtn) {
      this.refreshBtn.addEventListener('click', () => {
        if (this.app && this.app.playSound) this.app.playSound('click');
        this.fetchResults(true);
      });
    }

    if (this.retryBtn) {
      this.retryBtn.addEventListener('click', () => {
        if (this.app && this.app.playSound) this.app.playSound('click');
        this.fetchResults(true);
      });
    }

    // Filter pills (all, A0, A1, A2)
    document.querySelectorAll('.results-filter-pill').forEach((pill) => {
      pill.addEventListener('click', () => {
        document.querySelectorAll('.results-filter-pill').forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        this.stageFilter = pill.dataset.filter || 'all';
        this.renderRunsList();
      });
    });
  }

  onTabActivated() {
    if (this.chartLatency) this.chartLatency.setupDPI();
    if (this.chartThroughput) this.chartThroughput.setupDPI();
    if (this.chartLoss) this.chartLoss.setupDPI();
    if (this.chartReward) this.chartReward.setupDPI();
    this.renderCharts();
  }

  async fetchResults(notifyUser = false) {
    this.isLoading = true;
    this.error = null;
    this.showState('loading');

    try {
      const response = await fetch('/api/results', { cache: 'no-store' });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status} while fetching results index`);
      }
      const data = await response.json();
      this.runs = Array.isArray(data.results) ? data.results : [];

      if (this.runsCountBadge) {
        this.runsCountBadge.textContent = this.runs.length;
        this.runsCountBadge.style.display = this.runs.length > 0 ? 'inline-flex' : 'none';
      }

      if (this.runs.length === 0) {
        this.showState('empty');
        if (notifyUser && this.app && this.app.showToast) {
          this.app.showToast('Results Refreshed', 'No saved experiment result bundles exist yet.', 'info');
        }
        return;
      }

      this.showState('populated');
      this.renderRunsList();

      // Automatically select the latest or first run
      const runToSelect = this.runs.find(r => r.run_id === this.selectedRunId) || this.runs[0];
      if (runToSelect) {
        await this.selectRun(runToSelect.run_id);
      }

      // Check for completed A0, A1, A2 runs for comparative evaluation
      await this.evaluateComparisons();

      if (notifyUser && this.app && this.app.showToast) {
        this.app.showToast('Results Refreshed', `Loaded ${this.runs.length} saved experiment run(s).`, 'success');
      }
    } catch (err) {
      this.error = err.message || 'Unknown network error';
      this.showState('error', this.error);
      if (notifyUser && this.app && this.app.showToast) {
        this.app.showToast('Results Error', this.error, 'warn');
      }
    } finally {
      this.isLoading = false;
    }
  }

  showState(state, message = '') {
    if (this.loadingEl) this.loadingEl.style.display = state === 'loading' ? 'block' : 'none';
    if (this.errorEl) this.errorEl.style.display = state === 'error' ? 'block' : 'none';
    if (this.emptyEl) this.emptyEl.style.display = state === 'empty' ? 'block' : 'none';
    if (this.populatedEl) this.populatedEl.style.display = state === 'populated' ? 'block' : 'none';

    if (state === 'error' && this.errorMessageEl) {
      this.errorMessageEl.textContent = message;
    }
  }

  renderRunsList() {
    if (!this.runsListEl) return;
    this.runsListEl.innerHTML = '';

    const filtered = this.runs.filter((run) => {
      if (this.stageFilter === 'all') return true;
      const stage = (run.experiment && run.experiment.stage) || '';
      return stage.toUpperCase() === this.stageFilter.toUpperCase();
    });

    if (filtered.length === 0) {
      const emptyItem = document.createElement('div');
      emptyItem.className = 'results-filter-empty';
      emptyItem.textContent = `No runs found for filter "${this.stageFilter}".`;
      this.runsListEl.appendChild(emptyItem);
      return;
    }

    filtered.forEach((run) => {
      const card = document.createElement('div');
      card.className = `run-selector-card ${run.run_id === this.selectedRunId ? 'active' : ''}`;
      card.dataset.runId = run.run_id;

      const stage = (run.experiment && run.experiment.stage) || 'UNK';
      const statusClass = run.status === 'completed' ? 'ok' : run.status === 'failed' ? 'error' : 'neutral';
      const provClass = run.provenance === 'live' ? 'prov-live' : run.provenance === 'recorded_testbed' ? 'prov-recorded' : 'prov-sim';

      card.innerHTML = `
        <div class="run-selector-header">
          <span class="ablation-tag tag-${stage.toLowerCase()}">${this.escapeText(stage)}</span>
          <span class="badge-state ${statusClass}">${this.escapeText(run.status.toUpperCase())}</span>
        </div>
        <div class="run-selector-id" title="${this.escapeText(run.run_id)}">${this.escapeText(run.run_id)}</div>
        <div class="run-selector-meta">
          <span class="provenance-pill ${provClass}">${this.escapeText(run.provenance)}</span>
          <span class="run-time">${this.formatTimestamp(run.created_at_utc)}</span>
        </div>
        <div class="run-selector-footer">
          <span>${run.metric_count || 0} samples</span>
          <span>${run.duration_seconds ? run.duration_seconds + 's' : '--'}</span>
        </div>
      `;

      card.addEventListener('click', () => {
        if (this.app && this.app.playSound) this.app.playSound('click');
        this.selectRun(run.run_id);
      });

      this.runsListEl.appendChild(card);
    });
  }

  async selectRun(runId) {
    this.selectedRunId = runId;
    this.renderRunsList(); // Update active card state

    const runMeta = this.runs.find(r => r.run_id === runId);
    if (!runMeta) return;

    // Reset current run detail views
    this.resetRunDetails(runMeta);

    // Fetch summary and metrics in parallel
    try {
      const [summaryRes, metricsRes] = await Promise.all([
        fetch(`/api/results/${encodeURIComponent(runId)}/summary`, { cache: 'no-store' }),
        fetch(`/api/results/${encodeURIComponent(runId)}/metrics`, { cache: 'no-store' })
      ]);

      // Handle summary response
      if (summaryRes.status === 200) {
        const summaryData = await summaryRes.json();
        this.selectedRunSummary = summaryData;
        this.renderRunSummary(summaryData);
      } else if (summaryRes.status === 409) {
        // Failed or incomplete run
        const errData = await summaryRes.json();
        this.handleIncompleteOrFailedRun(errData, runMeta);
      } else {
        this.renderRunSummaryUnavailable(`HTTP ${summaryRes.status} loading summary`);
      }

      // Handle metrics response
      if (metricsRes.status === 200) {
        const metricsData = await metricsRes.json();
        this.selectedRunMetrics = metricsData.metrics || [];
        this.renderMetricCharts(this.selectedRunMetrics);
      } else {
        this.renderChartsUnavailable();
      }

      // Fetch trace if available
      if (runMeta.has_trace) {
        this.fetchRunTrace(runId);
      } else if (this.traceSection) {
        this.traceSection.style.display = 'none';
      }
    } catch (err) {
      this.renderRunSummaryUnavailable(err.message || 'Error loading run details');
      this.renderChartsUnavailable();
    }
  }

  resetRunDetails(meta) {
    if (this.detailRunId) this.detailRunId.textContent = meta.run_id;
    if (this.detailStage) {
      const stage = (meta.experiment && meta.experiment.stage) || 'UNKNOWN';
      this.detailStage.textContent = stage;
      this.detailStage.className = `ablation-tag tag-${stage.toLowerCase()}`;
    }
    if (this.detailStatus) {
      this.detailStatus.textContent = meta.status.toUpperCase();
      this.detailStatus.className = `badge-state ${meta.status === 'completed' ? 'ok' : meta.status === 'failed' ? 'error' : 'neutral'}`;
    }
    if (this.detailProvenance) {
      this.detailProvenance.textContent = `PROVENANCE: ${meta.provenance.toUpperCase()}`;
      const provClass = meta.provenance === 'live' ? 'prov-live' : meta.provenance === 'recorded_testbed' ? 'prov-recorded' : 'prov-sim';
      this.detailProvenance.className = `provenance-pill ${provClass}`;
    }
    if (this.detailCreated) this.detailCreated.textContent = meta.created_at_utc || '--';
    if (this.detailDuration) this.detailDuration.textContent = meta.duration_seconds ? `${meta.duration_seconds}s` : '--';
    if (this.detailGitCommit) this.detailGitCommit.textContent = meta.git_commit ? meta.git_commit.substring(0, 10) : 'unknown';
    if (this.detailTopology) {
      const top = meta.topology || {};
      this.detailTopology.textContent = `${top.switches || 4} switches, ${top.hosts || 8} hosts (${top.openflow || 'OF 1.3'})`;
    }
    if (this.detailWorkload) {
      const wk = meta.workload || {};
      this.detailWorkload.textContent = `${wk.steady_mbps || 3}M steady, ${wk.traffic_generator || 'standard'}`;
    }

    if (this.detailErrorNotice) this.detailErrorNotice.style.display = 'none';
  }

  handleIncompleteOrFailedRun(errorPayload, runMeta) {
    if (this.detailErrorNotice) {
      this.detailErrorNotice.style.display = 'flex';
      const msg = (errorPayload.error || 'Run did not complete successfully');
      const detail = (errorPayload.run && errorPayload.run.error && errorPayload.run.error.message) || '';
      if (this.detailErrorMessage) {
        this.detailErrorMessage.textContent = detail ? `${msg}: ${detail}` : msg;
      }
    }
    // Set KPIs to unavailable
    this.renderMetricKpi(this.kpiLatency, null, 'ms');
    this.renderMetricKpi(this.kpiThroughput, null, 'kbps');
    this.renderMetricKpi(this.kpiLoss, null, '%');
    this.renderMetricKpi(this.kpiReward, null, 'pts');
  }

  renderRunSummary(summaryData) {
    if (this.detailErrorNotice) this.detailErrorNotice.style.display = 'none';
    const metrics = (summaryData.summary && summaryData.summary.metrics) || {};

    this.renderMetricKpi(this.kpiLatency, metrics.latency_ms, 'ms');
    this.renderMetricKpi(this.kpiThroughput, metrics.throughput_kbps, 'kbps');
    this.renderMetricKpi(this.kpiLoss, metrics.loss_pct, '%');
    this.renderMetricKpi(this.kpiReward, metrics.reward, 'pts');
  }

  renderMetricKpi(element, metricObj, fallbackUnit = '') {
    if (!element) return;
    const valEl = element.querySelector('.kpi-val') || element;
    const unitEl = element.querySelector('.kpi-unit');

    if (!metricObj || metricObj.status === 'unavailable' || metricObj.value === null || metricObj.value === undefined) {
      valEl.textContent = 'Unavailable';
      valEl.classList.add('unavailable-text');
      if (unitEl) unitEl.textContent = '';
      return;
    }

    valEl.classList.remove('unavailable-text');
    const val = Number(metricObj.value);
    valEl.textContent = val.toFixed(1);
    if (unitEl) unitEl.textContent = metricObj.unit || fallbackUnit;
  }

  renderRunSummaryUnavailable(reason) {
    [this.kpiLatency, this.kpiThroughput, this.kpiLoss, this.kpiReward].forEach((el) => {
      this.renderMetricKpi(el, null);
    });
  }

  renderMetricCharts(metricRecords) {
    if (!Array.isArray(metricRecords) || metricRecords.length === 0) {
      this.renderChartsUnavailable();
      return;
    }

    const latencyData = [];
    const throughputData = [];
    const lossData = [];
    const rewardData = [];

    metricRecords.forEach((record) => {
      const m = record.metrics || {};
      if (m.latency_ms && m.latency_ms.status === 'available' && typeof m.latency_ms.value === 'number') {
        latencyData.push(m.latency_ms.value);
      }
      if (m.throughput_kbps && m.throughput_kbps.status === 'available' && typeof m.throughput_kbps.value === 'number') {
        throughputData.push(m.throughput_kbps.value);
      }
      if (m.loss_pct && m.loss_pct.status === 'available' && typeof m.loss_pct.value === 'number') {
        lossData.push(m.loss_pct.value);
      }
      if (m.reward && m.reward.status === 'available' && typeof m.reward.value === 'number') {
        rewardData.push(m.reward.value);
      }
    });

    if (this.chartLatency) {
      if (latencyData.length > 0) this.chartLatency.setData(latencyData);
      else this.chartLatency.clear();
      this.updateChartValueLabel('chartRunLatencyVal', latencyData, 'ms');
    }

    if (this.chartThroughput) {
      if (throughputData.length > 0) this.chartThroughput.setData(throughputData);
      else this.chartThroughput.clear();
      this.updateChartValueLabel('chartRunThroughputVal', throughputData, 'kbps');
    }

    if (this.chartLoss) {
      if (lossData.length > 0) this.chartLoss.setData(lossData);
      else this.chartLoss.clear();
      this.updateChartValueLabel('chartRunLossVal', lossData, '%');
    }

    if (this.chartReward) {
      if (rewardData.length > 0) this.chartReward.setData(rewardData);
      else this.chartReward.clear();
      this.updateChartValueLabel('chartRunRewardVal', rewardData, '');
    }
  }

  updateChartValueLabel(elementId, dataArray, unit = '') {
    const el = document.getElementById(elementId);
    if (!el) return;
    if (!dataArray || dataArray.length === 0) {
      el.textContent = '--';
      return;
    }
    const latest = dataArray[dataArray.length - 1];
    el.textContent = latest.toFixed(1) + (unit ? ' ' + unit : '');
  }

  renderChartsUnavailable() {
    if (this.chartLatency) this.chartLatency.clear();
    if (this.chartThroughput) this.chartThroughput.clear();
    if (this.chartLoss) this.chartLoss.clear();
    if (this.chartReward) this.chartReward.clear();

    ['chartRunLatencyVal', 'chartRunThroughputVal', 'chartRunLossVal', 'chartRunRewardVal'].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.textContent = 'Unavailable';
    });
  }

  renderCharts() {
    if (this.chartLatency) this.chartLatency.render();
    if (this.chartThroughput) this.chartThroughput.render();
    if (this.chartLoss) this.chartLoss.render();
    if (this.chartReward) this.chartReward.render();
  }

  async fetchRunTrace(runId) {
    if (!this.traceSection) return;
    try {
      const res = await fetch(`/api/results/${encodeURIComponent(runId)}/trace`, { cache: 'no-store' });
      if (!res.ok) {
        this.traceSection.style.display = 'none';
        return;
      }
      const data = await res.json();
      const traces = Array.isArray(data.trace) ? data.trace : [];
      if (traces.length === 0) {
        this.traceSection.style.display = 'none';
        return;
      }

      this.traceSection.style.display = 'block';
      if (this.traceCountBadge) this.traceCountBadge.textContent = traces.length;

      if (this.traceTableBody) {
        this.traceTableBody.innerHTML = '';
        traces.slice(0, 50).forEach((t) => {
          const row = document.createElement('tr');
          const time = t.timestamp_utc ? t.timestamp_utc.substring(11, 19) : '--';
          const decisionAction = (t.decision && t.decision.action) || t.event || '--';
          const safetyPassed = t.safety_result ? (t.safety_result.passed ? 'PASS' : 'REJECT') : 'N/A';

          row.innerHTML = `
            <td>${t.sequence !== undefined ? t.sequence : '--'}</td>
            <td class="mono-text">${this.escapeText(time)}</td>
            <td><span class="badge-tag accent-cyan">${this.escapeText(t.event || 'cycle')}</span></td>
            <td><code>${this.escapeText(decisionAction)}</code></td>
            <td><span class="badge-state ${safetyPassed === 'PASS' ? 'ok' : safetyPassed === 'REJECT' ? 'error' : 'neutral'}">${this.escapeText(safetyPassed)}</span></td>
          `;
          this.traceTableBody.appendChild(row);
        });
      }
    } catch (e) {
      if (this.traceSection) this.traceSection.style.display = 'none';
    }
  }

  async evaluateComparisons() {
    // Collect completed runs with summaries for stages A0, A1, A2
    const completedA0 = this.runs.filter(r => r.status === 'completed' && r.has_summary && r.experiment && r.experiment.stage === 'A0');
    const completedA1 = this.runs.filter(r => r.status === 'completed' && r.has_summary && r.experiment && r.experiment.stage === 'A1');
    const completedA2 = this.runs.filter(r => r.status === 'completed' && r.has_summary && r.experiment && r.experiment.stage === 'A2');

    const compareCandidateIds = [];
    if (completedA0.length > 0) compareCandidateIds.push(completedA0[0].run_id);
    if (completedA1.length > 0) compareCandidateIds.push(completedA1[0].run_id);
    if (completedA2.length > 0) compareCandidateIds.push(completedA2[0].run_id);

    if (compareCandidateIds.length === 0) {
      this.renderComparisonEmpty('No completed runs with finalized summaries are currently available for condition comparison.');
      return;
    }

    try {
      const url = `/api/results/compare?run_ids=${compareCandidateIds.map(encodeURIComponent).join(',')}`;
      const res = await fetch(url, { cache: 'no-store' });
      if (!res.ok) {
        this.renderComparisonEmpty('Comparison endpoint returned HTTP ' + res.status + '. All compared runs must be completed with summaries.');
        return;
      }
      const data = await res.json();
      this.comparisonResults = data.results || [];
      this.renderComparison(this.comparisonResults);
    } catch (err) {
      this.renderComparisonEmpty('Unable to load run comparisons: ' + err.message);
    }
  }

  renderComparisonEmpty(message) {
    if (this.comparisonNotice) {
      this.comparisonNotice.style.display = 'block';
      this.comparisonNotice.textContent = message;
    }
    if (this.comparisonCardsContainer) this.comparisonCardsContainer.innerHTML = '';
    if (this.comparisonTableBody) this.comparisonTableBody.innerHTML = '';
  }

  renderComparison(comparedList) {
    if (!this.comparisonCardsContainer || !Array.isArray(comparedList) || comparedList.length === 0) {
      this.renderComparisonEmpty('No completed comparison data available.');
      return;
    }

    if (this.comparisonNotice) this.comparisonNotice.style.display = 'none';
    this.comparisonCardsContainer.innerHTML = '';

    // Map by stage
    const byStage = {};
    comparedList.forEach(item => {
      const stage = (item.run && item.run.experiment && item.run.experiment.stage) || 'UNK';
      byStage[stage] = item;
    });

    ['A0', 'A1', 'A2'].forEach(stage => {
      const item = byStage[stage];
      const card = document.createElement('div');
      card.className = `ablation-card ${stage === 'A2' ? 'winner' : ''} ${stage.toLowerCase()}-card`;

      if (!item) {
        card.innerHTML = `
          <div class="ablation-card-header">
            <span class="ablation-tag tag-${stage.toLowerCase()}">CONDITION ${stage}</span>
            <span class="baseline-pill">NOT YET RECORDED</span>
          </div>
          <h3>${this.getStageTitle(stage)}</h3>
          <p class="unavailable-text">No completed ${stage} run bundle found in archive.</p>
          <div class="ablation-footer-status">
            <span>Status:</span>
            <span class="status-neutral">Awaiting Run</span>
          </div>
        `;
        this.comparisonCardsContainer.appendChild(card);
        return;
      }

      const m = (item.summary && item.summary.metrics) || {};
      const latVal = this.getMetricValText(m.latency_ms, 'ms');
      const tpVal = this.getMetricValText(m.throughput_kbps, 'kbps');
      const lossVal = this.getMetricValText(m.loss_pct, '%');
      const rewVal = this.getMetricValText(m.reward, '');
      const prov = (item.run && item.run.provenance) || 'unknown';

      card.innerHTML = `
        ${stage === 'A2' ? '<div class="winner-glow"></div>' : ''}
        <div class="ablation-card-header">
          <span class="ablation-tag tag-${stage.toLowerCase()}">CONDITION ${stage}</span>
          <span class="provenance-pill ${prov === 'live' ? 'prov-live' : 'prov-sim'}">${this.escapeText(prov)}</span>
        </div>
        <h3>${this.getStageTitle(stage)}</h3>
        <p>Run ID: <code style="font-size:0.7rem;">${this.escapeText(item.run.run_id)}</code></p>
        <div class="ablation-bars-list">
          <div class="ablation-bar-item">
            <div class="bar-label-row"><span>Mean Latency</span><strong>${latVal}</strong></div>
          </div>
          <div class="ablation-bar-item">
            <div class="bar-label-row"><span>Throughput</span><strong>${tpVal}</strong></div>
          </div>
          <div class="ablation-bar-item">
            <div class="bar-label-row"><span>Packet Loss</span><strong>${lossVal}</strong></div>
          </div>
          <div class="ablation-bar-item">
            <div class="bar-label-row"><span>Mean Reward</span><strong>${rewVal}</strong></div>
          </div>
        </div>
        <div class="ablation-footer-status">
          <span>Final Status:</span>
          <span class="status-pass">COMPLETED</span>
        </div>
      `;
      this.comparisonCardsContainer.appendChild(card);
    });

    // Populate the quantitative comparison matrix
    this.renderComparisonTable(byStage);
  }

  renderComparisonTable(byStage) {
    if (!this.comparisonTableBody) return;
    this.comparisonTableBody.innerHTML = '';

    const a0 = byStage['A0'] && byStage['A0'].summary && byStage['A0'].summary.metrics;
    const a1 = byStage['A1'] && byStage['A1'].summary && byStage['A1'].summary.metrics;
    const a2 = byStage['A2'] && byStage['A2'].summary && byStage['A2'].summary.metrics;

    const rows = [
      {
        name: 'Average End-to-End Latency',
        a0Val: this.getMetricValText(a0 && a0.latency_ms, 'ms'),
        a1Val: this.getMetricValText(a1 && a1.latency_ms, 'ms'),
        a2Val: this.getMetricValText(a2 && a2.latency_ms, 'ms'),
        improvement: this.calculateImprovement(a0 && a0.latency_ms, a2 && a2.latency_ms, 'reduction'),
        criterion: '≥ 20% Reduction vs A0'
      },
      {
        name: 'Network Throughput',
        a0Val: this.getMetricValText(a0 && a0.throughput_kbps, 'kbps'),
        a1Val: this.getMetricValText(a1 && a1.throughput_kbps, 'kbps'),
        a2Val: this.getMetricValText(a2 && a2.throughput_kbps, 'kbps'),
        improvement: this.calculateImprovement(a0 && a0.throughput_kbps, a2 && a2.throughput_kbps, 'gain'),
        criterion: 'Maintains sustained throughput'
      },
      {
        name: 'Packet Loss Percentage',
        a0Val: this.getMetricValText(a0 && a0.loss_pct, '%'),
        a1Val: this.getMetricValText(a1 && a1.loss_pct, '%'),
        a2Val: this.getMetricValText(a2 && a2.loss_pct, '%'),
        improvement: this.calculateImprovement(a0 && a0.loss_pct, a2 && a2.loss_pct, 'reduction'),
        criterion: 'Minimized loss under elephant burst'
      },
      {
        name: 'Cumulative / Mean Reward',
        a0Val: this.getMetricValText(a0 && a0.reward, ''),
        a1Val: this.getMetricValText(a1 && a1.reward, ''),
        a2Val: this.getMetricValText(a2 && a2.reward, ''),
        improvement: this.calculateImprovement(a0 && a0.reward, a2 && a2.reward, 'gain'),
        criterion: 'Positive trajectory with reflection'
      }
    ];

    rows.forEach(r => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong>${this.escapeText(r.name)}</strong></td>
        <td>${r.a0Val}</td>
        <td>${r.a1Val}</td>
        <td><span class="cell-winner">${r.a2Val}</span></td>
        <td>${r.improvement}</td>
        <td><span class="badge-state neutral">${this.escapeText(r.criterion)}</span></td>
      `;
      this.comparisonTableBody.appendChild(tr);
    });
  }

  calculateImprovement(metricA0, metricA2, type = 'reduction') {
    if (!metricA0 || metricA0.status !== 'available' || metricA0.value === null ||
        !metricA2 || metricA2.status !== 'available' || metricA2.value === null) {
      return '<span class="unavailable-text">Data Unavailable</span>';
    }

    const v0 = Number(metricA0.value);
    const v2 = Number(metricA2.value);
    if (v0 === 0) return '<span class="unavailable-text">N/A</span>';

    if (type === 'reduction') {
      const pct = ((v0 - v2) / v0) * 100;
      const sign = pct >= 0 ? '-' : '+';
      const isGood = pct >= 20;
      return `<span class="improvement-badge ${isGood ? 'improvement-pass' : ''}">${sign}${Math.abs(pct).toFixed(1)}%</span>`;
    } else {
      const pct = ((v2 - v0) / Math.abs(v0)) * 100;
      const sign = pct >= 0 ? '+' : '-';
      return `<span class="improvement-badge">${sign}${Math.abs(pct).toFixed(1)}%</span>`;
    }
  }

  getMetricValText(metric, unit = '') {
    if (!metric || metric.status === 'unavailable' || metric.value === null || metric.value === undefined) {
      return '<span class="unavailable-text">Unavailable</span>';
    }
    const val = Number(metric.value);
    return `${val.toFixed(1)}${unit ? ' ' + unit : ''}`;
  }

  getStageTitle(stage) {
    switch (stage) {
      case 'A0': return 'Static Ryu L2 Baseline';
      case 'A1': return 'Zero-Shot LLM Agent';
      case 'A2': return 'SELF-X Self-Improving Agent';
      default: return `Condition ${stage}`;
    }
  }

  formatTimestamp(utcString) {
    if (!utcString) return '--';
    try {
      const date = new Date(utcString);
      return date.toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
    } catch (e) {
      return utcString;
    }
  }

  escapeText(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
}

window.ExperimentResultsManager = ExperimentResultsManager;
