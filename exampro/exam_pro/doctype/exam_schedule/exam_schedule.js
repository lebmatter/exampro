// Copyright (c) 2024, Labeeb Mattra and contributors
// For license information, please see license.txt

frappe.ui.form.on('Exam Schedule', {
    refresh: function(frm) {
        // Fetch and display the status
        frm.call('get_exam_schedule_status')
            .then(r => {
                if (r.message) {
                    const status = r.message;
                    let color;
                    
                    // Set color based on status
                    if (status === "Upcoming") {
                        color = "blue";
                    } else if (status === "Ongoing") {
                        color = "green";
                    } else {
                        color = "gray";
                    }
                    
                    // Add the status indicator to the form
                    frm.page.set_indicator(status, color);
                }
            })
            .catch(err => {
                console.error("Error fetching exam schedule status:", err);
                // Set a default indicator if there's an error
                frm.page.set_indicator("Unknown", "gray");
            });
            
        // Add Actions dropdown with Generate Invite Link, Send Certificates, and Recompute Results
        frm.add_custom_button(__('Generate Invite Link'), function() {
            generate_invite_link(frm);
        }, __('Actions'));
        
        frm.add_custom_button(__('Send Certificates'), function() {
            send_certificates(frm);
        }, __('Actions'));
        
        frm.add_custom_button(__('Recompute Results'), function() {
            recompute_results(frm);
        }, __('Actions'));
    }
});

function generate_invite_link(frm) {
    frappe.show_alert({
        message: __('Generating invite link...'),
        indicator: 'blue'
    });
    
    frm.call('generate_invite_link')
        .then(r => {
            if (r.message) {
                // Show success message and refresh the form
                frappe.show_alert({
                    message: __('Invite link generated successfully!'),
                    indicator: 'green'
                });
                frm.refresh_field('schedule_invite_link');
                
                // Add a copy button next to the field
                setTimeout(() => {
                    if (frm.doc.schedule_invite_link) {
                        $(`[data-fieldname="schedule_invite_link"]`)
                            .find('.control-value-container')
                            .append(
                                `<button class="btn btn-xs btn-default copy-link" 
                                style="margin-left: 10px;" 
                                data-link="${frm.doc.schedule_invite_link}">
                                <i class="fa fa-copy"></i> Copy</button>`
                            );
                        
                        $('.copy-link').click(function() {
                            let link = $(this).data('link');
                            navigator.clipboard.writeText(link).then(function() {
                                frappe.show_alert({
                                    message: __('Link copied to clipboard!'),
                                    indicator: 'green'
                                });
                            });
                        });
                    }
                }, 500);
            }
        })
        .catch(err => {
            console.error("Error generating invite link:", err);
            frappe.show_alert({
                message: __('Failed to generate invite link. Please try again.'),
                indicator: 'red'
            });
        });
}

function send_certificates(frm) {
    // Check if exam has certification enabled
    frappe.db.get_value('Exam', frm.doc.exam, 'enable_certification')
        .then(r => {
            if (!r.message.enable_certification) {
                frappe.msgprint({
                    title: __('Certification Not Enabled'),
                    message: __('Certification is not enabled for this exam. Please enable it in the Exam settings first.'),
                    indicator: 'orange'
                });
                return;
            }
            
            // Confirm before sending certificates
            frappe.confirm(
                __('Are you sure you want to send certificates for this exam schedule? This will process all passed submissions and send certificate emails.'),
                function() {
                    // Show processing message
                    frappe.show_alert({
                        message: __('Processing certificates... This may take a while.'),
                        indicator: 'blue'
                    });
                    
                    // Call the send certificates function
                    frappe.call({
                        method: 'exampro.exam_pro.doctype.exam_schedule.exam_schedule.send_certificates',
                        args: {
                            docname: frm.doc.name
                        },
                        callback: function(r) {
                            if (r.message) {
                                frappe.msgprint({
                                    title: __('Certificates Sent Successfully'),
                                    message: __('Certificate sending completed successfully!<br><br><strong>Results:</strong><br>{0}', [r.message.replace(/\n/g, '<br>')]),
                                    indicator: 'green'
                                });
                            } else {
                                frappe.msgprint({
                                    title: __('Certificates Sent'),
                                    message: __('Certificate sending process completed.'),
                                    indicator: 'green'
                                });
                            }
                        },
                        error: function(r) {
                            frappe.msgprint({
                                title: __('Error Sending Certificates'),
                                message: __('An error occurred while sending certificates:<br><br>{0}', [r.message || 'Unknown error occurred']),
                                indicator: 'red'
                            });
                        },
                        freeze: true,
                        freeze_message: __('Sending certificates...')
                    });
                }
            );
        });
}

function recompute_results(frm) {
    // Confirm before recomputing results
    frappe.confirm(
        __('Are you sure you want to recompute results for this exam schedule? This will recalculate marks and status for all submissions and may take some time.'),
        function() {
            // Show processing message
            frappe.show_alert({
                message: __('Recomputing results... This may take a while.'),
                indicator: 'blue'
            });
            
            // Call the recompute results function
            frappe.call({
                method: 'exampro.exam_pro.doctype.exam_schedule.exam_schedule.recompute_results_for_schedule',
                args: {
                    schedule: frm.doc.name
                },
                callback: function(r) {
                    frappe.msgprint({
                        title: __('Results Recomputed Successfully'),
                        message: __('All exam submissions have been processed and their results updated successfully.'),
                        indicator: 'green'
                    });
                    
                    // Refresh the form to show updated data
                    frm.refresh();
                },
                error: function(r) {
                    frappe.msgprint({
                        title: __('Error Recomputing Results'),
                        message: __('An error occurred while recomputing results:<br><br>{0}', [r.message || 'Unknown error occurred while recomputing results']),
                        indicator: 'red'
                    });
                },
                freeze: true,
                freeze_message: __('Recomputing results...')
            });
        }
    );
}