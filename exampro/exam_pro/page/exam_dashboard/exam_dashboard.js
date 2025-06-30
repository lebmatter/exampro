frappe.pages['exam-dashboard'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Exam Dashboard',
        single_column: true
    });

    // Add filters
    page.add_field({
        fieldtype: 'Date',
        fieldname: 'start_date',
        label: 'From Date',
        default: frappe.datetime.add_days(frappe.datetime.get_today(), -30),
        onchange: function() {
            exam_dashboard.refresh();
        }
    });
    
    page.add_field({
        fieldtype: 'Date',
        fieldname: 'end_date',
        label: 'To Date',
        default: frappe.datetime.get_today(),
        onchange: function() {
            exam_dashboard.refresh();
        }
    });

    wrapper.exam_dashboard = new ExamDashboard(wrapper, page);
};

// Dashboard class
class ExamDashboard {
    constructor(wrapper, page) {
        this.wrapper = wrapper;
        this.page = page;
        this.make();
    }

    make() {
        this.$container = $('<div class="exam-dashboard">').appendTo(this.wrapper);
        
        // Create sections for metrics, charts, and tables
        this.$metrics_section = $('<div class="metrics-section">').appendTo(this.$container);
        this.$chart_section = $('<div class="chart-section">').appendTo(this.$container);
        this.$table_section = $('<div class="table-section">').appendTo(this.$container);
        
        this.refresh();
    }

    refresh() {
        this.filters = this.get_filters();
        this.fetch_and_render_data();
    }

    get_filters() {
        return {
            start_date: this.page.fields_dict.start_date.get_value(),
            end_date: this.page.fields_dict.end_date.get_value()
        };
    }

    fetch_and_render_data() {
        frappe.call({
            method: "exampro.exam_pro.page.exam_dashboard.exam_dashboard.get_dashboard_data",
            args: {
                filters: this.filters
            },
            callback: (r) => {
                if (!r.exc) {
                    this.render_metrics(r.message);
                    this.render_charts(r.message);
                    this.render_tables(r.message);
                }
            }
        });
    }

    render_metrics(data) {
        const metrics = [
            {
                label: 'Total Exams',
                value: data.total_exams,
                icon: 'book',
                color: 'blue'
            },
            {
                label: 'Total Schedules',
                value: data.total_schedules,
                icon: 'calendar',
                color: 'green'
            },
            {
                label: 'Total Candidates',
                value: data.total_candidates,
                icon: 'users',
                color: 'orange'
            },
            {
                label: 'Completed Exams',
                value: data.completed_exams,
                icon: 'check',
                color: 'purple'
            },
            {
                label: 'Pass Rate',
                value: data.pass_rate + '%',
                icon: 'percentage',
                color: 'red'
            },
            {
                label: 'Avg Score',
                value: data.avg_score.toFixed(2),
                icon: 'star',
                color: 'yellow'
            }
        ];

        this.$metrics_section.empty();
        
        // Create metric cards
        const $metrics_container = $('<div class="metrics-container d-flex flex-wrap">').appendTo(this.$metrics_section);
        
        metrics.forEach(metric => {
            const $metric_card = $(`
                <div class="metric-card" style="width: 200px; margin: 10px; padding: 15px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
                    <div class="d-flex align-items-center">
                        <div class="mr-3">
                            <div class="icon-circle bg-${metric.color}-light text-${metric.color}" style="width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center;">
                                <i class="fa fa-${metric.icon}"></i>
                            </div>
                        </div>
                        <div>
                            <div class="text-muted small">${metric.label}</div>
                            <div class="metric-value h4 mt-1">${metric.value}</div>
                        </div>
                    </div>
                </div>
            `);
            
            $metrics_container.append($metric_card);
        });
    }

    render_charts(data) {
        this.$chart_section.empty();
        
        // Create chart container with two columns
        const $chart_container = $('<div class="chart-container d-flex flex-wrap">').appendTo(this.$chart_section);
        
        // Create containers for each chart
        const $exam_status_chart = $('<div class="chart-box" style="width: 48%; margin: 1%; height: 300px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); border-radius: 5px; padding: 15px;">').appendTo($chart_container);
        const $exam_submissions_chart = $('<div class="chart-box" style="width: 48%; margin: 1%; height: 300px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); border-radius: 5px; padding: 15px;">').appendTo($chart_container);
        const $candidate_performance_chart = $('<div class="chart-box" style="width: 48%; margin: 1%; height: 300px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); border-radius: 5px; padding: 15px;">').appendTo($chart_container);
        const $schedule_type_chart = $('<div class="chart-box" style="width: 48%; margin: 1%; height: 300px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); border-radius: 5px; padding: 15px;">').appendTo($chart_container);
        
        // Render charts
        this.create_exam_status_chart($exam_status_chart, data);
        this.create_exam_submissions_chart($exam_submissions_chart, data);
        this.create_candidate_performance_chart($candidate_performance_chart, data);
        this.create_schedule_type_chart($schedule_type_chart, data);
    }

