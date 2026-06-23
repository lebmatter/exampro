import frappe
from frappe import _
from frappe.utils import format_datetime

from exampro.exam_pro.doctype.exam_schedule.exam_schedule import get_schedule_status


def get_context(context):
	schedule_id = frappe.form_dict.get("schedule_id")
	if not schedule_id:
		frappe.throw(_("No schedule specified."), frappe.ValidationError)

	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = f"/login?redirect-to=/exams/register/{schedule_id}"
		raise frappe.Redirect

	context.no_cache = 1

	schedule_name = frappe.db.get_value(
		"Exam Schedule", {"short_uuid": schedule_id}, "name"
	)
	if not schedule_name:
		context.valid = False
		context.message = _("Invalid schedule link.")
		return context

	schedule = frappe.get_doc("Exam Schedule", schedule_name)
	exam = frappe.get_doc("Exam", schedule.exam)

	if not exam.is_public:
		context.valid = False
		context.message = _("This exam is not available for public registration.")
		return context

	status = get_schedule_status(schedule_name)
	if status == "Completed":
		context.valid = False
		context.message = _("This exam schedule has already been completed.")
		return context

	existing = frappe.db.exists("Exam Submission", {
		"exam_schedule": schedule_name,
		"candidate": frappe.session.user,
		"status": ["not in", ["Registration Cancelled", "Aborted"]],
	})

	context.valid = True
	context.exam = exam
	context.exam_schedule = schedule
	context.schedule_name = schedule_name
	context.schedule_status = status
	context.has_submission = bool(existing)
	context.is_paid = bool(exam.enable_payment)
	context.price = exam.price or 0
	context.start_time_display = format_datetime(
		schedule.start_date_time, "dd MMM YYYY, HH:mm"
	)

	context.metatags = {
		"title": f"Register — {exam.title}",
		"description": f"Register for {exam.title}",
	}
