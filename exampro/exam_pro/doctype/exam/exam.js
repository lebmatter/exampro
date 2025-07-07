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
	// Show a loading indicator
	let loadingIndicator = frappe.show_alert(__('Loading questions...'), 15);

	// Call the server-side method to get question categories
	frappe.call({
		method: "exampro.www.manage.exams.get_question_categories",
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
						<table class="table table-bordered">
							<thead>
								<tr>
									<th>${__('Category')}</th>
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
					
					tableHtml += `
						<tr>
							<td>${cat.category_name}</td>
							<td>${cat.marks_per_question}</td>
							<td>${cat.question_count}</td>
							<td>${selectedCount}</td>
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
					title: __('Exam Questions'),
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
								<div class="row">
									<div class="col-md-6">
										<strong>${__('Total Selected Questions')}:</strong> ${totalSelected}
									</div>
									<div class="col-md-6">
										<strong>${__('Total Marks')}:</strong> ${totalMarks}
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
