// Copyright (c) 2024, Labeeb Mattra and contributors
// For license information, please see license.txt

frappe.ui.form.on('Exam Schedule', {
    refresh: function(frm) {
        $(".ongoing-stats-banner").remove();
        if (frm._ends_in_interval) {
            clearInterval(frm._ends_in_interval);
        }
        frm._refresh_id = (frm._refresh_id || 0) + 1;
        let current_refresh = frm._refresh_id;
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
                    
                    frm.page.set_indicator(status, color);

                    if (status === "Ongoing") {
                        show_ongoing_stats_banner(frm);
                    }

                    add_status_based_actions(frm, status);

                    // Add Schedule Dashboard button
                    if (!frm.is_new()) {
                        frm.add_custom_button(__('Schedule Dashboard'), function() {
                            window.location.href = '/app/schedule-dashboard?exam_schedule=' + encodeURIComponent(frm.doc.name);
                        }).addClass('btn-info');
                    }
                }
            })
            .catch(err => {
                console.error("Error fetching exam schedule status:", err);
                // Set a default indicator if there's an error
                frm.page.set_indicator("Unknown", "gray");
                // Add all actions as fallback
                add_status_based_actions(frm, "Unknown");
            });
    },
    
    show_assignment_count: function(frm) {
        show_assignment_counts(frm);
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
        // Proctor Archive - review videos and messages from completed schedule
        frm.add_custom_button(__('Proctor Archive'), function() {
            window.open('/proctor-archive?exam_schedule=' + encodeURIComponent(frm.doc.name), '_blank');
        }, __('Actions'));

        // Send Certificates - only show if status is Completed
        frm.add_custom_button(__('Send Certificates'), function() {
            send_certificates(frm);
        }, __('Actions'));

        // Recompute Results - only for Completed
        frm.add_custom_button(__('Recompute Results'), function() {
            recompute_results(frm);
        }, __('Actions'));

        // Export Results as CSV - only for Completed
        frm.add_custom_button(__('Export Results as CSV'), function() {
            export_results_csv(frm);
        }, __('Actions'));
    }
    
    if (status !== "Completed") {
        // Bulk Add Submissions - not for Completed schedules
        frm.add_custom_button(__('Bulk Add Submissions'), function() {
            bulk_add_submissions(frm);
        }, __('Actions'));
    }

    if (status === "Ongoing") {
        frm.add_custom_button(__('Force Terminate'), function() {
            show_force_terminate_dialog(frm);
        }, __('Actions'));
    }
}

