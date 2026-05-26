from datetime import datetime, timedelta
import frappe
from frappe.utils import now

from frappe import _
from frappe.utils import sanitize_html
from frappe.utils.data import markdown
from exampro.exam_pro.api.utils import submit_candidate_pending_exams, redirect_to_exams_list

from exampro.exam_pro.doctype.exam_submission.exam_submission import \
	get_current_qs
from exampro.exam_pro.doctype.exam_schedule.exam_schedule import get_schedule_status

# ACTIVE_EXAM_CODE_CACHE = "ACTIVEEXAMCODECACHE"

def get_live_exam(member=None):
	"""
	Get upcoming/ongoing exam of a candidate.

	Check if current time is inbetween start and end time
	Function returns only one live/upcoming exam details
	even if multiple entries are there.
	"""
	exam_details = {}

	submissions = frappe.get_all(
		"Exam Submission",
		{
			"candidate": member or frappe.session.user,
			"status": ["in", ["Registered", "Started"]]
		},[
			"name",
			"exam_schedule",
			"status",
			"exam_started_time",
			"exam_submitted_time",
			"additional_time_given"
	])
	for submission in submissions:
		# Pull only the fields we actually use. Avoids loading both the full
		# Exam Schedule and Exam docs on every landing-page hit.
		sched = frappe.get_cached_value(
			"Exam Schedule",
			submission["exam_schedule"],
			[
				"exam",
				"start_date_time",
				"duration",
				"schedule_type",
				"schedule_expire_in_days",
			],
			as_dict=True,
		)
		if not sched:
			continue

		exam_cfg = frappe.get_cached_value(
			"Exam",
			sched.exam,
			["enable_calculator", "enable_video_proctoring", "enable_chat"],
			as_dict=True,
		) or {}

		# end time is schedule start time + duration + additional time given
		end_time = sched.start_date_time + timedelta(minutes=sched.duration) + \
			timedelta(minutes=submission["additional_time_given"])
		if sched.schedule_type == "Flexible":
			# For flexible schedules, end time is extended by the configured window.
			end_time += timedelta(days=sched.schedule_expire_in_days or 0)

		exam_details = {
			"exam_submission": submission["name"],
			"exam": sched.exam,
			"exam_schedule": submission["exam_schedule"],
			"start_time": sched.start_date_time,
			"end_time": "",
			"additional_time_given": submission["additional_time_given"],
			"submission_status": submission["status"],
			"duration": sched.duration,
			"enable_calculator": exam_cfg.get("enable_calculator"),
			"is_live": False,
			"enable_video_proctoring": exam_cfg.get("enable_video_proctoring"),
			"enable_chat": exam_cfg.get("enable_chat"),
			"schedule_status": get_schedule_status(submission["exam_schedule"]),
			"schedule_type": sched.schedule_type,
		}
		if submission["status"] == "Started" and sched.schedule_type == "Fixed":
			exam_details["end_time"] = end_time
		elif submission["status"] == "Started" and sched.schedule_type == "Flexible":
			# for flexible exams, exam started time + duration + additional time given
			exam_details["end_time"] = submission["exam_started_time"] + \
				timedelta(minutes=sched.duration) + \
				timedelta(minutes=submission["additional_time_given"])

		# make datetime in isoformat
		for key, val in exam_details.items():
			if type(val) == datetime:
				exam_details[key] = val.isoformat()

		# checks if current time is between schedule start and end time
		# ongoing exams can be in Not staryed, started or submitted states
		tnow = datetime.strptime(now(), '%Y-%m-%d %H:%M:%S.%f')
		if submission["status"] == "Started":
			exam_details["is_live"] = True
			return exam_details
		elif sched.start_date_time <= tnow <= end_time and submission["status"] in ["Registered", "Started"] and sched.schedule_type == "Fixed":
			exam_details["is_live"] = True
			return exam_details
		elif sched.start_date_time <= tnow <= end_time and submission["status"] in ["Registered", "Started"] and sched.schedule_type == "Flexible":
			exam_details["is_live"] = True
			return exam_details
		if sched.start_date_time <= tnow <= end_time and submission["status"] == "Submitted":
			exam_details["is_live"] = False
			return exam_details
		elif tnow <= sched.start_date_time:
			exam_details["is_live"] = False
			return exam_details
		elif tnow > end_time:
			# Time is over: flip status without loading the full doc.
			# before_save hooks (role + proctor assignment) have already run
			# at start_exam, so skipping them here is safe.
			if submission["status"] != "Submitted":
				frappe.db.set_value(
					"Exam Submission", submission["name"], "status", "Submitted"
				)
				frappe.db.commit()

			return exam_details

	return exam_details


def get_context(context):
	context.no_cache = 1

	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login"
		raise frappe.Redirect

	submit_candidate_pending_exams()

	if frappe.form_dict.get("auto_submitted"):
		submission = frappe.form_dict.get("submission")
		if not submission or not frappe.db.exists("Exam Submission", submission) \
			or frappe.db.get_value("Exam Submission", submission, "candidate") != frappe.session.user:
			redirect_to_exams_list()

		context.exam = {}
		context.alert = {
			"title": "Exam Auto-Submitted",
			"text": "Your exam time has expired and your exam has been automatically submitted.",
			"actions": [
				{
					"label": "View Result",
					"icon": "bi-file-earmark-text",
					"href": "/exam/{}".format(submission),
					"primary": True,
				},
				{
					"label": "My Exams",
					"icon": "bi-list-ul",
					"href": "/my-exams",
					"primary": False,
				},
			],
		}
		return

	exam_details = get_live_exam(frappe.session.user)
	context.page_context = {}

	if not exam_details:
		context.exam = {}
		context.alert = {
			"title": "No exams scheduled.",
			"text": "You do not have any live or upcoming exams."
		}

	elif exam_details["schedule_status"] == "Upcoming":
		context.exam = {}
		context.alert = {
			"title": "You have an upcoming exam.",
			"text": "{} exam starts at {}".format(
				exam_details["exam"],
				exam_details["start_time"]
		)}
	
	elif exam_details["is_live"]:
		context.alert = {}
		exam = frappe.db.get_value(
			"Exam", exam_details["exam"], ["name","title", "instructions"], as_dict=True
		)
		for key, value in exam_details.items():
			exam[key] = value

		# markdown() does not strip embedded raw HTML/JS, so sanitize the result
		# before it is rendered with the | safe filter in the template.
		instructions = sanitize_html(markdown(exam["instructions"]))
		if instructions.strip() == "<p></p>" or instructions.strip() == "":
			instructions = ""
		exam["instructions"] = instructions if instructions else ""
		exam["current_qs"] = 1
		# return the last question requested in this exam, if applicable
		if exam["submission_status"] == "Started":
			_, current_qs_no = get_current_qs(exam_details["exam_submission"]) 
			exam["current_qs"] = current_qs_no or 1
		context.exam = exam

		context.metatags = {
			"title": exam.title,
			"image": exam.image,
			"description": exam.description,
			"keywords": exam.title,
			"og:type": "website",
		}
	elif not exam_details["is_live"]:
		context.exam = {}
		context.alert = {
			"title": "No exams scheduled.",
			"text": "You do not have any live or upcoming exams."
		}

