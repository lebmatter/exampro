import frappe
from frappe import _


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login"
		raise frappe.Redirect

	roles = frappe.get_roles()
	if "Exam Manager" not in roles and "Exam Partner" not in roles:
		frappe.local.flags.redirect_location = "/dashboard"
		raise frappe.Redirect

	context.no_cache = 1

	exam_name = frappe.form_dict.get("exam", "")
	schedule_name = frappe.form_dict.get("schedule", "")

	context.exam_name = exam_name
	context.schedule_name = schedule_name

	if exam_name:
		exam = frappe.db.get_value(
			"Exam", exam_name, ["title", "total_marks", "pass_percentage"], as_dict=True
		)
		context.exam_title = exam.title if exam else ""
		context.exam_total_marks = flt(exam.total_marks) if exam else 0
		context.exam_found = bool(exam)
	else:
		context.exam_title = ""
		context.exam_total_marks = 0
		context.exam_found = False

	if schedule_name:
		context.schedule_label = schedule_name
	else:
		context.schedule_label = ""


def flt(val):
	try:
		return float(val or 0)
	except (TypeError, ValueError):
		return 0.0
