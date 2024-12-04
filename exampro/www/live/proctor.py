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

		schedule_start_dt, sched_duration = frappe.db.get_value(
			"Exam Schedule", submission["exam_schedule"], ["start_date_time", "duration"]
		)

		# end time is schedule start time + duration + additional time given
		end_time = schedule_start_dt + timedelta(minutes=sched_duration) + \
			timedelta(minutes=submission["additional_time_given"])

		# checks if current time is between schedule start and end time
		# ongoing exams can be in Not staryed, started or submitted states
		tnow = datetime.strptime(now(), '%Y-%m-%d %H:%M:%S.%f')
		if schedule_start_dt <= tnow <= end_time:
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

def get_context(context):
	"""
	Get the active exams the logged-in user proctoring
	"""
	context.no_cache = 1

	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login"
		raise frappe.Redirect

	context.page_context = {}
	proctor_list = get_proctor_live_exams()

	context.submissions = proctor_list["live_submissions"]
	context.pending_candidates = proctor_list["pending_candidates"]
	context.video_chunk_length = frappe.db.get_single_value(
		"Exam Settings", "video_chunk_length"
	)