function show_force_terminate_dialog(frm) {
    let d = new frappe.ui.Dialog({
        title: __('Force Terminate Schedule'),
        fields: [
            {
                fieldtype: 'HTML',
                options: `<div class="alert alert-danger" style="margin-bottom: 12px;">
                    <strong>Warning:</strong> This will immediately terminate all active (Registered and Started) candidate submissions for this schedule. This action cannot be undone.
                </div>`
            },
            {
                fieldtype: 'Data',
                fieldname: 'confirm_text',
                label: 'Type <strong>terminate schedule</strong> to confirm',
                reqd: 0
            }
        ],
        primary_action_label: __('Terminate'),
        primary_action(values) {
            if (values.confirm_text !== 'terminate schedule') {
                frappe.show_alert({
                    message: __('Please type "terminate schedule" exactly to confirm.'),
                    indicator: 'red'
                });
                return;
            }
            d.hide();
            frappe.call({
                method: 'exampro.exam_pro.doctype.exam_schedule.exam_schedule.force_terminate_schedule',
                args: { schedule_name: frm.doc.name },
                callback(r) {
                    if (r.message) {
                        frappe.show_alert({
                            message: __('Terminated {0} submission(s).', [r.message.terminated]),
                            indicator: 'green'
                        });
                        frm.reload_doc();
                    }
                }
            });
        }
    });
    d.show();
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
                                <i data-feather="copy"></i> Copy</button>`
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

function export_results_csv(frm) {
    frappe.show_alert({ message: __('Preparing CSV export...'), indicator: 'blue' });
    frappe.call({
        method: 'exampro.exam_pro.doctype.exam_schedule.exam_schedule.export_results_csv',
        args: { schedule_name: frm.doc.name },
        callback: function(r) {
            if (r.message) {
                let blob = new Blob([r.message], { type: 'text/csv' });
                let url = URL.createObjectURL(blob);
                let a = document.createElement('a');
                a.href = url;
                a.download = frm.doc.name + '_results.csv';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            }
        }
    });
}

function show_assignment_counts(frm) {
    // Show processing message
    frappe.show_alert({
        message: __('Loading assignment counts...'),
        indicator: 'blue'
    });
    
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
                
                // Prepare data for the table
                let table_data = [];
                
                // Add data for each examiner
                frm.doc.examiners.forEach((examiner_row) => {
                    let examiner_email = examiner_row.examiner;
                    let counts = assignment_counts[examiner_email] || {
                        proctoring_count: 0,
                        evaluation_count: 0
                    };
                    
                    // Get examiner name from User doctype
                    let examiner_name = examiner_row.examiner; // fallback to email
                    
                    table_data.push([
                        examiner_name,
                        examiner_email,
                        examiner_row.can_proctor ? 'Yes' : 'No',
                        examiner_row.can_evaluate ? 'Yes' : 'No',
                        counts.proctoring_count,
                        counts.evaluation_count,
                        counts.proctoring_count + counts.evaluation_count
                    ]);
                });
                
                // Create and show the dialog with table
                let dialog = new frappe.ui.Dialog({
                    title: __('Examiner Assignment Counts'),
                    size: 'extra-large',
                    fields: [
                        {
                            fieldtype: 'HTML',
                            fieldname: 'assignment_table',
                            options: generate_assignment_table_html(table_data)
                        }
                    ],
                    primary_action_label: __('Close'),
                    primary_action: function() {
                        dialog.hide();
                    }
                });
                
                dialog.show();
            }
        },
        error: function(r) {
            console.error('Error loading examiner assignment counts:', r);
            frappe.msgprint({
                title: __('Error Loading Assignment Counts'),
                message: __('An error occurred while loading assignment counts:<br><br>{0}', [r.message || 'Unknown error occurred']),
                indicator: 'red'
            });
        }
    });
}

function show_ongoing_stats_banner(frm) {
    let refresh_id = frm._refresh_id;
    frappe.call({
        method: "exampro.exam_pro.doctype.exam_schedule.exam_schedule.get_submission_counts",
        args: { schedule: frm.doc.name },
        callback: function(r) {
            if (frm._refresh_id !== refresh_id) return;
            $(".ongoing-stats-banner").remove();
            let c = r.message || {};
            let total = Object.values(c).reduce((a, b) => a + b, 0);
            let live = c["Started"] || 0;
            let submitted = c["Submitted"] || 0;
            let terminated = c["Terminated"] || 0;

            let $banner = $(`
                <div class="ongoing-stats-banner" style="
                    padding: 12px 15px;
                    margin-bottom: 15px;
                    background: var(--alert-bg-green, #d1e7dd);
                    border-radius: var(--border-radius-md, 6px);
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    flex-wrap: wrap;
                ">
                    <a href="/app/exam-submission?exam_schedule=${encodeURIComponent(frm.doc.name)}" class="indicator-pill blue no-indicator-dot" style="text-decoration:none;">${total} Registered</a>
                    <a href="/app/exam-submission?exam_schedule=${encodeURIComponent(frm.doc.name)}&status=Started" class="indicator-pill green no-indicator-dot" style="text-decoration:none;">${live} Live</a>
                    <a href="/app/exam-submission?exam_schedule=${encodeURIComponent(frm.doc.name)}&status=Submitted" class="indicator-pill orange no-indicator-dot" style="text-decoration:none;">${submitted} Submitted</a>
                    <a href="/app/exam-submission?exam_schedule=${encodeURIComponent(frm.doc.name)}&status=Terminated" class="indicator-pill red no-indicator-dot" style="text-decoration:none;">${terminated} Terminated</a>
                    <a class="btn btn-xs btn-info ongoing-dashboard-btn">
                        View Dashboard
                    </a>
                    <span class="ends-in-label text-muted" style="margin-left:auto;font-weight:600;font-size:var(--text-sm);"></span>
                </div>
            `);

            $banner.find(".ongoing-dashboard-btn").on("click", function(e) {
                e.preventDefault();
                window.location.href = "/app/schedule-dashboard?exam_schedule=" + encodeURIComponent(frm.doc.name);
            });

            frm.$wrapper.find(".form-dashboard").after($banner);
            start_ends_in_timer(frm);
        }
    });
}

function start_ends_in_timer(frm) {
    if (frm._ends_in_interval) {
        clearInterval(frm._ends_in_interval);
    }

    let end = moment(frm.doc.start_date_time).add(frm.doc.duration || 0, "minutes");
    if (frm.doc.schedule_type === "Flexible") {
        end.add(frm.doc.schedule_expire_in_days || 0, "days");
    }

    function update() {
        let diff = end.diff(moment());
        if (diff <= 0) {
            clearInterval(frm._ends_in_interval);
            $(".ongoing-stats-banner .ends-in-label").text("");
            return;
        }
        let dur = moment.duration(diff);
        let h = Math.floor(dur.asHours());
        let m = dur.minutes();
        let s = dur.seconds();
        let text = h > 0 ? `Ends in ${h}h ${m}m ${s}s` : `Ends in ${m}m ${s}s`;
        $(".ongoing-stats-banner .ends-in-label").text(text);
    }

    update();
    frm._ends_in_interval = setInterval(update, 1000);
}

function generate_assignment_table_html(table_data) {
    let html = `
        <div class="assignment-counts-table">
            <table class="table table-bordered">
                <thead>
                    <tr>
                        <th>${__('Examiner Name')}</th>
                        <th>${__('Email')}</th>
                        <th>${__('Can Proctor')}</th>
                        <th>${__('Can Evaluate')}</th>
                        <th>${__('Proctoring Count')}</th>
                        <th>${__('Evaluation Count')}</th>
                        <th>${__('Total Assignments')}</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    if (table_data.length === 0) {
        html += `
            <tr>
                <td colspan="7" class="text-center text-muted">
                    ${__('No examiners found')}
                </td>
            </tr>
        `;
    } else {
        table_data.forEach((row) => {
            html += `
                <tr>
                    <td>${row[0]}</td>
                    <td>${row[1]}</td>
                    <td><span class="badge ${row[2] === 'Yes' ? 'badge-success' : 'badge-secondary'}">${row[2]}</span></td>
                    <td><span class="badge ${row[3] === 'Yes' ? 'badge-success' : 'badge-secondary'}">${row[3]}</span></td>
                    <td><span class="badge badge-primary">${row[4]}</span></td>
                    <td><span class="badge badge-info">${row[5]}</span></td>
                    <td><strong><span class="badge badge-dark">${row[6]}</span></strong></td>
                </tr>
            `;
        });
    }
    
    html += `
                </tbody>
            </table>
        </div>
        <style>
            .assignment-counts-table {
                margin-top: 15px;
            }
            .assignment-counts-table table {
                margin-bottom: 0;
            }
            .assignment-counts-table th {
                background-color: #f8f9fa;
                font-weight: 600;
                text-align: center;
            }
            .assignment-counts-table td {
                text-align: center;
                vertical-align: middle;
            }
            .badge {
                font-size: 0.875em;
            }
        </style>
    `;
    
    return html;
}
