// Copyright (c) 2024, Labeeb Mattra and contributors
// For license information, please see license.txt

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
	},
});

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
