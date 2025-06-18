import frappe
from frappe import _

# ACTIVE_EXAM_CODE_CACHE = "ACTIVEEXAMCODECACHE"

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
	assigned_evaluator = frappe.db.get_value("Exam Submission", submission_id, "assigned_evaluator")
	if assigned_evaluator != frappe.session.user:
		frappe.throw("You are not authorized to evaluate exams")
		
	submission = frappe.get_doc("Exam Submission", submission_id)
	
	# Verify if the user is assigned as evaluator
	if submission.assigned_evaluator != frappe.session.user:
		frappe.throw(_("You are not assigned to evaluate this submission"))
		
	exam = frappe.get_doc("Exam", exam_id)
	
	context = {
		"exam": exam,
		"submission": submission,
		"answers": get_submission_answers(submission_id)
	}
	
	html = frappe.render_template(
		"templates/exam/evaluation_form.html",
		context
	)
	
	return {
		"success": True,
		"html": html
	}

@frappe.whitelist()
def save_marks(question_id, marks, submission_id, feedback=None):
	"""Save marks for a question"""		
	submission = frappe.get_doc("Exam Submission", submission_id)
	
	# Verify if the user is assigned as evaluator
	if submission.assigned_evaluator != frappe.session.user:
		frappe.throw(_("You are not assigned to evaluate this submission"))
	
	# Get or create evaluation record
	evaluation = frappe.get_doc({
		"doctype": "Exam Evaluation",
		"submission": submission_id,
		"question": question_id,
		"marks": marks,
		"feedback": feedback,
		"evaluated_by": frappe.session.user
	})
	
	evaluation.save()
	
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
		"Exam Evaluation",
		filters={"submission": submission_id},
		fields=["question", "marks", "feedback"]
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
		fields=["name", "question", "answer", "is_correct", "mark"]
	)

def update_total_marks(submission_id):
	"""Update total obtained marks in submission"""
	total_marks = frappe.db.sql("""
		SELECT SUM(mark) as total
		FROM `tabExam Evaluation`
		WHERE submission = %s
	""", submission_id)[0][0] or 0
	
	frappe.db.set_value("Exam Submission", submission_id, "obtained_marks", total_marks)
