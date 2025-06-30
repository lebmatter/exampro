from datetime import datetime, timedelta
import frappe
from frappe.utils import now, format_datetime

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
			"exam_name": exam.name,
			"exam_schedule": submission["exam_schedule"],
			"start_time": schedule.start_date_time,
			"schedule_time": format_datetime(schedule.start_date_time, "dd MMM YYYY, HH:mm"),  # Added for template
			"end_time": end_time,
			"additional_time_given": submission["additional_time_given"],
			"submission_status": submission["status"],
			"status": submission["status"],  # Added for template
			"duration": f"{schedule.duration} min",  # Format duration as "X min"
			"enable_calculator": exam.enable_calculator,
			"schedule_status": "Upcoming",
			"schedule_type": schedule.schedule_type,
			"enable_video_proctoring": exam.enable_video_proctoring,
			"enable_chat": exam.enable_chat,
			"submission": submission["name"],  # Added for view result link
			"score": frappe.db.get_value("Exam Submission", submission["name"], "total_marks") if submission["status"] == "Submitted" else None
		}

		# make datetime in isoformat
		for key,val in exam_details.items():
			if isinstance(val, datetime):
				exam_details[key] = val.isoformat()

		# checks if current time is between schedule start and end time
		# ongoing exams can be in Not started, started or submitted states
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
				
		# Set status field to match template expectations
		if submission["status"] == "Not Started":
			exam_details["status"] = "Upcoming"
		else:
			exam_details["status"] = submission["status"]
				
		res.append(exam_details)

	# Sort exams by schedule time
	res.sort(key=lambda x: x["start_time"], reverse=True)

	return res


def get_next_exam(exams):
	"""Get the next upcoming or current exam for the user."""
	if not exams:
		return None
	
	# Group exams by status
	started_exams = [exam for exam in exams if exam["submission_status"] == "Started"]
	upcoming_exams = [exam for exam in exams if exam["schedule_status"] == "Upcoming"]
	
	# Return started exam first if available
	if started_exams:
		return started_exams[0]
	
	# Otherwise return the next upcoming exam (closest to current time)
	if upcoming_exams:
		# Sort by start_time
		return sorted(upcoming_exams, key=lambda x: x["start_time"])[0]
	
	return None

def get_time_until(target_datetime_str):
	"""Calculate time difference between now and target datetime."""
	target_datetime = datetime.fromisoformat(target_datetime_str)
	now_datetime = datetime.strptime(now(), '%Y-%m-%d %H:%M:%S.%f')
	diff = target_datetime - now_datetime
	
	days = diff.days
	hours, remainder = divmod(diff.seconds, 3600)
	minutes, seconds = divmod(remainder, 60)
	
	if days > 0:
		return f"{days} days, {hours} hours"
	elif hours > 0:
		return f"{hours} hours, {minutes} minutes"
	else:
		return f"{minutes} minutes"

def get_context(context):
	"""
	Check if there is any started exam for the user,
	If so redirect to it. Otherwise show exam list with upcoming exam banner.
	"""
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login"
		raise frappe.Redirect

	context.no_cache = 1
	context.exams = exams = get_user_exams()
	
	# Get next exam information for banner
	context.next_exam = next_exam = get_next_exam(exams)
	if next_exam:
		if next_exam["submission_status"] == "Started":
			context.next_exam_message = "You have an exam in progress. Continue where you left off."
			context.next_exam_link = "/exam"
			context.next_exam_link_text = "Continue Exam"
		elif next_exam["schedule_type"] == "Fixed" and next_exam["schedule_status"] == "Upcoming":
			time_until = get_time_until(next_exam["start_time"])
			context.next_exam_message = "Your next exam '{}' is scheduled to start in {}.".format(next_exam["exam_name"], time_until)
			context.next_exam_link = "/exam"
			context.next_exam_link_text = "View Details"
		elif next_exam["schedule_type"] == "Flexible":
			context.next_exam_message = "Your flexible schedule exam '{}' is available. {}".format(
				next_exam["exam_name"], 
				next_exam["schedule_status"]
			)
			context.next_exam_link = "/exam"
			context.next_exam_link_text = "Start Exam"
	
	context.metatags = {
		"title": "My Exams",
		"description": "View your upcoming and past exams"
	}
