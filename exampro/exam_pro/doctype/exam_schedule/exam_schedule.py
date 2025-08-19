# Copyright (c) 2024, Labeeb Mattra and contributors
# For license information, please see license.txt

from datetime import timedelta, datetime, date
from dateutil.parser import parse
import frappe
import base64
import uuid

from frappe.utils import now
from frappe.model.document import Document
from exampro.exam_pro.api.utils import submit_candidate_pending_exams
from exampro.exam_pro.api.examops import evaluation_values


class ExamSchedule(Document):

	# Add status to standard fields
	_standard_fieldnames = ['name', 'owner', 'creation', 'modified', 'modified_by',
		'parent', 'parentfield', 'parenttype', 'idx', 'docstatus',
		'naming_series', 'status']

	def generate_short_uuid(self):
		"""Generate a short UUID (8 characters)"""
		return str(uuid.uuid4()).replace('-', '')[:8]

	def before_insert(self):
		if not self.short_uuid:
			self.short_uuid = self.generate_short_uuid()

	def _validate_user_role(self, user_id, role_name):
		"""
		Check if the user has the specified role and assign it if needed
		"""
		# Check if the user has the role
		roles = frappe.get_roles(user_id)
		if role_name not in roles:
			frappe.throw(
				"User {} does not have the role '{}'. Please assign the role before proceeding.".format(
					user_id, role_name
				)
			)

	def on_trash(self):
		frappe.db.delete("Exam Submission", {"exam_schedule": self.name})

	def before_save(self):
		question_type = frappe.db.get_value("Exam", self.exam, "question_type")

		if question_type != "Choices" and not self.examiners:
			frappe.msgprint(
				"Warning: Exam with question type:{} needs evaluation. Add examiner list.".format(
					self.question_type
			))

		# validate cert template
		# if self.certificate_template != "":
		# 	has_certification = frappe.db.get_value("Exam", self.exam, "enable_certification")
		# 	if not has_certification:
		# 		frappe.msgprint("Warning: Certification is not enabled in the exam.")
		# 		self.certificate_template = ""
		
		old_doc = self.get_doc_before_save()
		if old_doc:
			current_time = parse(self.start_date_time) if isinstance(self.start_date_time, str) else self.start_date_time
			if old_doc.start_date_time != current_time:
				old_time = old_doc.start_date_time if isinstance(old_doc.start_date_time, datetime) else parse(old_doc.start_date_time)
				new_time = self.start_date_time if isinstance(self.start_date_time, datetime) else parse(self.start_date_time)
				
				frappe.msgprint(
					msg="""Scheduled time has changed from {} to {}. \
						System will send exam time modification emails to the students and proctors.""".format(
							old_time.strftime("%Y-%m-%d %H:%M") if old_time else "N/A",
							new_time.strftime("%Y-%m-%d %H:%M") if new_time else "N/A"
						),
					title="Sending modification emails...",
					wide=True
				)
	
		# If batch_assignments are present and auto_assign_batch_users is checked, add Exam Submissions for all users in the batches
		if self.batch_assignments and self.auto_assign_batch_users:
			self.create_exam_submissions_for_batch_users()

	def create_exam_submissions_for_batch_users(self):
		"""
		Fetch all users from the selected batches and create Exam Submission entries for each user
		while avoiding duplicates
		"""
		# Check for existing submissions to avoid duplicates
		existing_submissions = frappe.get_all("Exam Submission", 
			filters={"exam_schedule": self.name},
			fields=["candidate"]
		)
		
		existing_candidates = set([s.candidate for s in existing_submissions])
		
		submissions_created = 0
		batch_counts = {}
		
		# Process each batch in the batch_assignments table
		for batch_assignment in self.batch_assignments:
			batch_id = batch_assignment.batch_name
			
			# Get all users from the current batch
			batch_users = frappe.get_all("Exam Batch User", 
				filters={"exam_batch": batch_id},
				fields=["candidate"]
			)
			
			if not batch_users:
				frappe.msgprint(f"No users found in batch {batch_id}. No submissions created for this batch.")
				continue
			
			batch_counts[batch_id] = 0
			
			for user in batch_users:
				candidate = user.candidate
				
				# Skip if submission already exists for this candidate
				if candidate in existing_candidates:
					continue
					
				# Create new submission
				submission = frappe.new_doc("Exam Submission")
				submission.exam_schedule = self.name
				submission.exam = self.exam
				submission.candidate = candidate
				submission.exam_batch = batch_id
				submission.status = "Registered"
				submission.insert(ignore_permissions=True)
				submissions_created += 1
				batch_counts[batch_id] += 1
				
				# Add to existing candidates to avoid duplicates if the same candidate is in multiple batches
				existing_candidates.add(candidate)
		
		# Construct message about created submissions
		if submissions_created > 0:
			batch_messages = [f"{count} for batch {batch_id}" for batch_id, count in batch_counts.items() if count > 0]
			message = f"Created {submissions_created} new exam submissions ({', '.join(batch_messages)})"
			frappe.msgprint(message)

	def on_update(self):
		"""
		Detect changes in examiners child table and reassign exam submissions if needed
		"""
		old_doc = self.get_doc_before_save()
		if not old_doc:
			return  # This is a new document, no need to check for changes
		
		# Check if examiners have changed
		examiners_changed = self._have_examiners_changed(old_doc)
		
		if examiners_changed:
			frappe.msgprint(
				msg="Examiner assignments have been modified. All exam submissions will be reassigned to maintain balanced distribution.",
				title="Reassigning Exam Submissions",
				indicator="blue"
			)
			self._reassign_all_submissions()
	
	def _have_examiners_changed(self, old_doc):
		"""
		Check if examiners child table has been modified
		"""
		# Get current and old examiners
		current_examiners = {
			(ex.examiner, ex.can_proctor, ex.can_evaluate) 
			for ex in (self.examiners or [])
		}
		
		old_examiners = {
			(ex.examiner, ex.can_proctor, ex.can_evaluate) 
			for ex in (old_doc.examiners or [])
		}
		
		# Check if there are any differences
		return current_examiners != old_examiners
	
	def _reassign_all_submissions(self):
		"""
		Reassign all exam submissions for this schedule
		"""
		if not self.examiners:
			frappe.msgprint("No examiners available for assignment.", indicator="orange")
			return
		
		# Get all exam submissions for this schedule
		submissions = frappe.get_all(
			"Exam Submission",
			filters={"exam_schedule": self.name},
			fields=["name", "exam"]
		)
		
		if not submissions:
			return
		
		# Check exam requirements
		exam_doc = frappe.get_doc("Exam", self.exam)
		needs_proctoring = getattr(exam_doc, 'needs_proctoring', True)
		needs_evaluation = exam_doc.question_type != "Choices"
		
		if not needs_proctoring and not needs_evaluation:
			return  # No assignment needed
		
		# Get available examiners
		proctors = [ex.examiner for ex in self.examiners if ex.can_proctor] if needs_proctoring else []
		evaluators = [ex.examiner for ex in self.examiners if ex.can_evaluate] if needs_evaluation else []
		
		if needs_proctoring and not proctors:
			frappe.msgprint("No examiners available for proctoring.", indicator="orange")
		if needs_evaluation and not evaluators:
			frappe.msgprint("No examiners available for evaluation.", indicator="orange")
		
		# Track assignments for round-robin distribution
		proctor_assignments = {proctor: 0 for proctor in proctors}
		evaluator_assignments = {evaluator: 0 for evaluator in evaluators}
		
		updated_count = 0
		
		# Reassign all submissions
		for submission_data in submissions:
			submission = frappe.get_doc("Exam Submission", submission_data.name)
			updated = False
			
			# Assign proctor
			if needs_proctoring and proctors:
				# Find proctor with least assignments
				next_proctor = min(proctor_assignments, key=proctor_assignments.get)
				if submission.assigned_proctor != next_proctor:
					submission.assigned_proctor = next_proctor
					updated = True
				proctor_assignments[next_proctor] += 1
			
			# Assign evaluator
			if needs_evaluation and evaluators:
				# Find evaluator with least assignments
				next_evaluator = min(evaluator_assignments, key=evaluator_assignments.get)
				if submission.assigned_evaluator != next_evaluator:
					submission.assigned_evaluator = next_evaluator
					updated = True
				evaluator_assignments[next_evaluator] += 1
			
			# Save if updated
			if updated:
				submission.save(ignore_permissions=True)
				updated_count += 1
		
		if updated_count > 0:
			frappe.db.commit()
			frappe.msgprint(
				f"Successfully reassigned {updated_count} exam submissions.",
				indicator="green"
			)

	def after_save(self):
		self.send_proctor_emails()
	
	def get_status(self, additional_time=0):
		"""
		Calculate and return the status of the exam schedule.
		:param additional_time: Optional minutes to adjust the end time for status calculation.
		Returns the status of the exam schedule based on the current time and start date time.
		- "Upcoming" if the current time is before the start date time.
		- "Ongoing" if the current time is between the start date time and end date time.
		- "Completed" if the current time is after the end date time.
		"""
		current_time = datetime.fromisoformat(now().split(".")[0])
		
		# Ensure start_date_time is a datetime object
		start_time = self.start_date_time
		if not isinstance(start_time, datetime):
			start_time = parse(start_time) if start_time else current_time
		
		# Calculate end time based on schedule type
		if self.schedule_type == "Fixed":
			end_time = start_time + timedelta(minutes=self.duration or 0)
		else:
			# For flexible schedules, we consider the end time as start time + duration + days
			days = self.schedule_expire_in_days or 0
			end_time = start_time + timedelta(minutes=self.duration or 0, days=days)
		
		# If additional_time is provided, adjust the end time
		if additional_time:
			end_time += timedelta(minutes=additional_time)
		
		# Debug log
		frappe.logger().debug(f"Status calculation for {self.name}:")
		frappe.logger().debug(f"- current_time: {current_time}")
		frappe.logger().debug(f"- start_time: {start_time}")
		frappe.logger().debug(f"- end_time: {end_time}")
		
		# Determine status
		status = None
		if current_time < start_time:
			status = "Upcoming"
		elif start_time <= current_time <= end_time:
			status = "Ongoing"
		else:
			status = "Completed"
			
		frappe.logger().debug(f"- status: {status}")
		return status

	@frappe.whitelist()
	def get_exam_schedule_status(self):
		"""
		Returns the status of the exam schedule for list view and form view.
		This is a wrapper around get_status that can be called via frappe.call.
		"""
		return self.get_status()

	def send_proctor_emails(self):
		for examiner in self.examiners:
			if not examiner.notification_sent:
				context = {
					"exam": self.exam,
					"scheduled_time": self.start_date_time
				}
				# Retrieve the email template document
				email_template = frappe.get_doc("Email Template", "Exam Proctor Assignment")

				# Render the subject and message
				subject = frappe.render_template(email_template.subject, context)
				message = frappe.render_template(email_template.response, context)

				member_email = frappe.db.get_value("User", self.examiner, "email")
				frappe.sendmail(
					recipients=[member_email],
					subject=subject,
					message=message,
				)
				frappe.db.set_value("Examiner", examiner.name, "notification_sent", 1)
	
	def can_end_schedule(self):
		current_time = datetime.fromisoformat(now().split(".")[0])
		
		# Ensure start_date_time is a datetime object
		start_time = self.start_date_time
		if not isinstance(start_time, datetime):
			start_time = parse(start_time) if start_time else current_time
		
		if self.schedule_type == "Fixed":
			end_time = start_time + timedelta(minutes=self.duration)
		else:
			# For flexible schedules, we consider the end time as start time + duration + days
			end_time = start_time + timedelta(minutes=self.duration, days=self.schedule_expire_in_days)
		
		if current_time < end_time:
			frappe.msgprint("Can't end the schedule before {} (end time).".format(end_time.isoformat()))
			return False
		 
		return True

			
	def as_dict(self, no_nulls=False):
		"""Convert the document to a dict for the list view, including the status"""
		d = super(ExamSchedule, self).as_dict(no_nulls=no_nulls)
		status = self.get_status()
		d['status'] = status
		d['_server_status'] = status  # Special field for JavaScript to use
		return d
	
	@frappe.whitelist()
	def generate_invite_link(self):
		"""Generate an invite link for this exam schedule"""
		# Get the current domain from site configuration
		domain = frappe.local.conf.get("host_name") or frappe.local.site
		if not domain.startswith(('http://', 'https://')):
			domain = "http://" + domain
			
		# Use the short_uuid as the invite code
		if not self.short_uuid:
			self.short_uuid = self.generate_short_uuid()
		
		# Create the invite link using short_uuid
		invite_link = f"{domain}/exam/invite/{self.short_uuid}"
		
		# Update the document
		self.schedule_invite_link = invite_link
		self.save(ignore_permissions=True)
		
		return invite_link


