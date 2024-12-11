from datetime import datetime, timedelta
import frappe
from frappe.utils import now
from frappe import _
from exampro.exam_pro.utils import (
	check_profile_restriction,
	get_restriction_details
)

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
		{"candidate": member or frappe.session.user},[
			"name",
			"exam_schedule",
			"status",
			"exam_started_time",
			"exam_submitted_time",
			"additional_time_given"
   ])
	for submission in submissions:
		if submission["status"] in ["Registration Cancelled", "Aborted"]:
			continue

		schedule = frappe.get_doc("Exam Schedule", submission["exam_schedule"])
		exam = frappe.get_doc("Exam", schedule.exam)

		# end time is schedule start time + duration + additional time given
		end_time = schedule.start_date_time + timedelta(minutes=schedule.duration) + \
			timedelta(minutes=submission["additional_time_given"])

		exam_details = {
			"exam_submission": submission["name"],
			"exam": schedule.exam,
			"exam_schedule": submission["exam_schedule"],
			"start_time": schedule.start_date_time,
			"end_time": end_time,
			"additional_time_given": submission["additional_time_given"],
			"submission_status": submission["status"],
			"duration": schedule.duration,
			"enable_calculator": exam.enable_calculator,
			"live_status": "",
			"submission_status": submission["status"],
			"enable_video_proctoring": exam.enable_video_proctoring,
			"enable_chat": exam.enable_chat,
			"enable_calculator": exam.enable_calculator
		}

		# make datetime in isoformat
		for key,val in exam_details.items():
			if type(val) == datetime:
				exam_details[key] = val.isoformat()

		# checks if current time is between schedule start and end time
		# ongoing exams can be in Not staryed, started or submitted states
		tnow = datetime.strptime(now(), '%Y-%m-%d %H:%M:%S.%f')
		if schedule.start_date_time <= tnow <= end_time:
			exam_details["live_status"] = "Live"
			return exam_details
		elif tnow <= schedule.start_date_time:
			exam_details["live_status"] = "Upcoming"
			return exam_details
		elif tnow > end_time:
			# if time is over, submit if applicable
			if submission["status"] != "Submitted":
				doc = frappe.get_doc("Exam Submission", submission["name"])
				doc.status == "Submitted"
				doc.save(ignore_permissions=True)

			return {}

	return exam_details



def get_exam_registation(candidate=None):
	"""Returns all exam registrations of the user."""

	filters = {"candidate": candidate or frappe.session.user}
	return frappe.get_all("Exam Submission", filters, ["name", "exam", "status"])


def get_registered_exams():
	in_progress = []
	completed = []
	memberships = get_exam_registation(None)

	for membership in memberships:
		exam = frappe.db.get_value(
			"Exam",
			membership.exam,
			[
				"name",
				"upcoming",
				"title",
				"image",
				"enable_certification",
				"paid_certificate",
				"price_certificate",
				"currency",
				"published",
			],
			as_dict=True,
		)
		if not exam.published:
			continue
		progress = membership.status
		if progress == "Submitted":
			completed.append(exam)
		else:
			in_progress.append(exam)

	return {"in_progress": in_progress, "completed": completed}

def get_context(context):
	"""
	Check if there is any live exams for the user,
	If so redirect to it. Else show exam list
	"""
	if frappe.session.user != "Guest":
		exam_details = get_live_exam(frappe.session.user)
		if exam_details:
			frappe.local.flags.redirect_location = "/live/exam"
			raise frappe.Redirect
	

	context.no_cache = 1
	context.live_exams, context.upcoming_exams = get_exams()
	context.enrolled_exams = (
		get_registered_exams()["in_progress"] + get_registered_exams()["completed"]
	)
	context.created_exams = []

	context.metatags = {
		"title": _("Exam List"),
		"image": frappe.db.get_single_value("Website Settings", "banner_image"),
		"description": "This page lists all the exams published on our website",
		"keywords": "All Exams, Exams, Learn",
	}


def get_exams():
	exams = frappe.get_all(
		"Exam",
		filters={"published": True},
		fields=[
			"name",
			"upcoming",
			"title",
			"image",
			"enable_certification",
			"paid_certificate",
			"price_certificate",
			"currency",
		],
	)

	live_exams, upcoming_exams = [], []
	for exam in exams:
		if exam.upcoming:
			upcoming_exams.append(exam)
		else:
			live_exams.append(exam)
	return live_exams, upcoming_exams
