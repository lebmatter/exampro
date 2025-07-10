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
            
        // Handle Generate Invite Link button
        frm.add_custom_button(__('Generate Invite Link'), function() {
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
        });
    }
});