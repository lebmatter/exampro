frappe.pages['exam-overview'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Exam Overview',
		single_column: true
	});

	page.add_field({
		fieldtype: 'Link',
		fieldname: 'exam',
		label: 'Exam',
		options: 'Exam',
		onchange: function () {
			wrapper.exam_overview.refresh();
		}
	});

	wrapper.exam_overview = new ExamOverview(wrapper, page);

	let route_params = frappe.utils.get_query_params();
	if (route_params.exam) {
		page.fields_dict.exam.set_value(route_params.exam);
	}
};

const FEATHER = {
	book: '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>',
	users: '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
	check: '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>',
	award: '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="7"/><polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88"/></svg>',
	'x-circle': '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
	percent: '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="5" x2="5" y2="19"/><circle cx="6.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/></svg>',
	star: '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
	grid: '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>',
	calendar: '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
	'file-text': '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>',
};

function ficon(name, size) {
	let svg = FEATHER[name] || '';
	if (size && svg) {
		svg = svg.replace(/width="\d+"/, `width="${size}"`).replace(/height="\d+"/, `height="${size}"`);
	}
	return svg;
}

class ExamOverview {
	constructor(wrapper, page) {
		this.wrapper = wrapper;
		this.page = page;
		this.make();
	}

	make() {
		this.$container = $('<div class="exam-overview" style="max-width: 960px; margin: 0 auto; padding: 15px;">').appendTo(this.wrapper);
		this.$empty = $(`
			<div class="text-muted text-center" style="padding: 60px 20px;">
				<span style="color: #adb5bd;">${ficon('book', 48)}</span>
				<h5 class="mt-3" style="font-weight: 600;">Select an Exam</h5>
				<p>Choose an exam from the filter above to view its overview.</p>
			</div>
		`).appendTo(this.$container);
		this.$content = $('<div class="exam-overview-content" style="display:none;">').appendTo(this.$container);
	}

	refresh() {
		let exam_name = this.page.fields_dict.exam.get_value();
		if (!exam_name) {
			this.$empty.show();
			this.$content.hide();
			return;
		}
		this.$empty.hide();
		this.$content.show();
		this.fetch_and_render(exam_name);
	}

	fetch_and_render(exam_name) {
		frappe.call({
			method: 'exampro.exam_pro.page.exam_overview.exam_overview.get_exam_overview_data',
			args: { exam_name: exam_name },
			callback: (r) => {
				if (!r.exc && r.message) {
					this.render(r.message);
				}
			}
		});
	}

	render(data) {
		this.$content.html('');
		this.render_header(data);
		this.render_question_breakdown(data);
		this.render_candidate_metrics(data);
		this.render_charts(data);
		this.render_schedules(data);

		if (data.certification_stats) {
			this.render_certification(data.certification_stats);
		}
		if (data.evaluation_stats) {
			this.render_evaluation(data.evaluation_stats);
		}
	}

	render_header(data) {
		let pills = [];
		pills.push(this._pill(data.question_type, '#e7f1ff', '#0d6efd'));
		if (data.enable_certification) {
			pills.push(this._pill('Certification', '#e8f5e9', '#1b5e20'));
		}
		if (data.enable_video_proctoring) {
			pills.push(this._pill('Video Proctoring', '#fff3cd', '#8a6100'));
		}
		if (data.randomize_questions) {
			pills.push(this._pill('Randomized', '#f1f3f5', '#495057'));
		}

		let $header = $(`
			<div style="background: #fff; border: 1px solid rgba(0,0,0,0.08); border-radius: 6px; padding: 1.1rem 1.25rem; margin-bottom: 12px;">
				<div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px;">
					<div>
						<h5 style="margin: 0 0 6px 0; font-weight: 600;">${frappe.utils.escape_html(data.title)}</h5>
						<div style="display: flex; flex-wrap: wrap; gap: 6px;">${pills.join('')}</div>
					</div>
					<div style="display: flex; gap: 16px; flex-wrap: wrap; text-align: center;">
						${this._header_stat('Duration', data.duration + ' min')}
						${this._header_stat('Pass %', data.pass_percentage + '%')}
						${this._header_stat('Total Marks', data.total_marks)}
						${this._header_stat('Questions', data.total_questions)}
					</div>
				</div>
			</div>
		`);
		this.$content.append($header);
	}

	_pill(text, bg, color) {
		return `<span style="background: ${bg}; color: ${color}; padding: 0.25rem 0.6rem; border-radius: 4px; font-size: 0.78rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.02em;">${text}</span>`;
	}

	_header_stat(label, value) {
		return `<div>
			<div class="text-muted" style="font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.03em;">${label}</div>
			<div style="font-size: 1.1rem; font-weight: 600;">${value}</div>
		</div>`;
	}

