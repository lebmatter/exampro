// Copyright (c) 2024, Labeeb Mattra and contributors
// For license information, please see license.txt

frappe.listview_settings['Exam Schedule'] = {
    add_fields: ["start_date_time", "duration", "schedule_type", "schedule_expire_in_days"],
    
    onload: function(listview) {
        listview.page.add_inner_button(__("Refresh Status"), function() {
            listview.refresh();
        });
        show_ongoing_banner(listview);
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
    
    before_render: function(doc) {
        if (!doc) return;
        doc._needs_status_calculation = true;
        doc._server_status = null;
    }
};

function show_ongoing_banner(listview) {
    frappe.call({
        method: "exampro.exam_pro.doctype.exam_schedule.exam_schedule.get_ongoing_schedules",
        callback: function(r) {
            $(".ongoing-exam-banner").remove();
            let names = (r.message || []);
            if (!names.length) return;

            let $banner = $(`
                <div class="ongoing-exam-banner" style="
                    padding: 10px 15px;
                    margin-bottom: 10px;
                    background: var(--alert-bg-green, #d1e7dd);
                    border-radius: var(--border-radius-md, 6px);
                    display: flex;
                    align-items: center;
                    gap: 8px;
                ">
                    <span style="font-weight:600;">${names.length} ongoing exam${names.length > 1 ? "s" : ""}</span>
                    <a class="btn btn-xs btn-success ongoing-view-btn">View</a>
                </div>
            `);

            $banner.find(".ongoing-view-btn").on("click", function() {
                listview.filter_area.clear();
                listview.filter_area.add([[listview.doctype, "name", "in", names.join(", ")]]);
                listview.refresh();
            });

            listview.$result.closest(".layout-main-section").prepend($banner);
        }
    });
}
