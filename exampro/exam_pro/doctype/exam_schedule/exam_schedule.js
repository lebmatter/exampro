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
                    
                    // Add Actions dropdown based on status
                    add_status_based_actions(frm, status);
                }
            })
            .catch(err => {
                console.error("Error fetching exam schedule status:", err);
                // Set a default indicator if there's an error
                frm.page.set_indicator("Unknown", "gray");
                // Add all actions as fallback
                add_status_based_actions(frm, "Unknown");
            });
        
        // Load examiner assignment counts dynamically
        load_examiner_assignment_counts(frm);
    }
});

function add_status_based_actions(frm, status) {
    // Clear any existing actions to avoid duplicates
    frm.page.clear_actions_menu();
    
    // Add actions based on status
    if (status !== "Completed") {
        // Generate Invite Link - show for Upcoming and Ongoing, not for Completed
        frm.add_custom_button(__('Generate Invite Link'), function() {
            generate_invite_link(frm);
        }, __('Actions'));
    }
    
    if (status === "Completed") {
        // Send Certificates - only show if status is Completed
        frm.add_custom_button(__('Send Certificates'), function() {
            send_certificates(frm);
        }, __('Actions'));
        
        // Recompute Results - only for Completed
        frm.add_custom_button(__('Recompute Results'), function() {
            recompute_results(frm);
        }, __('Actions'));
    }
    
    if (status !== "Completed") {
        // Bulk Add Submissions - not for Completed schedules
        frm.add_custom_button(__('Bulk Add Submissions'), function() {
            bulk_add_submissions(frm);
        }, __('Actions'));
    }
}

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

function bulk_add_submissions(frm) {
    let dialog = new frappe.ui.Dialog({
        title: __('Bulk Add Exam Submissions'),
        fields: [
            {
                label: __('Email Addresses'),
                fieldname: 'email_list',
                fieldtype: 'Long Text',
                reqd: 1,
                description: __('Enter email addresses separated by commas, semicolons, or new lines')
            }
        ],
        primary_action_label: __('Add Submissions'),
        primary_action: function(values) {
            if (!values.email_list) {
                frappe.msgprint(__('Please enter at least one email address'));
                return;
            }
            
            // Show processing message
            frappe.show_alert({
                message: __('Processing email addresses...'),
                indicator: 'blue'
            });
            
            // Call the bulk add submissions function
            frappe.call({
                method: 'exampro.exam_pro.doctype.exam_schedule.exam_schedule.bulk_add_submissions',
                args: {
                    schedule_name: frm.doc.name,
                    email_list: values.email_list
                },
                callback: function(r) {
                    if (r.message) {
                        let result = r.message;
                        let message = __('Bulk submission process completed!<br><br>');
                        
                        if (result.added > 0) {
                            message += __('<strong>Successfully added:</strong> {0} submissions<br>', [result.added]);
                        }
                        
                        if (result.duplicates > 0) {
                            message += __('<strong>Skipped duplicates:</strong> {0} submissions<br>', [result.duplicates]);
                        }
                        
                        if (result.invalid_users && result.invalid_users.length > 0) {
                            message += __('<strong>Invalid/Non-existent users:</strong><br>');
                            result.invalid_users.forEach(email => {
                                message += __('• {0}<br>', [email]);
                            });
                        }
                        
                        frappe.msgprint({
                            title: __('Bulk Add Submissions Completed'),
                            message: message,
                            indicator: result.invalid_users && result.invalid_users.length > 0 ? 'orange' : 'green'
                        });
                    }
                    dialog.hide();
                    frm.refresh();
                },
                error: function(r) {
                    frappe.msgprint({
                        title: __('Error Adding Submissions'),
                        message: __('An error occurred while adding submissions:<br><br>{0}', [r.message || 'Unknown error occurred']),
                        indicator: 'red'
                    });
                },
                freeze: true,
                freeze_message: __('Adding submissions...')
            });
        }
    });
    
    dialog.show();
}

function load_examiner_assignment_counts(frm) {
    if (!frm.doc.examiners || frm.doc.examiners.length === 0) {
        return;
    }
    
    // Prevent multiple calls by checking if we're already loading
    if (frm._loading_examiner_counts) {
        return;
    }
    frm._loading_examiner_counts = true;
    
    // Call the backend function to get examiner assignment counts
    frappe.call({
        method: 'exampro.exam_pro.doctype.exam_submission.exam_submission.get_examiner_assignment_counts',
        args: {
            exam_schedule: frm.doc.name
        },
        callback: function(r) {
            if (r.message) {
                let assignment_counts = r.message;
                console.log('Assignment counts from server:', assignment_counts);
                
                // Update each examiner row with the counts
                frm.doc.examiners.forEach((examiner, idx) => {
                    let counts = assignment_counts[examiner.examiner] || {
                        proctoring_count: 0,
                        evaluation_count: 0
                    };
                    
                    console.log(`Setting counts for ${examiner.examiner}:`, counts);
                    
                    // Set the values directly in the doc
                    examiner.proctoring_count = counts.proctoring_count;
                    examiner.evaluation_count = counts.evaluation_count;
                });
                
                // Refresh the examiners field to show updated values
                frm.refresh_field('examiners');
            }
            frm._loading_examiner_counts = false;
        },
        error: function(r) {
            console.error('Error loading examiner assignment counts:', r);
            frm._loading_examiner_counts = false;
        }
    });
}