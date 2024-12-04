from datetime import datetime

import frappe
from frappe import _

from lms.lms.utils import (redirect_to_exams_list)


def get_context(context):
	context.no_cache = 1

	try:
		exam_submission = frappe.form_dict["exam_submission"]
	except KeyError:
		redirect_to_exams_list()

	set_exam_context(context, exam_submission)


def set_exam_context(context, exam_submission):
	"""
	Check if the candidate has cleared the exam,
	If yes, get the score card
	"""
	try:
		exam_submission = frappe.get_doc("LMS Exam Submission", exam_submission)
	except Exception:
		frappe.throw("Invalid exam requested.")
	
	if exam_submission.candidate != frappe.session.user:
		frappe.throw("Incorrect exam requested.")

	if exam_submission.evaluation_pending:
		frappe.throw("Evaluation pending in exam.")
	elif exam_submission.status != "Terminated":
		redirect_to_exams_list()
	else:
		termination_message = frappe.get_all(
			"LMS Exam Messages",
			filters={
				"exam_submission": exam_submission.name,
				"type_of_message": "Critical"
			},
			fields=["message"],
			order_by="creation desc",
			limit=1
		)
		
		if termination_message:
			context.termination_reason = termination_message[0].message
		else:
			context.termination_reason = "The exam was terminated due to a violation of exam rules."
