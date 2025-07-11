from datetime import datetime, timedelta
from frappe.utils import now

import frappe
from frappe import _

def get_proctor_live_exams(proctor=None):
	"""
	Get upcoming/ongoing exam of a proctor.

	Check if current time is inbetween start and end time
	Function returns only one live/upcoming exam details
	even if multiple entries are there.
	"""
	tracker = "{}:tracker"
	res = {"live_submissions":[], "pending_candidates": []}

	submissions = frappe.get_all(
		"Exam Submission",
		{"assigned_proctor": proctor or frappe.session.user},[
			"name",
			"candidate_name",
			"exam_schedule",
			"status",
			"exam_started_time",
			"exam_submitted_time",
			"additional_time_given"
	])
	for submission in submissions:
		if submission["status"] in ["Registration Cancelled", "Aborted"]:
			continue

		sched = frappe.get_doc("Exam Schedule", submission["exam_schedule"])
		if sched.get_status(additional_time=submission["additional_time_given"]) == "Completed":
			continue

		# end time is schedule start time + duration + additional time given
		end_time = sched.start_date_time + timedelta(minutes=sched.duration) + \
			timedelta(minutes=submission["additional_time_given"])

		# checks if current time is between schedule start and end time
		# ongoing exams can be in Not staryed, started or submitted states
		tnow = datetime.strptime(now(), '%Y-%m-%d %H:%M:%S.%f')
		if sched.start_date_time <= tnow <= end_time:
			userdata = {
				"name": submission["name"],
				"candidate_name": submission["candidate_name"],
				"status": submission["status"]
			}
			if frappe.cache().get(tracker.format(submission["name"])):
				# if tracker exists, candidate started the exam
				res["live_submissions"].append(userdata)
			else:
				res["pending_candidates"].append(userdata)

	return res

@frappe.whitelist()
def get_latest_messages(proctor=None):
	"""Get latest messages from all candidates being proctored by the current proctor"""
	result = []
	sub = get_proctor_live_exams(proctor)["live_submissions"]
	if not sub:
		return result
	
	for submission in sub:
		latest_msg = frappe.get_all(
			"Exam Messages",
			filters={"exam_submission": submission["name"]},
			fields=["message", "creation", "from"],
			order_by="creation desc",
			limit=1
		)

		msg_text = "Exam not started"
		if submission["status"] == "Started":
			msg_text = "Exam started"
		elif submission["status"] == "Terminated":
			msg_text = "Exam terminated"
		if latest_msg:
			msg_text = latest_msg[0].message

		result.append({
			"exam_submission": submission["name"],
			"candidate_name": submission["candidate_name"],
			"message": msg_text,
			"status": submission["status"]
		})

	return result

def get_context(context):
	"""
	Get the active exams the logged-in user proctoring
	"""
	if frappe.session.user == "Guest":
		raise frappe.PermissionError(_("Please login to access this page."))
	
	if "Exam Proctor" not in frappe.get_roles():
		raise frappe.PermissionError("You are not authorized to access this page")

	context.no_cache = 1

	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login"
		raise frappe.Redirect

	context.page_context = {}
	proctor_list = get_proctor_live_exams()

	context.submissions = proctor_list["live_submissions"]
	context.pending_candidates = proctor_list["pending_candidates"]
	context.latest_messages = get_latest_messages()

