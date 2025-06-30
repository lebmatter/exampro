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
    }
});