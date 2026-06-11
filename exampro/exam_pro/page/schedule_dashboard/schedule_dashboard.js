frappe.pages['schedule-dashboard'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Schedule Dashboard',
		single_column: true
	});

	page.add_field({
		fieldtype: 'Link',
		fieldname: 'exam_schedule',
		label: 'Exam Schedule',
		options: 'Exam Schedule',
		onchange: function () {
			wrapper.schedule_dashboard.on_schedule_change();
		}
	});

	wrapper.schedule_dashboard = new ScheduleDashboard(wrapper, page);

	let route_params = frappe.utils.get_query_params();
	if (route_params.exam_schedule) {
		page.fields_dict.exam_schedule.set_value(route_params.exam_schedule);
	}
};

class ScheduleDashboard {
	constructor(wrapper, page) {
		this.wrapper = wrapper;
		this.page = page;
		this._refresh_interval = null;
		this._countdown_interval = null;
		this.make();
	}

	make() {
		this.$container = $('<div class="schedule-dashboard" style="max-width: 960px; margin: 0 auto; padding: 15px;">').appendTo(this.wrapper);
		this.$empty = $(`
			<div class="text-muted text-center" style="padding: 60px 20px;">
				<i class="fa fa-calendar" style="font-size: 48px; color: #adb5bd;"></i>
				<h5 class="mt-3" style="font-weight: 600;">Select an Exam Schedule</h5>
				<p>Choose a schedule from the filter above to view its dashboard.</p>
			</div>
		`).appendTo(this.$container);
		this.$content = $('<div class="schedule-dashboard-content" style="display:none;">').appendTo(this.$container);

		this.$header_section = $('<div class="header-section mb-3">').appendTo(this.$content);
		this.$metrics_section = $('<div class="metrics-section mb-3">').appendTo(this.$content);
		this.$live_section = $('<div class="live-section mb-3" style="display:none;">').appendTo(this.$content);
		this.$chart_section = $('<div class="chart-section mb-3" style="display:none;">').appendTo(this.$content);
		this.$table_section = $('<div class="table-section" style="display:none;">').appendTo(this.$content);
	}

	on_schedule_change() {
		this.stop_auto_refresh();
		this.refresh();
	}

	refresh() {
		let schedule_name = this.page.fields_dict.exam_schedule.get_value();
		if (!schedule_name) {
			this.$empty.show();
			this.$content.hide();
			this.page.clear_indicator();
			return;
		}
		this.$empty.hide();
		this.$content.show();
		this.fetch_and_render_data(schedule_name);
	}

	fetch_and_render_data(schedule_name) {
		if (!schedule_name) {
			schedule_name = this.page.fields_dict.exam_schedule.get_value();
		}
		if (!schedule_name) return;

		frappe.call({
			method: 'exampro.exam_pro.page.schedule_dashboard.schedule_dashboard.get_schedule_dashboard_data',
			args: { schedule_name: schedule_name },
			callback: (r) => {
				if (!r.exc && r.message) {
					this.data = r.message;
					this.render(r.message);
				}
			}
		});
	}

	render(data) {
		this.render_header(data);
		this.render_metrics(data);

		let status = data.schedule_status;

		if (status === 'Ongoing') {
			this.$live_section.show();
			this.render_live_section(data);
			this.$chart_section.show();
			this.render_status_chart(data);
			this.start_auto_refresh();
		} else {
			this.$live_section.hide();
			this.stop_auto_refresh();
		}

		if (status === 'Completed') {
			this.$chart_section.show();
			this.render_completed_charts(data);
			this.$table_section.show();
			this.render_tables(data);
		} else if (status !== 'Ongoing') {
			this.$chart_section.hide();
			this.$table_section.hide();
		}

		if (status === 'Ongoing') {
			this.$table_section.show();
			this.render_live_candidates_table(data);
		}
	}

