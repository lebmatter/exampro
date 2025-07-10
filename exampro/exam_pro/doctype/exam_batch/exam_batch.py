# Copyright (c) 2025, Labeeb Mattra and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import re

class ExamBatch(Document):
	pass

@frappe.whitelist()
def bulk_add_users(batch_name, emails):
	"""
	Add multiple users to an Exam Batch based on a comma-separated list of email addresses.
	If user doesn't exist, create a new user with Exam Candidate role.
	
	Args:
		batch_name (str): Name of the Exam Batch
		emails (str): Comma-separated email addresses
	
	Returns:
		dict: Count of added and skipped users
	"""
	if not frappe.has_permission("Exam Batch", "write"):
		frappe.throw("Not permitted to add users to this batch")
	
	email_list = [email.strip() for email in emails.split(',') if email.strip()]
	added_count = 0
	skipped_count = 0
	
	# Email validation regex pattern
	email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
	
	for email in email_list:
		# Skip invalid email addresses
		if not re.match(email_pattern, email):
			frappe.log_error(f"Invalid email format: {email}", "Bulk Add Users")
			skipped_count += 1
			continue
		
		# Check if user exists
		user_exists = frappe.db.exists("User", email)
		
		# If user doesn't exist, create a new user
		if not user_exists:
			try:
				user = frappe.get_doc({
					"doctype": "User",
					"email": email,
					"first_name": email.split('@')[0],
					"send_welcome_email": 0
				})
				user.append("roles", {
					"role": "Exam Candidate"
				})
				user.insert(ignore_permissions=True)
				user_exists = email
			except Exception as e:
				frappe.log_error(f"Failed to create user {email}: {str(e)}", "Bulk Add Users")
				skipped_count += 1
				continue
		
		# Check if user is already added to this batch
		existing = frappe.db.exists("Exam Batch User", {
			"exam_batch": batch_name,
			"candidate": user_exists
		})
		
		if existing:
			skipped_count += 1
			continue
		
		# Add user to batch
		try:
			batch_user = frappe.new_doc("Exam Batch User")
			batch_user.exam_batch = batch_name
			batch_user.candidate = user_exists
			batch_user.insert(ignore_permissions=True)
			added_count += 1
		except Exception as e:
			frappe.log_error(f"Failed to add {email} to batch: {str(e)}", "Bulk Add Users")
			skipped_count += 1
	
	return {"added": added_count, "skipped": skipped_count}
