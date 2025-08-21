# Copyright (c) 2024, Labeeb Mattra and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ExamQuestionCategory(Document):
	def on_trash(self):
		frappe.db.delete("Exam Question", {"category": self.name})
