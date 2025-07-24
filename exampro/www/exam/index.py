from datetime import datetime, timedelta
import frappe
from frappe.utils import now

from frappe import _
from frappe.utils.data import markdown
from exampro.exam_pro.api.utils import submit_candidate_pending_exams

from exampro.exam_pro.doctype.exam_submission.exam_submission import \
	get_current_qs

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
		schedule = frappe.get_doc("Exam Schedule", submission["exam_schedule"])
		exam = frappe.get_doc("Exam", schedule.exam)

		# end time is schedule start time + duration + additional time given
		end_time = schedule.start_date_time + timedelta(minutes=schedule.duration) + \
			timedelta(minutes=submission["additional_time_given"])
		if schedule.schedule_type == "Flexible":
			# For flexible schedules, we consider the end time as start time + duration + 5 min buffer
			end_time += timedelta(days=schedule.schedule_expire_in_days)

		exam_details = {
			"exam_submission": submission["name"],
			"exam": schedule.exam,
			"exam_schedule": submission["exam_schedule"],
			"start_time": schedule.start_date_time,
			"end_time": "",
			"additional_time_given": submission["additional_time_given"],
			"submission_status": submission["status"],
			"duration": schedule.duration,
			"enable_calculator": exam.enable_calculator,
			"is_live": False,
			"enable_video_proctoring": exam.enable_video_proctoring,
			"enable_chat": exam.enable_chat,
			"schedule_status": schedule.get_status(),
			"schedule_type": schedule.schedule_type,
		}
		if submission["status"] == "Started" and schedule.schedule_type == "Fixed":
			exam_details["end_time"] = end_time
		elif submission["status"] == "Started" and schedule.schedule_type == "Flexible":
			# for flexible exams, exam started time + duration + additional time given
			exam_details["end_time"] = submission["exam_started_time"] + \
				timedelta(minutes=schedule.duration) + \
				timedelta(minutes=submission["additional_time_given"])

		# make datetime in isoformat
		for key,val in exam_details.items():
			if type(val) == datetime:
				exam_details[key] = val.isoformat()

		# checks if current time is between schedule start and end time
		# ongoing exams can be in Not staryed, started or submitted states
		tnow = datetime.strptime(now(), '%Y-%m-%d %H:%M:%S.%f')
		if submission["status"] == "Started":
			exam_details["is_live"] = True
			return exam_details
		elif schedule.start_date_time <= tnow <= end_time and submission["status"] in ["Registered", "Started"] and schedule.schedule_type == "Fixed":
			exam_details["is_live"] = True
			return exam_details
		elif schedule.start_date_time <= tnow <= end_time and submission["status"] in ["Registered", "Started"] and schedule.schedule_type == "Flexible":
			exam_details["is_live"] = True
			return exam_details
		if schedule.start_date_time <= tnow <= end_time and submission["status"] == "Submitted":
			exam_details["is_live"] = False
			return exam_details
		elif tnow <= schedule.start_date_time:
			exam_details["is_live"] = False
			return exam_details
		elif tnow > end_time:
			# if time is over, submit if applicable
			if submission["status"] != "Submitted":
				doc = frappe.get_doc("Exam Submission", submission["name"])
				doc.status == "Submitted"
				doc.save(ignore_permissions=True)

			return exam_details

	return exam_details


def get_context(context):
	context.no_cache = 1

	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login"
		raise frappe.Redirect

	submit_candidate_pending_exams()
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

		instructions = markdown(exam["instructions"])
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

