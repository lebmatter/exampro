// Copyright (c) 2024, Labeeb Mattra and contributors
// For license information, please see license.txt

frappe.ui.form.on("Exam Certificate", {
	refresh(frm) {
		// Add View Certificate button if document is saved
		if (frm.doc.name && !frm.is_new()) {
			frm.add_custom_button(__('View Certificate'), function() {
				downloadCertificate(frm.doc.name);
			}, __('Actions'));
			
			// Add Send Certificate Email button
			frm.add_custom_button(__('Send Certificate Email'), function() {
				sendCertificateEmail(frm.doc.name);
			}, __('Actions'));
		}
	},
});

function downloadCertificate(certificateName) {
	// Get the button to show loading state
	const button = cur_frm.custom_buttons[__('View Certificate')];
	
	if (button) {
		// Show loading state
		const originalText = button.text();
		button.text(__('Downloading...'));
		button.prop('disabled', true);
	}

	// Create a form to submit the download request
	frappe.call({
		method: "exampro.exam_pro.doctype.exam_certificate.exam_certificate.download_certificate_pdf",
		args: {
			certificate_name: certificateName,
		},
		callback: function (r) {
			if (r.message) {
				// Create a temporary link to download the file
				const link = document.createElement("a");
				link.href = "data:application/pdf;base64," + r.message;
				link.download = `certificate_${certificateName}.pdf`;
				document.body.appendChild(link);
				link.click();
				document.body.removeChild(link);

				// Show success message
				frappe.show_alert({
					message: __("Certificate downloaded successfully!"),
					indicator: "green",
				});
			}
		},
		error: function (r) {
			frappe.show_alert({
				message: r.message || __("Error downloading certificate"),
				indicator: "red",
			});
		},
		always: function () {
			// Restore button state
			if (button) {
				button.text(__('View Certificate'));
				button.prop('disabled', false);
			}
		},
	});
}

function sendCertificateEmail(certificateName) {
	// Show confirmation dialog before sending email
	frappe.confirm(
		__('Are you sure you want to send the certificate email?'),
		function() {
			// Get the button to show loading state
			const button = cur_frm.custom_buttons[__('Send Certificate Email')];
			
			if (button) {
				// Show loading state
				const originalText = button.text();
				button.text(__('Sending...'));
				button.prop('disabled', true);
			}

			// Send the certificate email
			frappe.call({
				method: "exampro.exam_pro.doctype.exam_certificate.exam_certificate.send_certificate_email",
				args: {
					certificate_name: certificateName,
				},
				callback: function (r) {
					if (r.message && r.message.success) {
						// Show success message
						frappe.show_alert({
							message: __("Certificate email sent successfully!"),
							indicator: "green",
						});
						
						// Optional: Show additional success message in msgprint
						frappe.msgprint({
							title: __('Email Sent'),
							message: __('The certificate email has been sent to the candidate.'),
							indicator: 'green'
						});
					}
				},
				error: function (r) {
					frappe.show_alert({
						message: r.message || __("Error sending certificate email"),
						indicator: "red",
					});
				},
				always: function () {
					// Restore button state
					if (button) {
						button.text(__('Send Certificate Email'));
						button.prop('disabled', false);
					}
				},
			});
		}
	);
}
