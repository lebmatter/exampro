import frappe

def redirect_to_exams_list():
	frappe.local.flags.redirect_location = "/my-exams"
	raise frappe.Redirect