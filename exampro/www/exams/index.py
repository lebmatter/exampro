from datetime import datetime, timedelta
import frappe
from frappe.utils import now, format_datetime
from frappe import _

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

def get_user_exams(user=None):
    """Get all exams (upcoming and past) for a user with relevant details"""
    user = user or frappe.session.user
    
    # Get all submissions for the user
    submissions = frappe.get_all(
        "Exam Submission",
        filters={"candidate": user},
        fields=[
            "name",
            "exam_schedule",
            "exam",
            "status",
            "total_marks",
            "result_status",
            "exam_started_time",
            "exam_submitted_time",
        ]
    )
    
    exams = []
    next_exam = None
    current_time = datetime.strptime(now(), '%Y-%m-%d %H:%M:%S.%f')
    
    for submission in submissions:
        schedule = frappe.get_doc("Exam Schedule", submission.exam_schedule)
        exam = frappe.get_doc("Exam", schedule.exam)
        
        exam_data = {
            "exam_name": exam.title,
            "schedule_time": format_datetime(schedule.start_date_time),
            "duration": schedule.duration,
            "status": "Upcoming" if schedule.start_date_time > current_time else submission.status,
            "score": submission.total_marks if submission.status == "Submitted" else None,
            "schedule_datetime": schedule.start_date_time,
            "submission": submission.name
        }
        
        # Find the next upcoming exam
        if schedule.start_date_time > current_time:
            if not next_exam or schedule.start_date_time < next_exam["schedule_datetime"]:
                next_exam = exam_data
        
        exams.append(exam_data)
    
    # Sort exams by schedule time
    exams.sort(key=lambda x: x["schedule_datetime"], reverse=True)
    
    return exams, next_exam

def get_context(context):
	"""
	Check if there is any started exam for the user,
	If so redirect to it. Otherwise show exam list with upcoming exam banner.
	"""
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login"
		raise frappe.Redirect

	# Get live exam details
	exam_details = get_live_exam(frappe.session.user)
	
	# Only redirect if exam is actually started
	if exam_details and exam_details.get("submission_status") == "Started":
		frappe.local.flags.redirect_location = "/live/exam"
		raise frappe.Redirect

	context.no_cache = 1
	context.exams, context.next_exam = get_user_exams()
	
	context.metatags = {
		"title": _("My Exams"),
		"description": "View your upcoming and past exams"
	}
