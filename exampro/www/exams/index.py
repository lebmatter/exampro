import frappe
from frappe import _
from lms.lms.utils import (
	# Exams and Course ceators share same role
	can_create_courses,
	check_profile_restriction,
	get_restriction_details,
	has_course_moderator_role
)
from lms.overrides.user import get_registered_exams, get_authored_exams, get_live_exam


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
	context.created_courses = get_authored_exams(None, False)
	context.restriction = check_profile_restriction()
	context.show_creators_section = can_create_courses()
	context.show_review_section = (
		has_course_moderator_role() and frappe.session.user != "Guest"
	)

	if context.restriction:
		context.restriction_details = get_restriction_details()

	context.metatags = {
		"title": _("Exam List"),
		"image": frappe.db.get_single_value("Website Settings", "banner_image"),
		"description": "This page lists all the exams published on our website",
		"keywords": "All Exams, Exams, Learn",
	}


def get_exams():
	exams = frappe.get_all(
		"LMS Exam",
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

	live_exams, upcoming_courses = [], []
	for exam in exams:
		if exam.upcoming:
			upcoming_courses.append(exam)
		else:
			live_exams.append(exam)
	return live_exams, upcoming_courses