	render_header(data) {
		let status = data.schedule_status;
		let status_color = { Upcoming: '#0d6efd', Ongoing: '#198754', Completed: '#6c757d' };
		let status_bg = { Upcoming: '#e7f1ff', Ongoing: '#e8f5e9', Completed: '#f1f3f5' };

		let time_info = '';
		if (status === 'Upcoming') {
			let start = new Date(data.start_date_time);
			time_info = `Starts: ${start.toLocaleString()}`;
		} else if (status === 'Ongoing') {
			let end = new Date(data.end_time);
			time_info = `Ends: ${end.toLocaleString()}`;
		} else {
			let end = new Date(data.end_time);
			time_info = `Ended: ${end.toLocaleString()}`;
		}

		this.$header_section.html(`
			<div style="background: #fff; border: 1px solid rgba(0,0,0,0.08); border-radius: 6px; padding: 1.1rem 1.25rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
				<div>
					<h5 style="margin: 0 0 4px 0; font-weight: 600;">${data.exam_title || data.exam}</h5>
					<span class="text-muted" style="font-size: 0.85rem;">${data.schedule_name} &middot; ${data.schedule_type} &middot; ${data.duration} min &middot; ${time_info}</span>
				</div>
				<div style="display: flex; align-items: center; gap: 10px;">
					${status === 'Ongoing' ? '<span id="sd-countdown" style="font-size: 0.85rem; font-weight: 600; color: #198754;"></span>' : ''}
					<span style="background: ${status_bg[status]}; color: ${status_color[status]}; padding: 0.3rem 0.75rem; border-radius: 4px; font-size: 0.78rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.03em;">
						${status}
					</span>
				</div>
			</div>
		`);

		this.stop_countdown();
		if (status === 'Upcoming') {
			this.start_countdown(new Date(data.start_date_time), 'starts in');
		} else if (status === 'Ongoing') {
			this.start_countdown(new Date(data.end_time), 'remaining');
		}
	}

	start_countdown(target_time, label) {
		let update = () => {
			let now = new Date();
			let diff = Math.max(0, Math.floor((target_time - now) / 1000));
			if (diff <= 0) {
				$('#sd-countdown').text('');
				this.stop_countdown();
				this.refresh();
				return;
			}
			let h = Math.floor(diff / 3600);
			let m = Math.floor((diff % 3600) / 60);
			let s = diff % 60;
			let parts = [];
			if (h) parts.push(h + 'h');
			if (m) parts.push(m + 'm');
			parts.push(s + 's');
			$('#sd-countdown').text(parts.join(' ') + ' ' + label);
		};
		update();
		this._countdown_interval = setInterval(update, 1000);
	}

	stop_countdown() {
		if (this._countdown_interval) {
			clearInterval(this._countdown_interval);
			this._countdown_interval = null;
		}
	}

	render_metrics(data) {
		let status = data.schedule_status;
		let counts = data.status_counts || {};
		let metrics = [];

		if (status === 'Upcoming') {
			metrics = [
				{ label: 'Registered', value: counts['Registered'] || 0, icon: 'users', color: 'blue' },
				{ label: 'Schedule Type', value: data.schedule_type, icon: 'calendar', color: 'green' },
				{ label: 'Duration', value: data.duration + ' min', icon: 'clock-o', color: 'orange' },
				{ label: 'Total Marks', value: data.total_marks, icon: 'star', color: 'purple' },
			];
		} else if (status === 'Ongoing') {
			metrics = [
				{ label: 'Registered', value: counts['Registered'] || 0, icon: 'users', color: 'blue' },
				{ label: 'Live Now', value: data.candidates_live || 0, icon: 'bolt', color: 'green' },
				{ label: 'Submitted', value: counts['Submitted'] || 0, icon: 'check', color: 'purple' },
				{ label: 'Terminated', value: counts['Terminated'] || 0, icon: 'ban', color: 'red' },
				{ label: 'Not Attempted', value: counts['Not Attempted'] || 0, icon: 'minus-circle', color: 'grey' },
				{ label: 'Total', value: data.total_candidates || 0, icon: 'list', color: 'orange' },
			];
		} else {
			metrics = [
				{ label: 'Total Candidates', value: data.total_candidates || 0, icon: 'users', color: 'blue' },
				{ label: 'Submitted', value: counts['Submitted'] || 0, icon: 'check', color: 'green' },
				{ label: 'Terminated', value: counts['Terminated'] || 0, icon: 'ban', color: 'red' },
				{ label: 'Not Attempted', value: counts['Not Attempted'] || 0, icon: 'minus-circle', color: 'grey' },
				{ label: 'Pass Rate', value: (data.pass_rate || 0) + '%', icon: 'trophy', color: 'orange' },
				{ label: 'Avg Score', value: data.avg_score != null ? data.avg_score : 'N/A', icon: 'star', color: 'purple' },
			];
		}

		this.$metrics_section.html('');
		let $row = $('<div class="d-flex flex-wrap" style="gap: 12px;">').appendTo(this.$metrics_section);

		metrics.forEach(m => {
			$row.append(`
				<div style="flex: 1 1 150px; max-width: 220px; background: #fff; border: 1px solid rgba(0,0,0,0.08); border-radius: 6px; padding: 14px 16px;">
					<div class="text-muted" style="font-size: 0.78rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.03em; margin-bottom: 6px;">
						<i class="fa fa-${m.icon}" style="margin-right: 4px;"></i>${m.label}
					</div>
					<div style="font-size: 1.4rem; font-weight: 600; color: #212529;">${m.value}</div>
				</div>
			`);
		});
	}

