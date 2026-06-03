from datetime import datetime, timedelta
import frappe
from frappe.utils import format_datetime
from exampro.exam_pro.api.utils import submit_candidate_pending_exams, can_show_exam_results_for_leaderboard


PAST_STATUSES = ("Submitted", "Terminated")


def get_past_exams(member=None, page=1, page_size=10):
	"""Return paginated past exams for the logged-in candidate.

	An exam is considered past when the submission is finished (Submitted /
	Terminated) or when the schedule window has closed even if the candidate
	never started (auto-submitted entries are handled by
	submit_candidate_pending_exams beforehand).
	"""
	res = []
	submissions = frappe.get_all(
		"Exam Submission",
		{"candidate": member or frappe.session.user},
		[
			"name",
			"exam_schedule",
			"status",
			"exam_started_time",
			"exam_submitted_time",
			"additional_time_given",
			"result_status",
		],
		ignore_permissions=True,
	)

	for sub in submissions:
		schedule = frappe.get_doc("Exam Schedule", sub["exam_schedule"], ignore_permissions=True)
		exam = frappe.get_doc("Exam", schedule.exam, ignore_permissions=True)
		sched_status = schedule.get_status()

		is_past = sub["status"] in PAST_STATUSES or sched_status == "Completed"
		if not is_past:
			continue

		certificate_exists = frappe.db.exists(
			"Exam Certificate", {"exam_submission": sub["name"]}
		)
		exam.leaderboard = exam.leaderboard or "No Leaderboard"
		submission_doc = frappe.get_doc("Exam Submission", sub["name"])
		leaderboard_can_show = can_show_exam_results_for_leaderboard(exam, submission_doc)

		res.append({
			"submission": sub["name"],
			"exam_title": exam.title,
			"start_time": schedule.start_date_time,
			"schedule_time": format_datetime(schedule.start_date_time, "dd MMM YYYY, HH:mm"),
			"duration": f"{schedule.duration} min",
			"schedule_type": schedule.schedule_type,
			"status": sub["status"],
			"result_status": sub["result_status"],
			"can_show_results": leaderboard_can_show,
			"leaderboard_enabled": exam.leaderboard != "No Leaderboard" and leaderboard_can_show,
			"certification_enabled": exam.enable_certification,
			"certificate_exists": certificate_exists,
			"certificate_name": certificate_exists if certificate_exists else None,
		})

	res.sort(key=lambda x: x["start_time"] or datetime.min, reverse=True)

	total = len(res)
	total_pages = (total + page_size - 1) // page_size
	start = (page - 1) * page_size
	end = min(start + page_size, total)

	return {
		"exams": res[start:end],
		"pagination": {
			"total": total,
			"page": page,
			"page_size": page_size,
			"total_pages": total_pages,
			"has_prev": page > 1,
			"has_next": page < total_pages,
		},
	}


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login"
		raise frappe.Redirect

	submit_candidate_pending_exams()
	context.no_cache = 1

	page = int(frappe.form_dict.get("page", 1))
	page_size = 10
	data = get_past_exams(page=page, page_size=page_size)
	context.exams = data["exams"]
	context.pagination = data["pagination"]

	context.metatags = {
		"title": "My Exams",
		"description": "Your past exam attempts",
	}


@frappe.whitelist()
def download_certificate(certificate_name):
	"""Download certificate PDF"""
	cert_doc = frappe.get_doc("Exam Certificate", certificate_name)
	if cert_doc.candidate != frappe.session.user:
		frappe.throw("You don't have permission to download this certificate")

	try:
		pdf_bytes = cert_doc.generate_pdf()
		import base64
		return base64.b64encode(pdf_bytes).decode("utf-8")
	except Exception as e:
		frappe.throw(f"Error generating certificate PDF: {str(e)}")
