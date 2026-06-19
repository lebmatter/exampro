# Copyright (c) 2024, Labeeb Mattra and contributors
# For license information, please see license.txt

import re

import frappe
from frappe.model.document import Document

def get_correct_options(question):
	correct_option_fields = [
		"is_correct_1",
		"is_correct_2",
		"is_correct_3",
		"is_correct_4",
	]
	return list(filter(lambda x: question.get(x) == 1, correct_option_fields))

def validate_duplicate_options(question):
	options = []

	for num in range(1, 5):
		if question.get(f"option_{num}"):
			options.append(question.get(f"option_{num}"))

	if len(set(options)) != len(options):
		frappe.throw(
			_("Duplicate options found for this question: {0}").format(
				frappe.bold(question.question)
			)
		)

def validate_correct_options(question):
	correct_options = get_correct_options(question)

	if len(correct_options) > 1:
		question.multiple = 1

	if not len(correct_options):
		frappe.throw(
			_("At least one option must be correct for this question: {0}").format(
				frappe.bold(question.question)
			)
		)

def extract_youtube_id(url):
	match = re.search(
		r"(?:youtube\.com/watch\?.*v=|youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})",
		url or "",
	)
	return match.group(1) if match else None


def validate_help_section(question):
	if question.help_show in (None, "", "Do not show"):
		return

	help_type = question.help_type or "Text"

	if help_type == "Text":
		if not (question.help_text or "").strip():
			frappe.throw(
				frappe._("Help text is required when help type is 'Text'.")
			)
	elif help_type == "YouTube Video":
		link = (question.help_link or "").strip()
		if not link:
			frappe.throw(frappe._("Help URL is required for YouTube Video type."))
		if not extract_youtube_id(link):
			frappe.throw(
				frappe._("Invalid YouTube URL. Use youtube.com/watch?v=ID, youtu.be/ID, or youtube.com/embed/ID.")
			)
	elif help_type == "Google Slides":
		link = (question.help_link or "").strip()
		if not link:
			frappe.throw(frappe._("Help URL is required for Google Slides type."))
		if "docs.google.com/presentation" not in link:
			frappe.throw(
				frappe._("Invalid Google Slides URL. Use a URL like docs.google.com/presentation/d/ID/embed.")
			)

	if question.type == "User Input" and question.help_show == "After wrong answer":
		frappe.throw(
			frappe._(
				"'After wrong answer' is not supported for subjective questions. "
				"Use 'After any answer' instead."
			)
		)

	quiz_rows = question.help_quiz or []
	if len(quiz_rows) > 3:
		frappe.throw(frappe._("Quick quiz allows at most 3 questions."))

	for idx, row in enumerate(quiz_rows, start=1):
		if row.correct_choice == "3" and not (row.choice_3 or "").strip():
			frappe.throw(
				frappe._(
					"Quick quiz row {0}: Choice 3 is required when it is marked as the correct choice."
				).format(idx)
			)


class ExamQuestion(Document):

	def validate(self):
		if self.type == "Choices":
			validate_duplicate_options(self)
			validate_correct_options(self)
		validate_help_section(self)