@frappe.whitelist()
def bulk_add_submissions(schedule_name, email_list):
	"""
	Bulk add exam submissions for the given email addresses
	"""
	# Check user permissions
	user_roles = frappe.get_roles()
	if "System Manager" not in user_roles and "Exam Manager" not in user_roles:
		frappe.throw("You do not have permission to bulk add submissions.")
	
	# Get the exam value directly from the database to avoid document modification issues
	exam_name = frappe.db.get_value("Exam Schedule", schedule_name, "exam")
	if not exam_name:
		frappe.throw("Exam Schedule not found or exam not set.")
	
	# Parse email list - handle commas, semicolons, and newlines
	import re
	emails = re.split(r'[,;\n\r]+', email_list.strip())
	emails = [email.strip() for email in emails if email.strip()]
	
	if not emails:
		frappe.throw("No valid email addresses provided.")
	
	# Get existing submissions to avoid duplicates
	# Only consider submissions that are not Terminated or Submitted
	existing_submissions = frappe.get_all("Exam Submission", 
		filters={
			"exam_schedule": schedule_name,
			"status": ["not in", ["Terminated", "Submitted"]]
		},
		fields=["candidate"]
	)
	existing_candidates = set([s.candidate for s in existing_submissions])
	
	added_count = 0
	duplicate_count = 0
	invalid_users = []
	
	# Process emails in smaller batches to avoid long-running transactions
	batch_size = 10
	for i in range(0, len(emails), batch_size):
		batch_emails = emails[i:i + batch_size]
		
		for email in batch_emails:
			# Skip if already exists
			if email in existing_candidates:
				duplicate_count += 1
				continue
			
			# Check if user exists
			user_exists = frappe.db.exists("User", email)
			if not user_exists:
				invalid_users.append(email)
				continue
			
			try:
				# Create new submission with minimal document interaction to avoid conflicts
				submission = frappe.get_doc({
					'doctype': 'Exam Submission',
					'exam_schedule': schedule_name,
					'exam': exam_name,
					'candidate': email,
					'status': 'Registered'
				})
				
				# Insert with flags to reduce hook execution and conflicts
				submission.insert(ignore_permissions=True, ignore_mandatory=True)
				
				added_count += 1
				
				# Add to existing candidates to avoid duplicates in this batch
				existing_candidates.add(email)
				
			except Exception as e:
				frappe.logger().error(f"Error creating submission for {email}: {str(e)}")
				invalid_users.append(f"{email} (Error: {str(e)})")
		
		# Commit after each batch and clear any cached documents
		frappe.db.commit()
		frappe.clear_cache(doctype="Exam Schedule")
		frappe.clear_cache(doctype="Exam Submission")
	
	return {
		"added": added_count,
		"duplicates": duplicate_count,
		"invalid_users": invalid_users
	}
	
	return {
		"added": added_count,
		"duplicates": duplicate_count,
		"invalid_users": invalid_users
	}


