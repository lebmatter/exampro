// Copyright (c) 2024, Labeeb Mattra and contributors
// For license information, please see license.txt

frappe.ui.form.on("Exam Category Settings", {
	question_category: function(frm, cdt, cdn) {
		checkDuplicateSelectRow(frm, cdt, cdn);
	},
	mark_per_question: function(frm, cdt, cdn) {
		checkDuplicateSelectRow(frm, cdt, cdn);
	},
});

function checkDuplicateSelectRow(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row || !row.question_category || !row.mark_per_question) return;
	const dup = (frm.doc.select_questions || []).find(r =>
		r.name !== row.name &&
		r.question_category === row.question_category &&
		cint(r.mark_per_question) === cint(row.mark_per_question)
	);
	if (!dup) return;

	frappe.msgprint({
		title: __('Duplicate Row'),
		indicator: 'orange',
		message: __('A row for category <b>{0}</b> with <b>{1}</b> mark per question already exists. Edit the existing row to change the count instead of adding a duplicate.', [row.question_category, row.mark_per_question])
	});

	const grid = frm.get_field('select_questions').grid;
	const grid_row = grid.grid_rows_by_docname[cdn];
	if (grid_row) {
		grid_row.remove();
		frm.refresh_field('select_questions');
	}
}

frappe.ui.form.on("Exam", {
	refresh(frm) {
		// Add handler for view_questions button
		frm.add_custom_button(__('View Questions'), function() {
			showQuestionCategoriesModal(frm);
		}, __('Actions'));

		// Set view_questions button handler
		frm.fields_dict.view_questions.input.onclick = function() {
			showQuestionCategoriesModal(frm);
		};

		if (!frm.is_new()) {
			frm.add_custom_button(__('Export Exam (JSON)'), function() {
				exportExamJson(frm);
			}, __('Actions'));

			frm.add_custom_button(__('Duplicate Exam with Questions'), function() {
				duplicateExam(frm);
			}, __('Actions'));
		}

		frm.add_custom_button(__('Import Exam (JSON)'), function() {
			importExamDialog();
		}, __('Actions'));
	},
});

function exportExamJson(frm) {
	const indicator = frappe.show_alert(__('Preparing export...'), 30);
	frappe.call({
		method: "exampro.exam_pro.doctype.exam.import_export.export_exam",
		args: { exam: frm.doc.name },
		callback: function(r) {
			indicator.hide();
			if (!r.message) {
				frappe.msgprint({ title: __('Error'), indicator: 'red', message: __('Export failed') });
				return;
			}
			const blob = new Blob([JSON.stringify(r.message, null, 2)], { type: 'application/json' });
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = `exam-${frm.doc.name}-${frappe.datetime.now_date()}.json`;
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(url);
		}
	});
}

function duplicateExam(frm) {
	frappe.confirm(
		__('Create a copy of this exam? The new exam will reuse the same question categories and questions.'),
		function() {
			frappe.call({
				method: "exampro.exam_pro.doctype.exam.import_export.duplicate_exam",
				args: { exam: frm.doc.name },
				freeze: true,
				freeze_message: __('Duplicating exam...'),
				callback: function(r) {
					if (r && r.message && r.message.name) {
						frappe.show_alert({ message: __('Duplicated: {0}', [r.message.title]), indicator: 'green' }, 7);
						frappe.set_route('Form', 'Exam', r.message.name);
					}
				}
			});
		}
	);
}

function importExamDialog() {
	const d = new frappe.ui.Dialog({
		title: __('Import Exam from JSON'),
		fields: [
			{
				fieldtype: 'HTML',
				fieldname: 'help',
				options: `<p class="text-muted small">${__("Upload a JSON file produced by Export Exam. Images are restored from embedded base64 data. The imported exam is created with title suffix \" (Imported)\".")}</p>`
			},
			{
				fieldtype: 'Attach',
				fieldname: 'json_file',
				label: __('JSON File'),
				reqd: 1,
				options: { restrictions: { allowed_file_types: ['.json', 'application/json'] } }
			}
		],
		primary_action_label: __('Import'),
		primary_action: function(values) {
			if (!values.json_file) return;
			d.disable_primary_action();
			d.set_message(__('Reading file...'));
			fetch(values.json_file, { credentials: 'same-origin' })
				.then(resp => {
					if (!resp.ok) throw new Error(`Could not read uploaded file (${resp.status})`);
					return resp.text();
				})
				.then(text => {
					if (text.length > 50 * 1024 * 1024) {
						throw new Error(__('File too large (max 50 MB)'));
					}
					d.set_message(__('Importing...'));
					return frappe.call({
						method: "exampro.exam_pro.doctype.exam.import_export.import_exam",
						args: { json_text: text },
						freeze: true,
						freeze_message: __('Importing exam...')
					});
				})
				.then(r => {
					d.hide();
					if (r && r.message && r.message.name) {
						frappe.show_alert({ message: __('Exam imported: {0}', [r.message.title]), indicator: 'green' }, 7);
						frappe.set_route('Form', 'Exam', r.message.name);
					}
				})
				.catch(err => {
					d.enable_primary_action();
					d.clear_message();
					frappe.msgprint({ title: __('Import Failed'), indicator: 'red', message: err.message || String(err) });
				});
		}
	});
	d.show();
}

