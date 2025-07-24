from datetime import datetime, timedelta

import frappe
from frappe import _

from exampro.exam_pro.api.utils import (redirect_to_exams_list)
from exampro.exam_pro.doctype.exam_schedule.exam_schedule import get_schedule_end_time


def get_context(context):
	context.no_cache = 1

	try:
		exam_submission = frappe.form_dict["exam_submission"]
	except KeyError:
		redirect_to_exams_list()

	set_exam_context(context, exam_submission)


def set_exam_context(context, exmsubmn):
	"""
	Set the exam context based on the submission status
	"""
	try:
		exam_submission = frappe.get_doc("Exam Submission", exmsubmn)
	except Exception:
		frappe.throw("Invalid exam requested.")
	
	# Check if user is authorized to view this exam
	if exam_submission.candidate != frappe.session.user and not is_exam_manager():
		frappe.throw("You are not authorized to view this exam result.")

	context.exam_submission = exam_submission
	
	# Get exam data
	exam_data = frappe.db.get_value(
		"Exam", exam_submission.exam,
		["total_marks", "show_result", "show_result_after_date", "total_marks"],
		as_dict=True
	)
	
	context.exam_data = exam_data
	
	# Set context based on submission status
	if exam_submission.status == "Terminated":
		context.result_type = "terminated"
		termination_message = frappe.get_all(
			"Exam Messages",
			filters={
				"exam_submission": exam_submission.name,
				"type_of_message": "Critical",
				"from": "System"
			},
			fields=["message"],
			order_by="creation desc",
			limit=1
		)
		
		if termination_message:
			context.message = termination_message[0].message
		else:
			context.message = "The exam was terminated due to a violation of exam rules."
	
	elif exam_submission.status == "Submitted":
		if exam_submission.evaluation_status == "Pending":
			context.result_type = "pending"
			context.message = "Evaluation pending in your exam. Please check back later for your score!"
		else:
			# Check result display settings
			if exam_data["show_result"] == "After Specific Date":
				if datetime.now() < exam_data["show_result_after_date"]:
					context.result_type = "pending"
					context.message = "Result will be published after {}.".format(
						exam_data["show_result_after_date"].strftime("%d %b %Y"))
				else:
					context.result_type = "scorecard"
			elif exam_data["show_result"] == "Do Not Show Score":
				context.result_type = "pending"
				context.message = "The score will not be displayed for this exam."
			elif exam_data["show_result"] == "After Exam Submission":
				context.result_type = "scorecard"
			elif exam_data["show_result"] == "After Schedule Completion":
				schedule_completion = get_schedule_end_time(exam_submission.exam_schedule, exam_submission.additional_time_given)
				ended = datetime.now() > schedule_completion
				end_time = schedule_completion + timedelta(minutes=5)  # Adding a buffer of 5 minutes
				if ended:
					context.result_type = "scorecard"
				else:
					context.result_type = "pending"
					context.message = "Result will be published after {}.".format(
						end_time.strftime("%d %b %Y, %H:%M:%S")
					)
		
		if context.result_type == "scorecard" and exam_submission.result_status == "NA":
			context.result_type = "pending"
			context.message = "Your exam submission is incomplete or not evaluated yet. Please check back later."

	else:
		context.result_type = "pending"
		context.message = "This exam submission is currently in progress or incomplete."


def is_exam_manager():
	"""Check if current user is an exam manager"""
	roles = frappe.get_roles(frappe.session.user)
	return "Exam Manager" in roles or "Administrator" in roles