    create_exam_status_chart($container, data) {
        $container.append('<h6 class="mb-3">Exam Status Distribution</h6>');
        
        const chart = new frappe.Chart($container[0], {
            data: {
                labels: ["Started", "Not Started", "Submitted"],
                datasets: [{
                    name: "Exam Status",
                    values: [
                        data.status_distribution.Started || 0,
                        data.status_distribution['Not Started'] || 0,
                        data.status_distribution.Submitted || 0
                    ]
                }]
            },
            type: 'pie',
            colors: ['#ff5858', '#5ec962', '#7575ff'],
            height: 240
        });
    }

    create_exam_submissions_chart($container, data) {
        $container.append('<h6 class="mb-3">Exam Submissions Over Time</h6>');
        
        const chart = new frappe.Chart($container[0], {
            data: {
                labels: data.submission_trend.labels,
                datasets: [{
                    name: "Submissions",
                    type: 'line',
                    values: data.submission_trend.values
                }]
            },
            type: 'line',
            colors: ['#7cd6fd'],
            lineOptions: {
                hideDots: 0,
                dotSize: 5
            },
            height: 240
        });
    }

    create_candidate_performance_chart($container, data) {
        $container.append('<h6 class="mb-3">Score Distribution</h6>');
        
        const chart = new frappe.Chart($container[0], {
            data: {
                labels: ["0-20", "21-40", "41-60", "61-80", "81-100"],
                datasets: [{
                    name: "Candidates",
                    values: data.score_distribution
                }]
            },
            type: 'bar',
            colors: ['#5e64ff'],
            height: 240
        });
    }

    create_schedule_type_chart($container, data) {
        $container.append('<h6 class="mb-3">Schedule Types</h6>');
        
        const chart = new frappe.Chart($container[0], {
            data: {
                labels: ["Fixed", "Flexible"],
                datasets: [{
                    name: "Schedule Type",
                    values: [
                        data.schedule_types.Fixed || 0,
                        data.schedule_types.Flexible || 0
                    ]
                }]
            },
            type: 'percentage',
            colors: ['#28a745', '#17a2b8'],
            height: 240
        });
    }

    render_tables(data) {
        this.$table_section.empty();
        
        // Create tables container
        const $tables_container = $('<div class="tables-container">').appendTo(this.$table_section);
        
        // Create Recent Exam Submissions table
        const $recent_submissions = $('<div class="table-box mb-4" style="box-shadow: 0 2px 5px rgba(0,0,0,0.1); border-radius: 5px; padding: 15px;">').appendTo($tables_container);
        $recent_submissions.append('<h6 class="mb-3">Recent Exam Submissions</h6>');
        
        if (data.recent_submissions.length) {
            const $table = $(`
                <table class="table table-bordered">
                    <thead>
                        <tr>
                            <th>Candidate</th>
                            <th>Exam</th>
                            <th>Submitted On</th>
                            <th>Score</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            `).appendTo($recent_submissions);
            
            data.recent_submissions.forEach(submission => {
                $(`
                    <tr>
                        <td>${submission.candidate_name}</td>
                        <td>${submission.exam}</td>
                        <td>${submission.submission_time}</td>
                        <td>${submission.score !== null ? submission.score : 'N/A'}</td>
                        <td>
                            <span class="badge ${submission.result_status === 'Pass' ? 'badge-success' : 'badge-danger'}">
                                ${submission.result_status || 'Pending'}
                            </span>
                        </td>
                    </tr>
                `).appendTo($table.find('tbody'));
            });
        } else {
            $recent_submissions.append('<div class="text-muted">No recent submissions</div>');
        }
        
        // Create Top Exams table
        const $top_exams = $('<div class="table-box" style="box-shadow: 0 2px 5px rgba(0,0,0,0.1); border-radius: 5px; padding: 15px;">').appendTo($tables_container);
        $top_exams.append('<h6 class="mb-3">Top Exams by Participation</h6>');
        
        if (data.top_exams.length) {
            const $table = $(`
                <table class="table table-bordered">
                    <thead>
                        <tr>
                            <th>Exam</th>
                            <th>Participants</th>
                            <th>Avg. Score</th>
                            <th>Pass Rate</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            `).appendTo($top_exams);
            
            data.top_exams.forEach(exam => {
                $(`
                    <tr>
                        <td>${exam.exam}</td>
                        <td>${exam.participants}</td>
                        <td>${exam.avg_score ? exam.avg_score.toFixed(2) : 'N/A'}</td>
                        <td>${exam.pass_rate ? exam.pass_rate + '%' : 'N/A'}</td>
                    </tr>
                `).appendTo($table.find('tbody'));
            });
        } else {
            $top_exams.append('<div class="text-muted">No exam data available</div>');
        }
    }
}
