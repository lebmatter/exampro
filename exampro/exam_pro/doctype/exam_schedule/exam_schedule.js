// Copyright (c) 2024, Labeeb Mattra and contributors
// For license information, please see license.txt

frappe.ui.form.on('Exam Schedule', {
    refresh: function(frm) {
        frm.add_custom_button(__('End Schedule'), function() {
            frappe.call({
                method: 'exampro.exam_pro.doctype.exam_schedule.exam_schedule.end_schedule',
                args: {
                    docname: frm.doc.name
                },
                callback: function(response) {
                    if(response.message == "Success") {
                        frappe.msgprint(__('Exam schedule is ended!'));
                        frm.reload_doc();
                    }
                }
            });
        });
    }
});