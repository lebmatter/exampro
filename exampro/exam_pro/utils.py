import frappe

def redirect_to_exams_list():
	frappe.local.flags.redirect_location = "/my-exams"
	raise frappe.Redirect

def get_website_context(context):
	user_roles = frappe.get_roles(frappe.session.user)
	top_bar_items = []
	if "Exam Proctor" in user_roles:
		top_bar_items.append({"label": "Proctor Exam", "url": "/proctor"})
	if "Exam Evaluator" in user_roles:
		top_bar_items.append({"label": "Evaluate Exam", "url": "/evaluate"})
	context.top_bar_items = top_bar_items

	return context