	render_question_breakdown(data) {
		let qb = data.question_breakdown;
		if (!qb || !qb.categories || !qb.categories.length) return;

		let $card = this._card('Question Composition', 'grid');

		let $table = $(`
			<table class="table" style="margin: 0;">
				<thead>
					<tr style="background: #fafbfc;">
						<th style="color: #6c757d; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.03em; font-weight: 600; padding: 0.75rem 1rem;">Category</th>
						<th style="color: #6c757d; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.03em; font-weight: 600; padding: 0.75rem 1rem;">Type</th>
						<th style="color: #6c757d; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.03em; font-weight: 600; padding: 0.75rem 1rem;">Marks/Q</th>
						<th style="color: #6c757d; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.03em; font-weight: 600; padding: 0.75rem 1rem;">Available</th>
						<th style="color: #6c757d; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.03em; font-weight: 600; padding: 0.75rem 1rem;">Selected</th>
					</tr>
				</thead>
				<tbody></tbody>
			</table>
		`);

		let config = qb.exam_config || {};
		qb.categories.forEach(cat => {
			let selected = config[cat.id] || 0;
			$table.find('tbody').append(`
				<tr style="border-top: 1px solid rgba(0,0,0,0.05);">
					<td style="padding: 0.85rem 1rem; font-weight: 600;">${frappe.utils.escape_html(cat.category_name)}</td>
					<td style="padding: 0.85rem 1rem;">${this._pill(cat.question_type, cat.question_type === 'Choices' ? '#e7f1ff' : '#fff3cd', cat.question_type === 'Choices' ? '#0d6efd' : '#8a6100')}</td>
					<td style="padding: 0.85rem 1rem;">${cat.marks_per_question}</td>
					<td style="padding: 0.85rem 1rem;">${cat.question_count}</td>
					<td style="padding: 0.85rem 1rem; font-weight: 600;">${selected}</td>
				</tr>
			`);
		});

		$card.find('.card-body-area').append($table);
		this.$content.append($card);
	}

	render_candidate_metrics(data) {
		let cs = data.candidate_stats;
		if (!cs || !cs.total) return;

		let metrics = [
			{ label: 'Total Candidates', value: cs.total, icon: 'users' },
			{ label: 'Submitted', value: cs.submitted, icon: 'check' },
			{ label: 'Passed', value: cs.passed, icon: 'award' },
			{ label: 'Failed', value: cs.failed, icon: 'x-circle' },
			{ label: 'Pass Rate', value: cs.pass_rate + '%', icon: 'percent' },
			{ label: 'Avg Score', value: cs.avg_score, icon: 'star' },
		];

		let $row = $('<div class="d-flex flex-wrap" style="gap: 12px; margin-bottom: 12px;">');
		metrics.forEach(m => {
			$row.append(`
				<div style="flex: 1 1 130px; max-width: 180px; background: #fff; border: 1px solid rgba(0,0,0,0.08); border-radius: 6px; padding: 14px 16px;">
					<div class="text-muted" style="font-size: 0.78rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.03em; margin-bottom: 6px; display: inline-flex; align-items: center; gap: 4px;">
						${ficon(m.icon)}${m.label}
					</div>
					<div style="font-size: 1.4rem; font-weight: 600; color: #212529;">${m.value}</div>
				</div>
			`);
		});
		this.$content.append($row);
	}

