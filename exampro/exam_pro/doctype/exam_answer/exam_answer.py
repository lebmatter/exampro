# Copyright (c) 2024, Labeeb Mattra and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ExamAnswer(Document):

	def before_save(self):
		"""
		Validate if appilicable before save
		"""
		# evaluate
		question_type = frappe.get_cached_value(
			"Exam Question", self.exam_question, "type"
		)
		mark = frappe.get_cached_value(
			"Exam Question", self.exam_question, "mark"
		)

		if question_type == "Choices" and self.answer:
			answered_options = [ans for ans in self.answer.split(",")]
			correct_options = frappe.get_cached_value(
				"Exam Question", self.exam_question,
				[
					"is_correct_1",
					"is_correct_2",
					"is_correct_3",
					"is_correct_4"
				],
				as_dict=True
			)
			correct_options = [
				ckey[-1:] for ckey, val in correct_options.items() if val
			]
			if sorted(answered_options) == sorted(correct_options):
				self.is_correct = 1
				self.evaluation_status = "Auto"
				self.mark = mark
			else:
				self.is_correct = 0
				self.evaluation_status = "Auto"
				self.mark = 0
		elif question_type == "Choices" and not self.answer:
			self.mark = 0
			self.evaluation_status = "Auto"
