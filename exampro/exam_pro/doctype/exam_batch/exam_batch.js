// Copyright (c) 2025, Labeeb Mattra and contributors
// For license information, please see license.txt

frappe.ui.form.on("Exam Batch", {
	refresh(frm) {
		// Add "Bulk Add Users" button in the form
		frm.add_custom_button(__('Bulk Add Users'), function() {
			show_bulk_add_users_dialog(frm);
		});
	},
});

function show_bulk_add_users_dialog(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __('Bulk Add Users'),
		fields: [
			{
				fieldname: 'user_emails',
				fieldtype: 'Text',
				label: __('User Emails (Comma Separated)'),
				reqd: 1,
				description: __('Enter comma separated email addresses')
			}
		],
		primary_action_label: __('Add Users'),
		primary_action: function() {
			const values = dialog.get_values();
			if (!values.user_emails) {
				frappe.msgprint(__('Please enter email addresses'));
				return;
			}
			
			// Show loading indicator
			frappe.show_progress(__('Adding Users'), 0, 100);
			
			// Call server-side method to add users
			frappe.call({
				method: 'exampro.exam_pro.doctype.exam_batch.exam_batch.bulk_add_users',
				args: {
					batch_name: frm.doc.name,
					emails: values.user_emails
				},
				callback: function(r) {
					frappe.hide_progress();
					if (r.message) {
						frappe.msgprint(__(`${r.message.added} users added successfully. ${r.message.skipped} users skipped.`));
						frm.reload_doc();
					}
				}
			});
			dialog.hide();
		}
	});
	
	dialog.show();
}
