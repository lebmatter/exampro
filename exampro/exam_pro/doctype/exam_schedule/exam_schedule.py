# Copyright (c) 2024, Labeeb Mattra and contributors
# For license information, please see license.txt

from datetime import timedelta, datetime, date
from dateutil.parser import parse
import frappe
import base64

from frappe.utils import now
from frappe.model.document import Document


class ExamSchedule(Document):

	# Add status to standard fields
	_standard_fieldnames = ['name', 'owner', 'creation', 'modified', 'modified_by',
		'parent', 'parentfield', 'parenttype', 'idx', 'docstatus',
		'naming_series', 'status']

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
		
		# validate examiner list
		self.validate_examiner_list()

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

	def validate_examiner_list(self):
		"""
		get all the other exams which falls in the current exam's timeframe
		make sure that there is no conflicting proctor.
		Conflicting evaluator is fine, since they are not time bound.
		
		Also checks if examiners have the appropriate roles based on their assigned flags,
		and assigns those roles if needed.
		"""
		if not self.examiners:
			return
		
		if not isinstance(self.start_date_time, datetime):
			exam_start = parse(self.start_date_time)
		else:
			exam_start = self.start_date_time
		end_time = exam_start + timedelta(minutes=self.duration)
		other_exams = frappe.get_all(
			"Exam Schedule",
			filters=[["start_date_time", ">=", exam_start]],
			fields=["name", "duration", "start_date_time"], 
		)

		for exam2 in other_exams:
			if exam2["name"] == self.name:
				continue

			examiners1 = [ex.examiner for ex in self.examiners]
			exam2_end = exam2["start_date_time"] + timedelta(minutes=exam2["duration"])
			if check_overlap(exam_start, end_time, exam2["start_date_time"], exam2_end):
				examiners2 = frappe.db.get_all(
					"Examiner",
					filters={"parent": self.name, "can_proctor": 1},
					fields=["examiner"]
				)
				examiners2 = [ex.examiner for ex in examiners2]
				# check if any examiner in the 2nd list
				overlap = set(examiners1).intersection(set(examiners2))
				if overlap:
					frappe.throw(
						"Can't add {} as proctor(s). Overlap found with schedule {}".format(
							overlap, exam2["name"]
						))
			
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
			
		# Encode the schedule name in base64
		encoded_name = base64.b64encode(self.name.encode('utf-8')).decode('utf-8')
		
		# Create the invite link
		invite_link = f"{domain}/exam/invite/{encoded_name}"
		
		# Update the document
		self.schedule_invite_link = invite_link
		self.save(ignore_permissions=True)
		
		return invite_link
	
def check_overlap(start_time1, end_time1, start_time2, end_time2):
	assert isinstance(start_time1, datetime), "start_time1 must be a datetime object"
	assert isinstance(end_time1, datetime), "end_time1 must be a datetime object"
	assert isinstance(start_time2, datetime), "start_time2 must be a datetime object"
	assert isinstance(end_time2, datetime), "end_time2 must be a datetime object"

	# Check if Period 1 starts before Period 2 ends AND Period 1 ends after Period 2 starts
	return start_time1 < end_time2 and end_time1 > start_time2


def _submit_pending_exams(schedule_name):
	"""
	submit exams if pendding
	"""	
	submissions = frappe.get_all(
		"Exam Submission", 
		filters={"exam_schedule": schedule_name},
		fields=["name", "result_status", "status", "total_marks", "exam", "candidate", "candidate_name"]
	)
	for subm in submissions:
		if subm["status"] in ["Submitted", "Terminated", "Registered"]:
			continue
		doc = frappe.get_doc("Exam Submission", subm["name"])
		doc.status = "Submitted"
		doc.exam_submitted_time = datetime.now()
		doc.save(ignore_permissions=True)


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
	if not doc.can_end_schedule():
		return

	_submit_pending_exams(docname)
	has_certification = frappe.db.get_value("Exam", doc.exam, "enable_certification")
	if has_certification:
		_send_certificates(docname)

	return "Success"

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