import frappe
from frappe import _


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login"
		raise frappe.Redirect

	if "Exam Manager" not in frappe.get_roles():
		raise frappe.PermissionError(_("You are not authorized to access this page"))

	context.no_cache = 1

	context.categories = frappe.db.sql(
		"""
		SELECT c.name, c.title,
		       (SELECT COUNT(*) FROM `tabExam Question` q WHERE q.category = c.name) AS question_count
		FROM `tabExam Question Category` c
		ORDER BY c.modified DESC
		LIMIT 10
		""",
		as_dict=True,
	)

	settings = frappe.get_single("Exam Settings")
	context.ai_configured = bool(settings.openrouter_api_key)
	context.default_model = settings.default_text_model

	context.exams = frappe.db.sql(
		"""
		SELECT DISTINCT e.name, e.title, e.exam_mode, e.duration,
			   e.question_type, e.total_questions, e.total_marks,
			   e.certificate_template, e.enable_payment, e.price
		FROM `tabExam` e
		LEFT JOIN `tabExam Schedule` s ON s.exam = e.name
		ORDER BY COALESCE(s.start_date_time, e.modified) DESC
		LIMIT 10
		""",
		as_dict=True,
	)

	context.batches = frappe.get_all(
		"Exam Batch",
		fields=["name"],
		order_by="name",
	)

	context.certificate_templates = frappe.get_all(
		"Exam Certificate Template",
		fields=["name", "title"],
		order_by="title",
	)

	context.partners = frappe.get_all(
		"Exam Partner",
		filters={"is_active": 1},
		fields=["name", "partner_name"],
		order_by="partner_name",
	)
