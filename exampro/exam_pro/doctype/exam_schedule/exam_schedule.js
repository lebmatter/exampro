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
                    // Show progress dialog
                    let progress_dialog = new frappe.ui.Dialog({
                        title: __('Sending Certificates'),
                        fields: [
                            {
                                fieldtype: 'HTML',
                                fieldname: 'progress_area',
                                options: `
                                    <div class="progress-container">
                                        <div class="progress" style="height: 20px;">
                                            <div class="progress-bar progress-bar-striped progress-bar-animated" 
                                                 style="width: 0%;" id="cert-progress-bar"></div>
                                        </div>
                                        <div class="progress-text text-muted mt-2" id="cert-progress-text">
                                            Initializing...
                                        </div>
                                        <div class="progress-details mt-3" id="cert-progress-details">
                                        </div>
                                    </div>
                                `
                            }
                        ],
                        primary_action_label: __('Close'),
                        primary_action: function() {
                            progress_dialog.hide();
                        }
                    });
                    
                    progress_dialog.show();
                    progress_dialog.$wrapper.find('.btn-primary').hide(); // Hide close button initially
                    
                    // Call the send certificates function
                    frappe.call({
                        method: 'exampro.exam_pro.doctype.exam_schedule.exam_schedule.send_certificates',
                        args: {
                            docname: frm.doc.name
                        },
                        callback: function(r) {
                            if (r.message) {
                                // Update progress to 100%
                                $('#cert-progress-bar').css('width', '100%').removeClass('progress-bar-animated');
                                $('#cert-progress-text').text('Certificate sending completed successfully!');
                                $('#cert-progress-details').html(`
                                    <div class="alert alert-success">
                                        <strong>Results:</strong><br>
                                        ${r.message.replace(/\n/g, '<br>')}
                                    </div>
                                `);
                                
                                // Show close button
                                progress_dialog.$wrapper.find('.btn-primary').show();
                                
                                // Show success alert
                                frappe.show_alert({
                                    message: __('Certificates sent successfully!'),
                                    indicator: 'green'
                                });
                            }
                        },
                        error: function(r) {
                            $('#cert-progress-bar').css('width', '100%').removeClass('progress-bar-animated').addClass('bg-danger');
                            $('#cert-progress-text').text('Error occurred while sending certificates');
                            $('#cert-progress-details').html(`
                                <div class="alert alert-danger">
                                    <strong>Error:</strong><br>
                                    ${r.message || 'An unknown error occurred'}
                                </div>
                            `);
                            progress_dialog.$wrapper.find('.btn-primary').show();
                        },
                        freeze: false // Don't freeze the UI as we have our own progress dialog
                    });
                    
                    // Simulate progress updates (since we can't get real-time progress from server)
                    let progress = 0;
                    let progress_interval = setInterval(function() {
                        if (progress < 90) {
                            progress += Math.random() * 15;
                            if (progress > 90) progress = 90;
                            
                            $('#cert-progress-bar').css('width', progress + '%');
                            
                            if (progress < 30) {
                                $('#cert-progress-text').text('Checking submissions...');
                            } else if (progress < 60) {
                                $('#cert-progress-text').text('Processing certificates...');
                            } else {
                                $('#cert-progress-text').text('Sending emails...');
                            }
                        } else {
                            clearInterval(progress_interval);
                        }
                    }, 500);
                    
                    // Clear interval when dialog is hidden
                    progress_dialog.$wrapper.on('hidden.bs.modal', function() {
                        clearInterval(progress_interval);
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
            // Show progress dialog
            let progress_dialog = new frappe.ui.Dialog({
                title: __('Recomputing Results'),
                fields: [
                    {
                        fieldtype: 'HTML',
                        fieldname: 'progress_area',
                        options: `
                            <div class="progress-container">
                                <div class="progress" style="height: 20px;">
                                    <div class="progress-bar progress-bar-striped progress-bar-animated" 
                                         style="width: 0%;" id="recompute-progress-bar"></div>
                                </div>
                                <div class="progress-text text-muted mt-2" id="recompute-progress-text">
                                    Initializing...
                                </div>
                                <div class="progress-details mt-3" id="recompute-progress-details">
                                </div>
                            </div>
                        `
                    }
                ],
                primary_action_label: __('Close'),
                primary_action: function() {
                    progress_dialog.hide();
                }
            });
            
            progress_dialog.show();
            progress_dialog.$wrapper.find('.btn-primary').hide(); // Hide close button initially
            
            // Call the recompute results function
            frappe.call({
                method: 'exampro.exam_pro.doctype.exam_schedule.exam_schedule.recompute_results_for_schedule',
                args: {
                    schedule: frm.doc.name
                },
                callback: function(r) {
                    // Update progress to 100%
                    $('#recompute-progress-bar').css('width', '100%').removeClass('progress-bar-animated');
                    $('#recompute-progress-text').text('Results recomputation completed successfully!');
                    $('#recompute-progress-details').html(`
                        <div class="alert alert-success">
                            <strong>Results recomputed successfully!</strong><br>
                            All exam submissions have been processed and their results updated.
                        </div>
                    `);
                    
                    // Show close button
                    progress_dialog.$wrapper.find('.btn-primary').show();
                    
                    // Show success alert
                    frappe.show_alert({
                        message: __('Results recomputed successfully!'),
                        indicator: 'green'
                    });
                    
                    // Refresh the form to show updated data
                    frm.refresh();
                },
                error: function(r) {
                    $('#recompute-progress-bar').css('width', '100%').removeClass('progress-bar-animated').addClass('bg-danger');
                    $('#recompute-progress-text').text('Error occurred while recomputing results');
                    $('#recompute-progress-details').html(`
                        <div class="alert alert-danger">
                            <strong>Error:</strong><br>
                            ${r.message || 'An unknown error occurred while recomputing results'}
                        </div>
                    `);
                    progress_dialog.$wrapper.find('.btn-primary').show();
                },
                freeze: false // Don't freeze the UI as we have our own progress dialog
            });
            
            // Simulate progress updates (since we can't get real-time progress from server)
            let progress = 0;
            let progress_interval = setInterval(function() {
                if (progress < 90) {
                    progress += Math.random() * 10;
                    if (progress > 90) progress = 90;
                    
                    $('#recompute-progress-bar').css('width', progress + '%');
                    
                    if (progress < 30) {
                        $('#recompute-progress-text').text('Fetching submissions...');
                    } else if (progress < 60) {
                        $('#recompute-progress-text').text('Evaluating answers...');
                    } else {
                        $('#recompute-progress-text').text('Updating results...');
                    }
                } else {
                    clearInterval(progress_interval);
                }
            }, 300);
            
            // Clear interval when dialog is hidden
            progress_dialog.$wrapper.on('hidden.bs.modal', function() {
                clearInterval(progress_interval);
            });
        }
    );
}