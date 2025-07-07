# Copyright (c) 2025, Labeeb Mattra and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from datetime import datetime
from frappe.utils import now


class ExamBatchUser(Document):
	def before_save(self):
		# If this is a new document (being inserted for the first time)
		if self.is_new():
			# Check for upcoming exam schedules with this batch and auto_assign_batch_users enabled
			self.check_and_create_exam_submissions()
	
	def check_and_create_exam_submissions(self):
		"""
		Check for upcoming exam schedules with this batch and auto_assign_batch_users enabled,
		and create Exam Submission entries accordingly
		"""
		# Get current datetime for comparison
		current_time = datetime.fromisoformat(now().split(".")[0])
		
		# Get all exam schedules with auto_assign_batch_users enabled and upcoming
		schedules = frappe.get_all("Exam Schedule",
			filters={
				"auto_assign_batch_users": 1,
				"start_date_time": (">", current_time)  # Only upcoming schedules
			},
			fields=["name", "exam"]
		)
		
		# Filter schedules to only include those that have this batch
		valid_schedules = []
		for schedule in schedules:
			# Check if this batch is included in the schedule's batch_assignments
			batch_assigned = frappe.get_all("Schedule Batch Assignment",
				filters={
					"parent": schedule.name,
					"batch_name": self.exam_batch
				},
				fields=["name"],
				limit=1
			)
			
			if batch_assigned:
				valid_schedules.append(schedule)
		
		schedules = valid_schedules
		
		submissions_created = 0
		for schedule in schedules:
			# Check if a submission already exists for this candidate and schedule
			existing = frappe.get_all("Exam Submission", 
				filters={
					"exam_schedule": schedule.name,
					"candidate": self.candidate
				},
				limit=1
			)
			
			if not existing:
				# Create new submission
				submission = frappe.new_doc("Exam Submission")
				submission.exam_schedule = schedule.name
				submission.exam = schedule.exam
				submission.candidate = self.candidate
				submission.exam_batch = self.exam_batch
				submission.status = "Registered"
				submission.insert(ignore_permissions=True)
				submissions_created += 1
		
		if submissions_created > 0:
			frappe.msgprint(f"Created {submissions_created} exam submissions for the newly added batch user")
