// Copyright (c) 2024, Labeeb Mattra and contributors
// For license information, please see license.txt

frappe.query_reports["Exam Schedule Status"] = {
	"filters": [
		{
			"fieldname": "exam",
			"label": __("Exam"),
			"fieldtype": "Link",
			"options": "Exam"
		},
		{
			"fieldname": "status",
			"label": __("Status"),
			"fieldtype": "Select",
			"options": "\nUpcoming\nOngoing\nCompleted"
		},
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_days(frappe.datetime.get_today(), -30)
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_days(frappe.datetime.get_today(), 30)
		}
	],
	"formatter": function(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		
		if (column.fieldname == "status") {
			if (data.status === "Upcoming") {
				value = `<span class="indicator-pill blue">${data.status}</span>`;
			} else if (data.status === "Ongoing") {
				value = `<span class="indicator-pill green">${data.status}</span>`;
			} else if (data.status === "Completed") {
				value = `<span class="indicator-pill gray">${data.status}</span>`;
			}
		}
		
		return value;
	}
};
