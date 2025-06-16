import frappe
from frappe import _
import json

@frappe.whitelist()
def get_submission_details(exam_id, submission_id):
    """Get exam submission details for evaluation"""
    if not frappe.db.exists("Examiner", {"user": frappe.session.user}):
        frappe.throw(_("You are not authorized to evaluate exams"))
        
    submission = frappe.get_doc("Exam Submission", submission_id)
    
    # Verify if the user is assigned as evaluator
    if submission.evaluator != frappe.session.user:
        frappe.throw(_("You are not assigned to evaluate this submission"))
        
    exam = frappe.get_doc("Exam", exam_id)
    
    # Update submission status if needed
    if submission.status == "Submitted":
        submission.status = "Evaluation In Progress"
        submission.save()
    
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
    if not frappe.db.exists("Examiner", {"user": frappe.session.user}):
        frappe.throw(_("You are not authorized to evaluate exams"))
        
    submission = frappe.get_doc("Exam Submission", submission_id)
    
    # Verify if the user is assigned as evaluator
    if submission.evaluator != frappe.session.user:
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
    if not frappe.db.exists("Examiner", {"user": frappe.session.user}):
        frappe.throw(_("You are not authorized to evaluate exams"))
        
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
        fields=["name", "question", "answer", "is_correct", "marks"]
    )

def update_total_marks(submission_id):
    """Update total obtained marks in submission"""
    total_marks = frappe.db.sql("""
        SELECT SUM(marks) as total
        FROM `tabExam Evaluation`
        WHERE submission = %s
    """, submission_id)[0][0] or 0
    
    frappe.db.set_value("Exam Submission", submission_id, "obtained_marks", total_marks)
