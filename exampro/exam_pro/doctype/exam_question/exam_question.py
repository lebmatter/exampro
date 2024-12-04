# Copyright (c) 2024, Labeeb Mattra and contributors
# For license information, please see license.txt

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

class ExamQuestion(Document):

	def validate(self):
		if self.type == "Choices":
			validate_duplicate_options(self)
			validate_correct_options(self)

