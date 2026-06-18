import frappe
from frappe import _


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login"
		raise frappe.Redirect

	if "Exam Manager" not in frappe.get_roles():
		raise frappe.PermissionError(_("You are not authorized to access this page"))

	context.no_cache = 1

	context.categories = frappe.get_all(
		"Exam Question Category",
		fields=["name", "title"],
		order_by="title",
	)

	settings = frappe.get_single("Exam Settings")
	context.ai_configured = bool(settings.openrouter_api_key)
	context.default_model = settings.default_text_model

	context.exams = frappe.db.sql(
		"""
		SELECT DISTINCT e.name, e.title, e.exam_mode, e.duration,
			   e.question_type, e.total_questions, e.total_marks
		FROM `tabExam` e
		INNER JOIN `tabExam Schedule` s ON s.exam = e.name
		ORDER BY s.start_date_time DESC
		LIMIT 10
		""",
		as_dict=True,
	)

	context.batches = frappe.get_all(
		"Exam Batch",
		fields=["name"],
		order_by="name",
	)
