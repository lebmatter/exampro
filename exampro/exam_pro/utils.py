import frappe

def redirect_to_exams_list():
	frappe.local.flags.redirect_location = "/exams"
	raise frappe.Redirect