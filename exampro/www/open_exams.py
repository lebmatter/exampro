import frappe
from frappe.utils import format_datetime, strip_html


def _short_desc(html, length=160):
	if not html:
		return ""
	text = strip_html(html).strip()
	if len(text) > length:
		text = text[: length - 1].rstrip() + "…"
	return text


def get_context(context):
	context.no_cache = 1
	context.is_logged_in = frappe.session.user != "Guest"

	schedules = frappe.get_all(
		"Exam Schedule",
		fields=[
			"name", "exam", "start_date_time", "schedule_type",
			"duration", "schedule_expire_in_days", "badge", "short_uuid",
		],
		ignore_permissions=True,
	)

	exams_map = {}
	skipped_exams = set()
	for sched in schedules:
		exam_name = sched.exam

		if exam_name in skipped_exams:
			continue

		if exam_name not in exams_map:
			exam_doc = frappe.get_doc("Exam", exam_name, ignore_permissions=True)
			if not exam_doc.is_public:
				skipped_exams.add(exam_name)
				continue
			exams_map[exam_name] = {
				"name": exam_doc.name,
				"title": exam_doc.title,
				"description": _short_desc(exam_doc.description),
				"duration": exam_doc.duration,
				"question_type": exam_doc.question_type,
				"image": exam_doc.image,
				"enable_payment": exam_doc.enable_payment,
				"price": exam_doc.price,
				"schedules": [],
			}

		schedule_doc = frappe.get_doc("Exam Schedule", sched.name, ignore_permissions=True)
		status = schedule_doc.get_status()
		if status != "Upcoming":
			continue

		exams_map[exam_name]["schedules"].append({
			"name": sched.name,
			"short_uuid": sched.short_uuid,
			"start_date_time": format_datetime(sched.start_date_time, "dd MMM YYYY, HH:mm"),
			"schedule_type": sched.schedule_type,
			"duration": sched.duration,
			"badge": sched.badge or "Exam",
		})

	context.exams = [e for e in exams_map.values() if e["schedules"]]
	context.metatags = {
		"title": "Public Exams",
		"description": "Browse and register for upcoming public exams.",
	}
