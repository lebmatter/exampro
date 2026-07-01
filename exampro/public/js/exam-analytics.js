function examAnalyticsApp() {
  const data = window.examAnalyticsData || {};

  return {
    examName: data.examName || '',
    scopeSchedule: data.scheduleName || '',

    questionStats: [],
    questionStatsLoaded: false,

    summaryData: null,
    summaryLoaded: false,

    scheduleComparison: [],
    scheduleComparisonLoaded: false,

    _summaryChartRendered: false,
    _schedulesChartRendered: false,

    init() {
      this.loadQuestionStats();
    },

    loadQuestionStats() {
      this.questionStatsLoaded = false;
      frappe.call({
        method: 'exampro.exam_pro.api.analytics.get_question_stats',
        args: { exam_name: this.examName, schedule_name: this.scopeSchedule || null },
        callback: (r) => {
          this.questionStats = (!r.exc && r.message) ? r.message : [];
          this.questionStatsLoaded = true;
          this.$nextTick(() => feather.replace());
        },
      });
    },

    loadSummary() {
      if (this.summaryLoaded) return;
      frappe.call({
        method: 'exampro.exam_pro.api.analytics.get_exam_summary',
        args: { exam_name: this.examName, schedule_name: this.scopeSchedule || null },
        callback: (r) => {
          if (!r.exc && r.message) {
            this.summaryData = r.message;
            this.$nextTick(() => {
              this.renderSummaryCharts();
              feather.replace();
            });
          }
          this.summaryLoaded = true;
        },
      });
    },

    loadScheduleComparison() {
      if (this.scheduleComparisonLoaded) return;
      frappe.call({
        method: 'exampro.exam_pro.api.analytics.get_schedule_comparison',
        args: { exam_name: this.examName },
        callback: (r) => {
          if (!r.exc && r.message) {
            this.scheduleComparison = r.message;
            this.$nextTick(() => {
              this.renderScheduleChart();
              feather.replace();
            });
          }
          this.scheduleComparisonLoaded = true;
        },
      });
    },

    renderSummaryCharts() {
      if (this._summaryChartRendered || !this.summaryData) return;
      this._summaryChartRendered = true;

      const distEl = document.getElementById('ea-score-dist-chart');
      if (distEl && this.summaryData.score_distribution) {
        distEl.innerHTML = '';
        new frappe.Chart(distEl, {
          data: {
            labels: ['0–20%', '20–40%', '40–60%', '60–80%', '80–100%'],
            datasets: [{ name: 'Candidates', values: this.summaryData.score_distribution }],
          },
          type: 'bar',
          colors: ['#f5c344'],
          height: 220,
        });
      }

      const pfEl = document.getElementById('ea-pass-fail-chart');
      if (pfEl) {
        const allLabels = ['Passed', 'Failed', 'Pending Eval'];
        const allValues = [
          this.summaryData.passed || 0,
          this.summaryData.failed || 0,
          this.summaryData.pending_eval || 0,
        ];
        const labels = allLabels.filter((_, i) => allValues[i] > 0);
        const values = allValues.filter(v => v > 0);
        if (values.length > 0) {
          pfEl.innerHTML = '';
          new frappe.Chart(pfEl, {
            data: { labels, datasets: [{ values }] },
            type: 'pie',
            colors: ['#1b5e20', '#b71c1c', '#e67700'],
            height: 220,
          });
        }
      }
    },

    renderScheduleChart() {
      if (this._schedulesChartRendered || this.scheduleComparison.length < 2) return;
      this._schedulesChartRendered = true;

      const el = document.getElementById('ea-schedule-trend-chart');
      if (!el) return;

      el.innerHTML = '';
      new frappe.Chart(el, {
        data: {
          labels: this.scheduleComparison.map(s => s.start_date_time.substring(0, 10)),
          datasets: [
            { name: 'Pass Rate (%)', values: this.scheduleComparison.map(s => s.pass_rate) },
            { name: 'Avg Score', values: this.scheduleComparison.map(s => s.avg_score) },
          ],
        },
        type: 'line',
        colors: ['#1b5e20', '#0c63e4'],
        height: 240,
      });
    },

    successRateClass(rate) {
      if (rate >= 70) return 'badge-simple';
      if (rate >= 40) return 'badge-medium';
      return 'badge-hard';
    },

    dIndexClass(d) {
      if (d >= 0.3) return 'badge-simple';
      if (d >= 0.1) return 'badge-medium';
      return 'badge-hard';
    },

    dIndexTooltip(d) {
      if (d >= 0.3) return 'Good discriminator';
      if (d >= 0.1) return 'Fair discriminator';
      return 'Poor discriminator — consider reviewing this question';
    },
  };
}
