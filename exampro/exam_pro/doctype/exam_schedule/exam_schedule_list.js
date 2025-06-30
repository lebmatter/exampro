// Copyright (c) 2024, Labeeb Mattra and contributors
// For license information, please see license.txt

frappe.listview_settings['Exam Schedule'] = {
    add_fields: ["start_date_time", "duration", "schedule_type", "schedule_expire_in_days"],
    
    onload: function(listview) {
        // Add a custom field for status
        listview.page.add_inner_button(__("Refresh Status"), function() {
            listview.refresh();
        });
    },
    
    get_indicator: function(doc) {
        // Guard against undefined doc
        if (!doc) {
            console.error("get_indicator called with undefined doc");
            return ["Unknown", "gray"];
        }
        
        // Immediately query the server for each row's status
        // We need to do this synchronously, since get_indicator must return immediately
        if (!doc._fetching_status && !doc._server_status) {
            doc._fetching_status = true;
            
            // Use a direct server call to get the status
            try {
                var xhr = new XMLHttpRequest();
                xhr.open('POST', '/api/method/exampro.exam_pro.doctype.exam_schedule.exam_schedule.get_server_status', false); // false = synchronous
                xhr.setRequestHeader('Content-Type', 'application/json');
                xhr.setRequestHeader('X-Frappe-CSRF-Token', frappe.csrf_token);
                
                xhr.send(JSON.stringify({ 
                    schedule_name: doc.name 
                }));
                
                if (xhr.status === 200) {
                    var response = JSON.parse(xhr.responseText);
                    if (response.message) {
                        doc._server_status = response.message;
                    }
                }
            } catch (e) {
                console.error("Error fetching status synchronously:", e);
            }
            
            doc._fetching_status = false;
        }
        
        // If we have server status, use it
        if (doc._server_status) {
            return [doc._server_status, doc._server_status === "Upcoming" ? "blue" : 
                   doc._server_status === "Ongoing" ? "green" : "gray"];
        }
        
        // Fallback - This should rarely happen now
        return ["Calculating...", "orange"];
    },
    
    // Add the status as a formatted column
    formatters: {
        start_date_time: function(value, df, doc) {
            if (!value) return '';
            try {
                return frappe.datetime.str_to_user(value);
            } catch (e) {
                console.error("Error formatting date:", e);
                return value || '';
            }
        }
    },
    
    // Before render, prepare for status calculation
    before_render: function(doc) {
        // Guard against undefined doc
        if (!doc) {
            console.error("before_render called with undefined doc");
            return;
        }

        // Mark that this doc needs status calculation
        doc._needs_status_calculation = true;
        doc._server_status = null;
    }
};
