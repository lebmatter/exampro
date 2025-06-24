from datetime import datetime, timedelta
import frappe
from frappe.utils import now, format_datetime
from frappe import _

def get_user_exams(member=None):
	"""
	Get upcoming/ongoing exam of a candidate.
	"""
	res = []

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
			"end_time": end_time,
			"additional_time_given": submission["additional_time_given"],
			"submission_status": submission["status"],
			"duration": schedule.duration,
			"enable_calculator": exam.enable_calculator,
			"schedule_status": "Upcoming",
			"schedule_type": schedule.schedule_type,
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
		if schedule.start_date_time <= tnow <= end_time and schedule.schedule_type == "Fixed":
			frappe.local.flags.redirect_location = "/exam"
			raise frappe.Redirect
		if schedule.start_date_time <= tnow <= end_time and schedule.schedule_type == "Flexible":
			exam_details["schedule_status"] = "Ongoing. Finish before " + format_datetime(end_time, "dd MMM, HH:mm")
		elif tnow <= schedule.start_date_time and schedule.schedule_type == "Fixed":
			exam_details["schedule_status"] = "Upcoming"
		elif tnow > end_time:
			exam_details["schedule_status"] = "Ended"
			# if time is over, submit if applicable
			if submission["status"] != "Submitted":
				doc = frappe.get_doc("Exam Submission", submission["name"])
				doc.status = "Submitted"
				doc.save(ignore_permissions=True)

	# Sort exams by schedule time
	res.sort(key=lambda x: x["start_time"], reverse=True)

	return res


def get_context(context):
	"""
	Check if there is any started exam for the user,
	If so redirect to it. Otherwise show exam list with upcoming exam banner.
	"""
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login"
		raise frappe.Redirect

	context.no_cache = 1
	context.exams = get_user_exams()
	
	context.metatags = {
		"title": _("My Exams"),
		"description": "View your upcoming and past exams"
	}
