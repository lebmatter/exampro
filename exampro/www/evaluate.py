import frappe
from frappe import _

def get_evaluator_live_exams(evaluator=None):
	"""
	Get upcoming/ongoing exam of an evaluator.
	Shows submissions ready for evaluation only after exam schedule has ended.
	"""
	evaluator = evaluator or frappe.session.user
	submissions = frappe.get_all(
		"Exam Submission",
		filters={
			"assigned_evaluator": evaluator,
			"evaluation_pending": [">", 0],
			"status": "Submitted"
		},
		fields=[
			"name as submission_id", 
			"exam", 
			"candidate_name",
			"status",
			"evaluation_pending",
			"exam_schedule",
			"exam_submitted_time",
		]
	)
	res = []

	for submission in submissions:
		exam = frappe.get_doc("Exam", submission.exam)
		# default 3 days for evaluation
		evaluation_ends_days = frappe.db.get_value("Exam", exam.name,  "evaluation_ends_in_days") or 3
		# end time is exam_submitted time + evaluation_ends_days 
		evaluation_end_time = frappe.utils.add_days(submission.exam_submitted_time, evaluation_ends_days)
		if evaluation_end_time < frappe.utils.now_datetime():
			continue

		submission.title = exam.title
		submission.name = exam.name  # This is needed for the data-exam-id in template
		res.append(submission)

	return res

def get_context(context):
	context.no_cache = 1

	if frappe.session.user == "Guest":
		raise frappe.PermissionError(_("Please login to access this page."))
	if "Exam Evaluator" not in frappe.get_roles():
		raise frappe.PermissionError("You are not authorized to access this page")


		
	# Get assigned exams for the evaluator
	context.assigned_exams = get_evaluator_live_exams()
	
	context.page_context = {}

@frappe.whitelist()
def get_submission_details(exam_id, submission_id):
	"""Get exam submission details for evaluation"""
	# Verify if the user is assigned as evaluator
	assigned_evaluator = frappe.db.get_value("Exam Submission", submission_id, "assigned_evaluator")
	if assigned_evaluator != frappe.session.user:
		frappe.throw("You are not authorized to evaluate this exam")
	
	# Get all answers with their evaluation status
	answers = frappe.get_all(
		"Exam Answer",
		filters={"parent": submission_id},
		fields=[
			"name",
			"seq_no",
			"exam_question", 
			"question",
			"answer",
			"is_correct",
			"evaluation_status",
			"evaluator",
			"evaluator_response",
			"mark"
		],
		order_by="seq_no"
	)
	
	# Get max marks and question type for each question
	for answer in answers:
		question_data = frappe.db.get_value("Exam Question", answer.exam_question, ["mark", "type"], as_dict=True)
		answer.max_marks = question_data.mark
		answer.question_type = question_data.type
	
	return {
		"success": True,
		"answers": answers
	}

@frappe.whitelist()
def save_marks(question_id, marks, submission_id, feedback=None):
	"""Save marks for a question"""        
	submission = frappe.get_doc("Exam Submission", submission_id)
	# Validate input
	if not question_id or not marks or not submission_id:
		frappe.throw(_("Question name, marks, and submission ID are required"))

	# if marks is str, convert to float
	if isinstance(marks, str):
		try:
			marks = float(marks)
		except ValueError:
			frappe.throw(_("Marks must be a valid number"))
	if not isinstance(marks, (int, float)):
		frappe.throw(_("Marks must be a number"))

	# Verify if the user is assigned as evaluator
	if submission.assigned_evaluator != frappe.session.user:
		frappe.throw(_("You are not assigned to evaluate this submission"))

	# check max mark
	max_marks = frappe.get_cached_value(
		"Exam Question", question_id, "mark"
	)
	if marks > max_marks:
		frappe.throw(_("Marks cannot be greater than the maximum marks for this question: {0}").format(max_marks))
	
	# Find the answer record
	result_doc = frappe.get_doc("Exam Answer", "{}-{}".format(submission_id, question_id), ignore_permissions=True)
	# Update evaluation details
	result_doc.mark = float(marks)
	result_doc.evaluator_response = feedback
	result_doc.evaluator = frappe.session.user
	result_doc.evaluation_status = "Done"
	result_doc.save(ignore_permissions=True)


	# Update evaluation_pending count 
	pending_count = frappe.db.get_value("Exam Submission", submission_id, "evaluation_pending")
	frappe.db.set_value("Exam Submission", submission_id, "evaluation_pending", pending_count -1)

	return {
		"success": True,
		"message": "Marks saved successfully"
	}

@frappe.whitelist()
def get_existing_marks(submission_id):
	"""Get existing evaluation marks"""
	submission = frappe.get_doc("Exam Submission", submission_id)
	
	# Verify if the user is assigned as evaluator
	if submission.assigned_evaluator != frappe.session.user:
		frappe.throw(_("You are not assigned to evaluate this submission"))
		
	marks = frappe.get_all(
		"Exam Answer",
		filters={"parent": submission_id},
		fields=["exam_question", "mark", "evaluator_response", "evaluation_status"]
	)
	
	return {
		"success": True,
		"marks": marks
	}

def get_submission_answers(submission_id):
	"""Get all answers for a submission"""
	return frappe.get_all(
		"Exam Answer",
		filters={"parent": submission_id},
		fields=[
			"name", 
			"exam_question", 
			"question", 
			"answer", 
			"is_correct", 
			"evaluation_status",
			"mark",
			"evaluator_response"
		],
		order_by="seq_no"
	)