def _send_certificates(schedule_name):
	"""
	send certificates if applicable
	"""
	submissions = frappe.get_all(
		"Exam Submission", 
		filters={"exam_schedule": schedule_name},
		fields=["name", "result_status", "status", "total_marks", "exam", "candidate", "candidate_name"]
	)
	for subm in submissions:
		if subm["status"] != "Submitted":
			continue
		
		if subm["result_status"] != "Passed":
			continue

		try:
			frappe.get_last_doc("Exam Certificate", filters={"exam_submission": subm["name"]})
		except frappe.DoesNotExistError:
			today = date.today()
			certexp = frappe.db.get_value("Exam", subm["exam"], "expiry")

			new_cert = frappe.get_doc({
				"doctype":"Exam Certificate",
				"exam_submission": subm["name"],
				"exam": subm["exam"],
				"member": subm["candidate"],
				"member_name": subm["candidate_name"],
				"issue_date": today
			})
			if certexp:
				certexp *= 365
				new_cert.expiry_date = today + timedelta(days=certexp)
			new_cert.insert()

@frappe.whitelist()
def send_certificates(docname):
	# check user has system manager or exam manager role
	user_roles = frappe.get_roles()
	if "System Manager" not in user_roles and "Exam Manager" not in user_roles:
		frappe.throw("You do not have permission to send certificates.")

	doc = frappe.get_doc("Exam Schedule", docname)
	
	# Check if schedule can be ended (is completed)
	if get_schedule_status(docname) != "Completed":
		frappe.throw("Cannot send certificates. The exam schedule is not yet completed.")

	# Check if exam has certification enabled
	has_certification = frappe.db.get_value("Exam", doc.exam, "enable_certification")
	if not has_certification:
		frappe.throw("Certification is not enabled for this exam.")

	# Get all submitted submissions
	submissions = frappe.get_all(
		"Exam Submission", 
		filters={"exam_schedule": docname, "status": "Submitted"},
		fields=["name", "result_status", "exam", "candidate", "candidate_name"]
	)
	
	if not submissions:
		return "No submitted exam submissions found for this schedule."

	# Submit any pending exams first
	for subm in submissions:
		try:
			submit_candidate_pending_exams(subm["candidate"])
		except:
			pass  # Continue if this fails

	# Count passed submissions
	passed_submissions = [s for s in submissions if s["result_status"] == "Passed"]
	
	if not passed_submissions:
		return f"No passed submissions found. Total submissions: {len(submissions)}, None passed."

	# Send certificates for passed submissions
	certificates_sent = 0
	certificates_already_exist = 0
	errors = []

	for subm in passed_submissions:
		try:
			# Check if certificate already exists
			existing_cert = frappe.db.exists("Exam Certificate", {"exam_submission": subm["name"]})
			if existing_cert:
				certificates_already_exist += 1
				continue

			# Create new certificate
			today = date.today()
			cert_expiry = frappe.db.get_value("Exam", subm["exam"], "expiry")

			new_cert = frappe.get_doc({
				"doctype": "Exam Certificate",
				"exam_submission": subm["name"],
				"exam": subm["exam"],
				"candidate": subm["candidate"],
				"candidate_name": subm["candidate_name"],
				"issue_date": today,
				"certificate_template": frappe.db.get_value("Exam", subm["exam"], "certificate_template")
			})
			
			if cert_expiry:
				cert_expiry *= 365
				new_cert.expiry_date = today + timedelta(days=cert_expiry)
			
			new_cert.insert()
			certificates_sent += 1

		except Exception as e:
			errors.append(f"Error creating certificate for {subm['candidate_name']}: {str(e)}")

	# Prepare result message
	result_parts = []
	result_parts.append(f"Certificates sent: {certificates_sent}")
	
	if certificates_already_exist:
		result_parts.append(f"Certificates already existed: {certificates_already_exist}")
	
	if errors:
		result_parts.append(f"Errors: {len(errors)}")
		result_parts.extend(errors[:3])  # Show first 3 errors
		if len(errors) > 3:
			result_parts.append(f"... and {len(errors) - 3} more errors")

	result_parts.append(f"Total passed submissions: {len(passed_submissions)}")
	result_parts.append(f"Total submissions: {len(submissions)}")

	return "\n".join(result_parts)