	render_charts(data) {
		let result_dist = data.result_distribution || {};
		let has_results = Object.keys(result_dist).length > 0;
		let has_scores = (data.score_distribution || []).some(v => v > 0);

		if (!has_results && !has_scores) return;

		let $row = $('<div class="d-flex flex-wrap" style="gap: 12px; margin-bottom: 12px;">');

		if (has_results) {
			$row.append(`<div id="eo-result-chart" style="flex: 1 1 45%; background: #fff; border: 1px solid rgba(0,0,0,0.08); border-radius: 6px; padding: 16px; min-height: 280px;">
				<h6 style="font-weight: 600; margin-bottom: 12px;">Result Distribution</h6>
			</div>`);
		}
		if (has_scores) {
			$row.append(`<div id="eo-score-chart" style="flex: 1 1 45%; background: #fff; border: 1px solid rgba(0,0,0,0.08); border-radius: 6px; padding: 16px; min-height: 280px;">
				<h6 style="font-weight: 600; margin-bottom: 12px;">Score Distribution</h6>
			</div>`);
		}

		this.$content.append($row);

		if (has_results) {
			let labels = Object.keys(result_dist);
			let values = Object.values(result_dist);
			let color_map = { 'Passed': '#198754', 'Failed': '#dc3545', 'NA': '#6c757d' };
			new frappe.Chart('#eo-result-chart', {
				data: { labels: labels, datasets: [{ name: 'Results', values: values }] },
				type: 'pie',
				colors: labels.map(l => color_map[l] || '#adb5bd'),
				height: 220
			});
		}
		if (has_scores) {
			new frappe.Chart('#eo-score-chart', {
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

	render_schedules(data) {
		let sched = data.schedules;
		if (!sched || !sched.total) return;

		let ss = sched.status_summary || {};
		let $card = this._card('Schedules', 'calendar');

		let $summary = $(`
			<div class="d-flex flex-wrap" style="gap: 12px; padding: 12px 16px;">
				${this._mini_stat('Total', sched.total)}
				${this._mini_stat('Upcoming', ss.Upcoming || 0, '#0d6efd')}
				${this._mini_stat('Ongoing', ss.Ongoing || 0, '#198754')}
				${this._mini_stat('Completed', ss.Completed || 0, '#6c757d')}
			</div>
		`);
		$card.find('.card-body-area').append($summary);

		let $table = $(`
			<table class="table" style="margin: 0;">
				<thead>
					<tr style="background: #fafbfc;">
						<th style="color: #6c757d; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.03em; font-weight: 600; padding: 0.75rem 1rem;">Schedule</th>
						<th style="color: #6c757d; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.03em; font-weight: 600; padding: 0.75rem 1rem;">Date</th>
						<th style="color: #6c757d; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.03em; font-weight: 600; padding: 0.75rem 1rem;">Type</th>
						<th style="color: #6c757d; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.03em; font-weight: 600; padding: 0.75rem 1rem;">Candidates</th>
						<th style="color: #6c757d; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.03em; font-weight: 600; padding: 0.75rem 1rem;">Status</th>
					</tr>
				</thead>
				<tbody></tbody>
			</table>
		`);

		let status_bg = { Upcoming: '#e7f1ff', Ongoing: '#e8f5e9', Completed: '#f1f3f5' };
		let status_color = { Upcoming: '#0d6efd', Ongoing: '#1b5e20', Completed: '#495057' };

		(sched.list || []).forEach(s => {
			let dt = s.start_date_time ? new Date(s.start_date_time).toLocaleString() : '';
			$table.find('tbody').append(`
				<tr style="border-top: 1px solid rgba(0,0,0,0.05);">
					<td style="padding: 0.85rem 1rem;">
						<a href="/app/schedule-dashboard?exam_schedule=${encodeURIComponent(s.name)}" style="font-weight: 600; color: #0d6efd;">${frappe.utils.escape_html(s.name)}</a>
					</td>
					<td style="padding: 0.85rem 1rem;">${dt}</td>
					<td style="padding: 0.85rem 1rem;">${s.schedule_type}</td>
					<td style="padding: 0.85rem 1rem; font-weight: 600;">${s.candidates}</td>
					<td style="padding: 0.85rem 1rem;">
						${this._pill(s.status, status_bg[s.status] || '#f1f3f5', status_color[s.status] || '#495057')}
					</td>
				</tr>
			`);
		});

		$card.find('.card-body-area').append($table);
		this.$content.append($card);
	}

	render_certification(stats) {
		let pct = stats.eligible ? Math.round(stats.issued / stats.eligible * 100) : 0;
		let $card = this._card('Certification', 'file-text');
		$card.find('.card-body-area').html(`
			<div style="padding: 16px;">
				<div class="d-flex" style="gap: 24px; margin-bottom: 12px;">
					${this._mini_stat('Issued', stats.issued, '#198754')}
					${this._mini_stat('Eligible', stats.eligible)}
					${this._mini_stat('Pending', stats.pending, stats.pending > 0 ? '#fd7e14' : '#6c757d')}
				</div>
				<div style="background: #e9ecef; border-radius: 4px; height: 8px; overflow: hidden;">
					<div style="width: ${pct}%; height: 100%; background: #198754; border-radius: 4px;"></div>
				</div>
				<div class="text-muted" style="font-size: 0.78rem; margin-top: 6px;">${pct}% certificates issued</div>
			</div>
		`);
		this.$content.append($card);
	}

	render_evaluation(stats) {
		let pct = stats.total ? Math.round(stats.evaluated / stats.total * 100) : 0;
		let $card = this._card('Evaluation Progress', 'check');
		$card.find('.card-body-area').html(`
			<div style="padding: 16px;">
				<div class="d-flex" style="gap: 24px; margin-bottom: 12px;">
					${this._mini_stat('Evaluated', stats.evaluated, '#198754')}
					${this._mini_stat('Total', stats.total)}
					${this._mini_stat('Pending', stats.pending, stats.pending > 0 ? '#fd7e14' : '#6c757d')}
				</div>
				<div style="background: #e9ecef; border-radius: 4px; height: 8px; overflow: hidden;">
					<div style="width: ${pct}%; height: 100%; background: #198754; border-radius: 4px;"></div>
				</div>
				<div class="text-muted" style="font-size: 0.78rem; margin-top: 6px;">${pct}% evaluated</div>
			</div>
		`);
		this.$content.append($card);
	}

	_card(title, icon) {
		let $card = $(`
			<div style="background: #fff; border: 1px solid rgba(0,0,0,0.08); border-radius: 6px; overflow: hidden; margin-bottom: 12px;">
				<div style="background: #fafbfc; border-bottom: 1px solid rgba(0,0,0,0.06); padding: 0.75rem 1.1rem; font-weight: 600; font-size: 0.95rem; display: inline-flex; align-items: center; gap: 6px;">
					<span style="color: #868e96;">${ficon(icon)}</span>${title}
				</div>
				<div class="card-body-area"></div>
			</div>
		`);
		return $card;
	}

	_mini_stat(label, value, color) {
		return `<div>
			<div class="text-muted" style="font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.03em;">${label}</div>
			<div style="font-size: 1.15rem; font-weight: 600; ${color ? 'color:' + color : ''}">${value}</div>
		</div>`;
	}
}
