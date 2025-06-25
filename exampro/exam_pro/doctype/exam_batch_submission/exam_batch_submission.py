# Copyright (c) 2025, Labeeb Mattra and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ExamBatchSubmission(Document):
	def on_save(self):
		self.create_exam_submissions()
		
	def create_exam_submissions(self):
		"""
		Create exam_submission entries for all users in the exam_batch
		"""
		# Get all users from exam_batch_user for this batch
		batch_users = frappe.get_all(
			"Exam Batch User",
			filters={"exam_batch": self.exam_batch},
			fields=["candidate"]
		)
		
		for user in batch_users:
			# Check if submission already exists for this user and schedule
			existing_submission = frappe.db.exists(
				"Exam Submission",
				{
					"candidate": user.candidate, 
					"exam_schedule": self.exam_schedule,
					"exam_batch": self.exam_batch
				}
			)
			
			if not existing_submission:
				# Create new exam submission
				submission = frappe.new_doc("Exam Submission")
				submission.candidate = user.candidate
				submission.exam_schedule = self.exam_schedule
				submission.exam = self.exam
				submission.exam_batch = self.exam_batch
				submission.status = "Registered"
				
				# Get candidate name
				user_doc = frappe.get_doc("User", user.candidate)
				submission.candidate_name = user_doc.full_name
				
				# Save the submission
				submission.insert(ignore_permissions=True)
				
		frappe.msgprint(f"Created exam submissions for all users in batch {self.exam_batch}")