// Function to show the questions modal
function showQuestionCategoriesModal(frm) {
	// Check if exam exists
	if (!frm.doc.name) {
		frappe.msgprint({
			title: __('Error'),
			indicator: 'red',
			message: __('Please save the exam first before viewing available questions.')
		});
		return;
	}

	// Show a loading indicator
	let loadingIndicator = frappe.show_alert(__('Loading questions...'), 15);

	// Call the server-side method to get question categories
	frappe.call({
		method: "exampro.exam_pro.doctype.exam.exam.get_question_categories",
		args: {
			exam: frm.doc.name
		},
		callback: function(response) {
			// Hide the loading indicator
			loadingIndicator.hide();

			if (response.message && response.message.success) {
				// Create a dialog to display the questions
				const categories = response.message.categories || [];
				const examConfig = response.message.exam_config || {};
				
				// Create HTML for the table
				let tableHtml = `
					<div class="table-responsive">
						<table class="table table-bordered table-striped">
							<thead class="table-dark">
								<tr>
									<th>${__('Category')}</th>
									<th>${__('Question Type')}</th>
									<th>${__('Marks/Question')}</th>
									<th>${__('Available Questions')}</th>
									<th>${__('Selected Questions')}</th>
								</tr>
							</thead>
							<tbody>
				`;
				
				// Add rows for each category
				categories.forEach(cat => {
					const compositeKey = cat.id;
					const selectedCount = examConfig[compositeKey] || 0;
					const availableClass = cat.question_count > 0 ? 'text-success' : 'text-muted';
					const selectedClass = selectedCount > 0 ? 'text-primary font-weight-bold' : '';
					
					tableHtml += `
						<tr>
							<td>${cat.category_name}</td>
							<td><span class="badge badge-info">${cat.question_type}</span></td>
							<td class="text-center">${cat.marks_per_question}</td>
							<td class="text-center ${availableClass}">${cat.question_count}</td>
							<td class="text-center ${selectedClass}">${selectedCount}</td>
						</tr>
					`;
				});
				
				// Close the table
				tableHtml += `
							</tbody>
						</table>
					</div>
				`;
				
				// Calculate totals
				let totalSelected = 0;
				let totalMarks = 0;
				
				Object.keys(examConfig).forEach(key => {
					const count = examConfig[key];
					const category = categories.find(c => c.id === key);
					if (category) {
						totalSelected += count;
						totalMarks += count * category.marks_per_question;
					}
				});
				
				// Create the dialog
				const d = new frappe.ui.Dialog({
					title: __('Available Questions Overview'),
					size: 'large',
					fields: [
						{
							fieldtype: 'HTML',
							fieldname: 'questions_table',
							options: tableHtml
						},
						{
							fieldtype: 'HTML',
							fieldname: 'summary',
							options: `
								<div class="row mt-3">
									<div class="col-md-6">
										<div class="card border-primary">
											<div class="card-body text-center">
												<h5 class="card-title text-primary">${totalSelected}</h5>
												<p class="card-text">${__('Total Selected Questions')}</p>
											</div>
										</div>
									</div>
									<div class="col-md-6">
										<div class="card border-success">
											<div class="card-body text-center">
												<h5 class="card-title text-success">${totalMarks}</h5>
												<p class="card-text">${__('Total Marks')}</p>
											</div>
										</div>
									</div>
								</div>
							`
						}
					],
					primary_action_label: __('Close'),
					primary_action: function() {
						d.hide();
					}
				});
				
				d.show();
			} else {
				// Show an error message if the call failed
				frappe.msgprint({
					title: __('Error'),
					indicator: 'red',
					message: response.message?.error || __('Failed to load question categories')
				});
			}
		}
	});
}