	render_live_section(data) {
		let metrics = [
			{ label: 'Avg Attention Score', value: data.avg_attention_score_live || 0 },
			{ label: 'Total Warnings', value: data.total_warnings_live || 0 },
			{ label: 'Avg Away Time', value: (data.avg_away_time_live || 0) + 's' },
			{ label: 'Avg Distracted Time', value: (data.avg_distracted_time_live || 0) + 's' },
		];

		this.$live_section.html(`
			<div style="background: #fff; border: 1px solid rgba(0,0,0,0.08); border-radius: 6px; overflow: hidden;">
				<div style="background: #fafbfc; border-bottom: 1px solid rgba(0,0,0,0.06); padding: 0.75rem 1.1rem; font-weight: 600; font-size: 0.95rem;">
					<i class="fa fa-eye" style="margin-right: 6px; color: #868e96;"></i>Live Monitoring
				</div>
				<div style="padding: 16px;">
					<div class="d-flex flex-wrap" style="gap: 12px;" id="sd-live-metrics"></div>
				</div>
			</div>
		`);

		let $row = this.$live_section.find('#sd-live-metrics');
		metrics.forEach(m => {
			$row.append(`
				<div style="flex: 1 1 120px; max-width: 200px; background: #fafbfc; border-radius: 4px; padding: 12px 14px;">
					<div class="text-muted" style="font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.02em; margin-bottom: 4px;">${m.label}</div>
					<div style="font-size: 1.15rem; font-weight: 600;">${m.value}</div>
				</div>
			`);
		});
	}

	render_status_chart(data) {
		let counts = data.status_counts || {};
		let labels = [];
		let values = [];
		for (let [k, v] of Object.entries(counts)) {
			labels.push(k);
			values.push(v);
		}
		if (!labels.length) {
			this.$chart_section.hide();
			return;
		}

		this.$chart_section.html(`
			<div class="d-flex flex-wrap" style="gap: 12px;">
				<div id="sd-status-chart" style="flex: 1 1 45%; background: #fff; border: 1px solid rgba(0,0,0,0.08); border-radius: 6px; padding: 16px; min-height: 280px;">
					<h6 style="font-weight: 600; margin-bottom: 12px;">Candidate Status</h6>
				</div>
			</div>
		`);

		new frappe.Chart('#sd-status-chart', {
			data: { labels: labels, datasets: [{ name: 'Candidates', values: values }] },
			type: 'pie',
			colors: ['#0d6efd', '#198754', '#7c5cfc', '#dc3545', '#6c757d', '#fd7e14'],
			height: 220
		});
	}

