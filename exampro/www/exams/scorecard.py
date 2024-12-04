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
		exam_submission = frappe.db.get_value(
			"LMS Exam Submission", exam_submission,
			["exam", "candidate", "total_marks", "result_status", "evaluation_pending"],
			as_dict=True
		)
	except Exception:
		frappe.throw("Invalid exam requested.")
	
	if exam_submission["candidate"] != frappe.session.user:
		frappe.throw("Incorrect question requested.")

	if exam_submission["evaluation_pending"]:
		frappe.throw("Evaluation pending in exam.")
	else:
		exam_data = frappe.db.get_value(
			"LMS Exam", exam_submission["exam"],
			["total_marks", "show_result", "show_result_after_date"],
			as_dict=True
		)
		if exam_data["show_result"] == "After Specific Date":
			if datetime.now() > exam_data["show_result_after_date"]:
				frappe.throw("Result is not published yet.")

		exam_submission["exam_total_marks"] = exam_data["total_marks"]
		context.exam_submission = exam_submission