@frappe.whitelist()
def get_server_status(schedule_name):
	"""Get the status of an exam schedule for the list view"""
	try:
		doc = frappe.get_doc("Exam Schedule", schedule_name)
		status = doc.get_status()
		frappe.logger().info(f"get_server_status for {schedule_name}: {status}")
		return status
	except Exception as e:
		frappe.logger().error(f"Error in get_server_status for {schedule_name}: {str(e)}")
		return "Error"

def get_schedule_status(exam_schedule, additional_time=0):
	"""
	Calculate and return the status of the exam schedule.
	:param additional_time: Optional minutes to adjust the end time for status calculation.
	Returns the status of the exam schedule based on the current time and start date time.
	- "Upcoming" if the current time is before the start date time.
	- "Ongoing" if the current time is between the start date time and end date time.
	- "Completed" if the current time is after the end date time.
	"""
	start_date_time, schedule_type, duration, schedule_expire_in_days = frappe.get_value(
		"Exam Schedule", exam_schedule, 
		["start_date_time", "schedule_type", "duration", "schedule_expire_in_days"]
	)
	current_time = datetime.now()
	
	# Calculate end time based on schedule type
	if schedule_type == "Fixed":
		end_time = start_date_time + timedelta(minutes=duration or 0)
	else:
		# For flexible schedules, we consider the end time as start time + duration + days
		days = schedule_expire_in_days or 0
		end_time = start_date_time + timedelta(minutes=duration or 0, days=days)
	
	# If additional_time is provided, adjust the end time
	if additional_time:
		end_time += timedelta(minutes=additional_time)
	
	# Determine status
	status = None
	if current_time < start_date_time:
		status = "Upcoming"
	elif start_date_time <= current_time <= end_time:
		status = "Ongoing"
	else:
		status = "Completed"
		
	return status