	render_completed_charts(data) {
		let result_dist = data.result_status_distribution || {};
		let has_results = Object.keys(result_dist).length > 0;
		let has_scores = (data.score_distribution || []).some(v => v > 0);

		let html = '<div class="d-flex flex-wrap" style="gap: 12px;">';

		if (has_results) {
			html += `<div id="sd-result-chart" style="flex: 1 1 45%; background: #fff; border: 1px solid rgba(0,0,0,0.08); border-radius: 6px; padding: 16px; min-height: 280px;">
				<h6 style="font-weight: 600; margin-bottom: 12px;">Result Distribution</h6>
			</div>`;
		}
		if (has_scores) {
			html += `<div id="sd-score-chart" style="flex: 1 1 45%; background: #fff; border: 1px solid rgba(0,0,0,0.08); border-radius: 6px; padding: 16px; min-height: 280px;">
				<h6 style="font-weight: 600; margin-bottom: 12px;">Score Distribution</h6>
			</div>`;
		}

		if (data.evaluation_progress) {
			let ep = data.evaluation_progress;
			let pct = ep.total ? Math.round(ep.evaluated / ep.total * 100) : 0;
			html += `<div style="flex: 1 1 45%; background: #fff; border: 1px solid rgba(0,0,0,0.08); border-radius: 6px; padding: 16px;">
				<h6 style="font-weight: 600; margin-bottom: 12px;">Evaluation Progress</h6>
				<div style="font-size: 2rem; font-weight: 600; color: #212529;">${ep.evaluated} / ${ep.total}</div>
				<div class="text-muted" style="font-size: 0.85rem;">evaluated (${pct}%)</div>
				<div style="margin-top: 10px; background: #e9ecef; border-radius: 4px; height: 8px; overflow: hidden;">
					<div style="width: ${pct}%; height: 100%; background: #198754; border-radius: 4px;"></div>
				</div>
				${ep.pending > 0 ? `<div class="text-muted" style="font-size: 0.78rem; margin-top: 6px;">${ep.pending} pending evaluation</div>` : ''}
			</div>`;
		}

		html += '</div>';
		this.$chart_section.html(html);

		if (has_results) {
			let labels = Object.keys(result_dist);
			let values = Object.values(result_dist);
			let color_map = { 'Passed': '#198754', 'Failed': '#dc3545', 'NA': '#6c757d' };
			let colors = labels.map(l => color_map[l] || '#adb5bd');
			new frappe.Chart('#sd-result-chart', {
				data: { labels: labels, datasets: [{ name: 'Results', values: values }] },
				type: 'pie',
				colors: colors,
				height: 220
			});
		}

		if (has_scores) {
			new frappe.Chart('#sd-score-chart', {
				data: {
					labels: ['0-20', '21-40', '41-60', '61-80', '81-100'],
					datasets: [{ name: 'Candidates', values: data.score_distribution }]
				},
				type: 'bar',
				colors: ['#5e64ff'],
				height: 220
			});
		}
	}

	render_live_candidates_table(data) {
		let candidates = data.live_candidates || [];

		this.$table_section.html(`
			<div style="background: #fff; border: 1px solid rgba(0,0,0,0.08); border-radius: 6px; overflow: hidden;">
				<div style="background: #fafbfc; border-bottom: 1px solid rgba(0,0,0,0.06); padding: 0.75rem 1.1rem; font-weight: 600; font-size: 0.95rem;">
					<i class="fa fa-users" style="margin-right: 6px; color: #868e96;"></i>Live Candidates (${candidates.length})
				</div>
				<div style="padding: 0;" id="sd-live-table-body"></div>
			</div>
		`);

		if (!candidates.length) {
			$('#sd-live-table-body').html('<div class="text-muted text-center" style="padding: 24px;">No candidates currently taking the exam.</div>');
			return;
		}

		let $table = $(`
			<table class="table" style="margin: 0;">
				<thead>
					<tr style="background: #fafbfc;">
						<th style="color: #6c757d; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.03em; font-weight: 600; padding: 0.75rem 1rem;">Candidate</th>
						<th style="color: #6c757d; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.03em; font-weight: 600; padding: 0.75rem 1rem;">Attention</th>
						<th style="color: #6c757d; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.03em; font-weight: 600; padding: 0.75rem 1rem;">Warnings</th>
						<th style="color: #6c757d; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.03em; font-weight: 600; padding: 0.75rem 1rem;">Away Time</th>
						<th style="color: #6c757d; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.03em; font-weight: 600; padding: 0.75rem 1rem;">Distracted</th>
					</tr>
				</thead>
				<tbody></tbody>
			</table>
		`);

		candidates.forEach(c => {
			let attention_color = (c.attention_score || 0) >= 70 ? '#198754' : (c.attention_score || 0) >= 40 ? '#fd7e14' : '#dc3545';
			$table.find('tbody').append(`
				<tr style="border-top: 1px solid rgba(0,0,0,0.05);">
					<td style="padding: 0.85rem 1rem; font-weight: 600;">${frappe.utils.escape_html(c.candidate_name || c.candidate)}</td>
					<td style="padding: 0.85rem 1rem;"><span style="color: ${attention_color}; font-weight: 600;">${c.attention_score || 0}</span></td>
					<td style="padding: 0.85rem 1rem;">${c.warning_count || 0}</td>
					<td style="padding: 0.85rem 1rem;">${(c.total_away_time || 0).toFixed(1)}s</td>
					<td style="padding: 0.85rem 1rem;">${(c.total_distracted_time || 0).toFixed(1)}s</td>
				</tr>
			`);
		});

		$('#sd-live-table-body').append($table);
	}

