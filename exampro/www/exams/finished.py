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


def set_exam_context(context, exmsubmn):
	"""
	Check if the candidate has cleared the exam,
	If yes, get the score card
	"""
	try:
		exam_submission = frappe.get_doc("LMS Exam Submission", exmsubmn)
	except Exception:
		frappe.throw("Invalid exam requested.")
	
	if exam_submission.candidate != frappe.session.user:
		frappe.throw("Incorrect exam requested.")

	elif exam_submission.status != "Submitted":
		redirect_to_exams_list()
	else:
		
		exam_data = frappe.db.get_value(
			"LMS Exam", exam_submission.exam,
			["total_marks", "show_result", "show_result_after_date"],
			as_dict=True
		)

		if exam_submission.evaluation_pending:
			context.score_message = "Evaluation pending in your exam. Please check back later for your score!"
		elif exam_data["show_result"] == "After Specific Date":
			if datetime.now() < exam_data["show_result_after_date"]:
				context.score_message = "Result will be published after {}.".format(exam_data["show_result_after_date"].strftime("%d %b %Y"))
			else:
				frappe.local.flags.redirect_location = "/exams/scorecard/{}".format(exam_submission.name)
				raise frappe.Redirect
		elif exam_data["show_result"] == "Do Not Show Score":
			context.score_message = "The score will not be displayed for this exam."
		elif exam_data["show_result"] == "After Exam Submission":
			frappe.local.flags.redirect_location = "/exams/scorecard/{}".format(exam_submission.name)
			raise frappe.Redirect