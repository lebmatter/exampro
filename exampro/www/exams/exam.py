import frappe
from frappe import _

from lms.lms.utils import (
	has_course_moderator_role,
	is_certified,
	is_instructor,
	redirect_to_exams_list,
	get_exam_average_rating,
)


def get_context(context):
	context.no_cache = 1

	try:
		exam_name = frappe.form_dict["exam"]
	except KeyError:
		redirect_to_exams_list()

	set_exam_context(context, exam_name)
	context.avg_rating = get_exam_average_rating(context.exam.name)


def set_exam_context(context, exam_name):
	exam = frappe.db.get_value(
		"LMS Exam",
		exam_name,
		[
			"name",
			"title",
			"image",
			"short_introduction",
			"description",
			"published",
			"upcoming",
			"enable_certification"
		],
		as_dict=True,
	)

	if frappe.form_dict.get("edit"):
		if not is_instructor(exam.name) and not has_course_moderator_role():
			raise frappe.PermissionError(_("You do not have permission to access this page."))
		exam.edit_mode = True

	if exam is None:
		raise frappe.PermissionError(_("This is not a valid course URL."))

	related_courses = frappe.get_all(
		"Related Courses", {"parent": exam.name}, ["course"]
	)
	for csr in related_courses:
		csr.update(
			frappe.db.get_value(
				"LMS Course",
				csr.course,
				["name", "upcoming", "title", "image", "enable_certification"],
				as_dict=True,
			)
		)
	exam.related_courses = related_courses

	context.exam = exam
	# context.registartion = registartion
	context.certificate = is_certified(exam.name)
	if context.exam.upcoming:
		context.is_user_interested = get_user_interest(context.exam.name)

	context.metatags = {
		"title": exam.title,
		"image": exam.image,
		"description": exam.short_introduction,
		"keywords": exam.title,
		"og:type": "website",
	}


def get_user_interest(exam):
	return frappe.db.count(
		"LMS Exam Interest", {"exam": exam, "user": frappe.session.user}
	)
