import frappe
from frappe import _


def get_context(context):
	if frappe.session.user == "Guest":
		raise frappe.PermissionError(_("Please login to access this page."))

	roles = frappe.get_roles()
	is_manager = "Exam Manager" in roles
	is_proctor = "Exam Proctor" in roles

	if not is_manager and not is_proctor:
		raise frappe.PermissionError(_("You are not authorized to access this page."))

	exam_schedule = frappe.form_dict.get("exam_schedule")
	if not exam_schedule:
		frappe.throw(_("Exam schedule is required."))

	sched = frappe.get_doc("Exam Schedule", exam_schedule)
	if sched.get_status() != "Completed":
		frappe.throw(_("Archive is only available for completed schedules."))

	filters = {
		"exam_schedule": exam_schedule,
		"status": ["in", ["Submitted", "Terminated", "Not Attempted"]],
	}
	if not is_manager:
		filters["assigned_proctor"] = frappe.session.user

	submissions = frappe.get_all(
		"Exam Submission",
		filters=filters,
		fields=[
			"name", "candidate_name", "status", "exam",
			"attention_score", "exam_started_time", "exam_submitted_time",
			"assigned_proctor",
		],
		order_by="candidate_name asc",
	)

	for sub in submissions:
		exam_doc = frappe.get_cached_doc("Exam", sub["exam"])
		sub["enable_video_proctoring"] = exam_doc.get("enable_video_proctoring", 0)
		sub["enable_chat"] = exam_doc.get("enable_chat", 0)
		sub["warning_message_count"] = frappe.db.count(
			"Exam Messages",
			{"exam_submission": sub["name"], "type_of_message": ["in", ["Warning", "Critical"]]}
		)
		if sub.get("exam_started_time"):
			sub["exam_started_time"] = str(sub["exam_started_time"])
		if sub.get("exam_submitted_time"):
			sub["exam_submitted_time"] = str(sub["exam_submitted_time"])

	latest_messages = []
	for sub in submissions:
		latest_msg = frappe.get_all(
			"Exam Messages",
			filters={"exam_submission": sub["name"]},
			fields=["message"],
			order_by="creation desc",
			limit=1,
		)
		latest_messages.append({
			"exam_submission": sub["name"],
			"candidate_name": sub["candidate_name"],
			"message": latest_msg[0].message if latest_msg else "No messages",
			"status": sub["status"],
			"enable_video_proctoring": sub.get("enable_video_proctoring", 0),
			"enable_chat": sub.get("enable_chat", 0),
			"warning_message_count": sub.get("warning_message_count", 0),
		})

	exam_title = frappe.db.get_value("Exam", sched.exam, "title")

	context.no_cache = 1
	context.submissions = submissions
	context.latest_messages = latest_messages
	context.exam_schedule = exam_schedule
	context.exam_title = exam_title or ""
	context.schedule_date = str(sched.start_date_time)
	context.schedule_duration = sched.duration
	context.is_manager = is_manager
