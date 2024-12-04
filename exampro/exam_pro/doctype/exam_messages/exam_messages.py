# Copyright (c) 2024, Labeeb Mattra and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from exampro.exam_pro.doctype.exam_submission.exam_submission import terminate_exam


class ExamMessages(Document):

	def after_insert(self):
		# trigger webocket msg to proctor and candidate
		chat_message = {
				"creation": self.timestamp,
				"exam_submission": self.exam_submission,
				"message": self.message,
				"type_of_message": self.type_of_message
		}
		frappe.publish_realtime(
			event='newcandidatemsg',
			message=chat_message,
			user=frappe.db.get_value(
				"Exam Submission", self.exam_submission, "candidate"
		))

		# if there is an assigned proctor, send a msg
		proctor = frappe.db.get_value(
				"Exam Submission", self.exam_submission, "assigned_proctor"
		)
		if proctor:
			frappe.publish_realtime(
				event='newproctormsg',
				message=chat_message,
				user=proctor
			)
		# update critical warning error
		wc = frappe.cache().hget(self.exam_submission, "warning_count") or 0
		new_wc = wc + 1
		frappe.cache().hset(self.exam_submission, "warning_count", new_wc)

		if self.type_of_message == "Warning":
			exam = frappe.get_cached_value("Exam Submission", self.exam_submission, "exam")
			max_warning = frappe.get_cached_value("Exam", exam, "max_warning_count")
			if new_wc > max_warning:
				terminate_exam(self.exam_submission, check_permission=False)

