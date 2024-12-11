from datetime import datetime
import frappe
from frappe import _
from frappe.utils.data import markdown

from exampro.exam_pro.doctype.exam_submission.exam_submission import \
	get_current_qs
from .evaluate import get_live_exam

# ACTIVE_EXAM_CODE_CACHE = "ACTIVEEXAMCODECACHE"

def get_context(context):
	context.no_cache = 1

	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login"
		raise frappe.Redirect

	exam_details = get_live_exam(frappe.session.user)
	context.page_context = {}

	if not exam_details:
		context.exam = {}
		context.alert = {
			"title": "No exams scheduled.",
			"text": "You do not have any live or upcoming exams."
		}
	elif exam_details["submission_status"] == "Submitted":
		frappe.local.flags.redirect_location = f"/exams/finished/{exam_details['exam_submission']}"
		raise frappe.Redirect
	elif exam_details["submission_status"] == "Terminated":
		frappe.local.flags.redirect_location = f"/exams/terminated/{exam_details['exam_submission']}"
		raise frappe.Redirect
	
	elif exam_details["live_status"] == "Live":
		context.alert = {}
		exam = frappe.db.get_value(
			"Exam", exam_details["exam"], ["name","title", "instructions"], as_dict=True
		)
		for key, value in exam_details.items():
			exam[key] = value

		exam["instructions"] = markdown(exam["instructions"])
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


	elif exam_details["live_status"] == "Upcoming":
		context.exam = {}
		context.alert = {
			"title": "You have an upcoming exam.",
			"text": "{} exam starts at {}".format(
				exam_details["exam"],
				exam_details["start_time"]
		)}