def get_schedule_end_time(exam_schedule, additional_time=0):
	"""
	Get the end time of the exam schedule based on its type and additional time.
	:param additional_time: Optional minutes to adjust the end time.
	Returns the end time as a datetime object.
	"""
	start_date_time, schedule_type, duration, schedule_expire_in_days = frappe.get_value(
		"Exam Schedule", exam_schedule, 
		["start_date_time", "schedule_type", "duration", "schedule_expire_in_days"]
	)
	
	if not isinstance(start_date_time, datetime):
		start_date_time = parse(start_date_time) if start_date_time else datetime.now()
	
	if schedule_type == "Fixed":
		end_time = start_date_time + timedelta(minutes=duration or 0)
	else:
		end_time = start_date_time + timedelta(minutes=duration or 0, days=schedule_expire_in_days or 0)
	
	if additional_time:
		end_time += timedelta(minutes=additional_time)
	
	return end_time

@frappe.whitelist()
def recompute_results_for_schedule(schedule):
	"""
	Recompute results for all submissions in the given exam schedule.
	This will update the total marks, evaluation status, and result status for each submission.
	"""
	sched = frappe.get_doc("Exam Schedule", schedule, ignore_permissions=True)
	# get max additional time given for submissions in this schedule
	max_additional_time = frappe.db.get_value("Exam Submission", {"exam_schedule": schedule}, "max(additional_time_given)") or 0
	if sched.get_status(additional_time=max_additional_time) != "Completed":
		frappe.throw("Cannot recompute results since the exam schedule is not completed.")

	submissions = frappe.get_all(
		"Exam Submission", 
		filters={"exam_schedule": schedule},
		fields=["name", "exam", "additional_time_given"]
	)
	for submission in submissions:
		doc = frappe.get_doc("Exam Submission", submission["name"], ignore_permissions=True)
		if doc.status == "Started":
			doc.status = "Submitted"
		elif doc.status == "Registered":
			doc.status = "Not Attempted"
		total_marks, evaluation_status, result_status = evaluation_values(
			doc.exam, doc.submitted_answers
		)
		doc.total_marks = total_marks
		doc.evaluation_status = evaluation_status
		doc.result_status = result_status
		doc.save()
		frappe.db.commit()

