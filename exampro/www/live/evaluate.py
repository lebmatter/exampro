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
			"exam_schedule"
		]
	)

	for submission in submissions:
		exam = frappe.get_doc("Exam", submission.exam)
		submission.title = exam.title
		submission.name = exam.name  # This is needed for the data-exam-id in template

	return submissions

def get_context(context):
	context.no_cache = 1

	if frappe.session.user == "Guest":
		raise frappe.PermissionError(_("Please login to access this page."))
		
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
	
	# Get max marks for each question
	for answer in answers:
		max_marks = frappe.db.get_value("Exam Question", answer.exam_question, "mark")
		answer.max_marks = max_marks
	
	return {
		"success": True,
		"answers": answers
	}

@frappe.whitelist()
def save_marks(question_id, marks, submission_id, feedback=None):
	"""Save marks for a question"""        
	submission = frappe.get_doc("Exam Submission", submission_id)
	
	# Verify if the user is assigned as evaluator
	if submission.assigned_evaluator != frappe.session.user:
		frappe.throw(_("You are not assigned to evaluate this submission"))
	
	# Find the answer record
	answer = frappe.get_doc("Exam Answer", {
		"parent": submission_id,
		"exam_question": question_id
	})
	
	# Update evaluation details
	answer.mark = float(marks)
	answer.evaluator_response = feedback
	answer.evaluator = frappe.session.user
	answer.evaluation_status = "Done"
	answer.save()
	
	# Update total marks in submission
	update_total_marks(submission_id)
	
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

def update_total_marks(submission_id):
	"""Update total obtained marks in submission"""
	total_marks = frappe.db.sql("""
		SELECT SUM(mark) as total
		FROM `tabExam Answer`
		WHERE parent = %s
	""", submission_id)[0][0] or 0
	
	frappe.db.set_value("Exam Submission", submission_id, "obtained_marks", total_marks)
	
	# Update evaluation_pending count 
	pending_count = frappe.db.count("Exam Answer", {
		"parent": submission_id,
		"evaluation_status": ["in", ["Not Attempted", "Pending"]]
	})
	
	frappe.db.set_value("Exam Submission", submission_id, "evaluation_pending", pending_count)
