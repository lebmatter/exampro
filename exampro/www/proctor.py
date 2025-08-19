from datetime import datetime, timedelta
from frappe.utils import now

import frappe
from frappe import _

def get_proctor_upcoming_events(proctor=None):
	"""
	Get upcoming proctoring events for the next 7 days
	"""
	proctor = proctor or frappe.session.user
	
	# Get current time and 7 days from now
	current_time = frappe.utils.now_datetime()
	week_later = current_time + timedelta(days=7)
	
	# Get upcoming exam schedules where user is assigned as proctor
	upcoming_schedules = frappe.get_all(
		"Exam Schedule",
		filters={
			"start_date_time": ["between", [current_time, week_later]],
			"status": ["in", ["Scheduled", "Active"]]
		},
		fields=[
			"name",
			"exam",
			"start_date_time", 
			"duration",
			"status"
		],
		order_by="start_date_time"
	)
	
	upcoming_events = []
	for schedule in upcoming_schedules:
		# Count assigned candidates for this proctor in this schedule
		candidate_count = frappe.db.count(
			"Exam Submission",
			{
				"exam_schedule": schedule.name,
				"assigned_proctor": proctor,
				"status": ["not in", ["Registration Cancelled", "Aborted"]]
			}
		)
		
		if candidate_count > 0:
			exam_title = frappe.db.get_value("Exam", schedule.exam, "title")
			upcoming_events.append({
				"schedule_name": schedule.name,
				"exam_title": exam_title,
				"start_time": schedule.start_date_time,
				"duration": schedule.duration,
				"candidate_count": candidate_count,
				"status": schedule.status
			})
	
	return upcoming_events

def get_proctor_live_exams(proctor=None, skip_submitted=False):
	"""
	Get upcoming/ongoing exam of a proctor.

	Check if current time is inbetween start and end time
	Function returns only one live/upcoming exam details
	even if multiple entries are there.
	"""
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
		if skip_submitted and submission["status"] == "Submitted":
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
			if submission["status"] == "Started":
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
		elif submission["status"] == "Submitted":
			msg_text = "Exam submitted. Schedule ongoing."
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
	proctor_list = get_proctor_live_exams(skip_submitted=True)

	context.submissions = proctor_list["live_submissions"]
	context.pending_candidates = proctor_list["pending_candidates"]
	context.latest_messages = get_latest_messages()
	
	# Get upcoming events for alert
	upcoming_events = get_proctor_upcoming_events()
	if upcoming_events:
		# Show alert if there are upcoming events in next 24 hours
		next_24_hours = frappe.utils.now_datetime() + timedelta(hours=24)
		urgent_events = [e for e in upcoming_events if e['start_time'] <= next_24_hours]
		
		if urgent_events:
			total_candidates = sum(e['candidate_count'] for e in urgent_events)
			context.alert = {
				"title": f"Upcoming Proctoring Session{'' if len(urgent_events) == 1 else 's'}",
				"text": f"You have {len(urgent_events)} proctoring session{'' if len(urgent_events) == 1 else 's'} scheduled in the next 24 hours with {total_candidates} assigned candidate{'' if total_candidates == 1 else 's'}. Please ensure you're prepared and available at the scheduled time."
			}
	
	context.upcoming_events = upcoming_events