	render_tables(data) {
		let submissions = data.recent_submissions || [];

		this.$table_section.html(`
			<div style="background: #fff; border: 1px solid rgba(0,0,0,0.08); border-radius: 6px; overflow: hidden;">
				<div style="background: #fafbfc; border-bottom: 1px solid rgba(0,0,0,0.06); padding: 0.75rem 1.1rem; font-weight: 600; font-size: 0.95rem;">
					<i class="fa fa-list" style="margin-right: 6px; color: #868e96;"></i>Recent Submissions
				</div>
				<div style="padding: 0;" id="sd-submissions-body"></div>
			</div>
		`);

		if (!submissions.length) {
			$('#sd-submissions-body').html('<div class="text-muted text-center" style="padding: 24px;">No submissions yet.</div>');
			return;
		}

		let $table = $(`
			<table class="table" style="margin: 0;">
				<thead>
					<tr style="background: #fafbfc;">
						<th style="color: #6c757d; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.03em; font-weight: 600; padding: 0.75rem 1rem;">Candidate</th>
						<th style="color: #6c757d; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.03em; font-weight: 600; padding: 0.75rem 1rem;">Submitted</th>
						<th style="color: #6c757d; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.03em; font-weight: 600; padding: 0.75rem 1rem;">Score</th>
						<th style="color: #6c757d; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.03em; font-weight: 600; padding: 0.75rem 1rem;">Result</th>
					</tr>
				</thead>
				<tbody></tbody>
			</table>
		`);

		submissions.forEach(s => {
			let result_bg = { 'Passed': '#e8f5e9', 'Failed': '#fdecea', 'NA': '#f1f3f5' };
			let result_color = { 'Passed': '#1b5e20', 'Failed': '#b71c1c', 'NA': '#495057' };
			let rs = s.result_status || 'NA';
			$table.find('tbody').append(`
				<tr style="border-top: 1px solid rgba(0,0,0,0.05);">
					<td style="padding: 0.85rem 1rem; font-weight: 600;">${frappe.utils.escape_html(s.candidate_name || s.candidate)}</td>
					<td style="padding: 0.85rem 1rem;">${s.exam_submitted_time || ''}</td>
					<td style="padding: 0.85rem 1rem;">${s.total_marks != null ? s.total_marks : 'N/A'}</td>
					<td style="padding: 0.85rem 1rem;">
						<span style="background: ${result_bg[rs] || '#f1f3f5'}; color: ${result_color[rs] || '#495057'}; padding: 0.25rem 0.6rem; border-radius: 4px; font-size: 0.78rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.02em;">${rs}</span>
					</td>
				</tr>
			`);
		});

		$('#sd-submissions-body').append($table);
	}

	start_auto_refresh() {
		this.stop_auto_refresh();
		this._refresh_interval = setInterval(() => {
			this.fetch_and_render_data();
		}, 30000);
		this.page.set_indicator('Live', 'green');
	}

	stop_auto_refresh() {
		if (this._refresh_interval) {
			clearInterval(this._refresh_interval);
			this._refresh_interval = null;
		}
		this.page.clear_indicator();
	}
}
