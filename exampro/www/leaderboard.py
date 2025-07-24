# Copyright (c) 2024, Labeeb Mattra and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def get_context(context):
    """Context for the HTML page with submission-specific routing"""
    
    # Get submission ID from URL path
    path_parts = frappe.local.request.path.strip('/').split('/')
    if len(path_parts) < 2:
        frappe.throw(_("Submission ID not specified in URL"))
    
    submission_id = path_parts[1]  # /leaderboard/<submission_id>
    
    # Check if user is logged in
    if frappe.session.user == "Guest":
        frappe.throw(_("Please login to view the leaderboard"), frappe.AuthenticationError)
    
    # Check if submission exists and get exam details
    if not frappe.db.exists("Exam Submission", submission_id):
        frappe.throw(_("Exam submission '{0}' not found").format(submission_id))
    

    # Get submission details
    user_submission_doc = frappe.get_doc("Exam Submission", submission_id)
    exam_name = user_submission_doc.exam

    # Check if this submission belongs to the current user
    if user_submission_doc.candidate != frappe.session.user:
        context.error_message = _("You don't have permission to view this leaderboard.")
        context.show_error = True
        context.title = _("Access Restricted")
        context.show_sidebar = False
        return context
    
    # Get exam details
    exam_doc = frappe.get_doc("Exam", exam_name)
    
    # Check leaderboard settings
    if exam_doc.leaderboard == "No Leaderboard":
        context.error_message = _("Leaderboard is not enabled for this exam.")
        context.show_error = True
        context.title = _("Leaderboard Disabled")
        context.show_sidebar = False
        return context
    
    # Set context variables
    context.title = _("Leaderboard - {0}").format(exam_doc.title)
    context.show_sidebar = False
    context.exam = {
        "name": exam_doc.name,
        "title": exam_doc.title,
        "description": exam_doc.description,
        "leaderboard_type": exam_doc.leaderboard,
        "leaderboard_rows": exam_doc.leaderboard_rows or 10,
        "total_marks": exam_doc.total_marks,
        "pass_percentage": exam_doc.pass_percentage,
        "image": exam_doc.image
    }
    # calculate percentage
    if user_submission_doc.total_marks and exam_doc.total_marks:
        percentage = (user_submission_doc.total_marks / exam_doc.total_marks) * 100
    else:
        percentage = 0.0
    context.user_submission = {
        "total_marks": user_submission_doc.total_marks or 0,
        "percentage": percentage,
        "result_status": user_submission_doc.result_status,
        "exam_schedule": user_submission_doc.exam_schedule
    }
    context.show_error = False
    
    # Get leaderboard data
    # try:
    leaderboard_data = get_leaderboard_data_internal(
        exam_name, 
        exam_doc.leaderboard, 
        exam_doc.leaderboard_rows or 10,
        user_submission_doc.exam_schedule if exam_doc.leaderboard == "Schedule Level" else None
    )
    context.leaderboard_data = leaderboard_data["data"]
    context.stats = leaderboard_data["stats"]
    
    # Find user's rank
    context.user_rank = find_user_rank(leaderboard_data["data"], frappe.session.user)
        
    # except Exception as e:
    #     frappe.log_error(f"Error loading leaderboard data: {str(e)}")
    #     context.error_message = _("Error loading leaderboard data. Please try again later.")
    #     context.show_error = True
    
    return context

def find_user_rank(leaderboard_data, user):
    """Find the current user's rank in the leaderboard"""
    for index, submission in enumerate(leaderboard_data, 1):
        if submission.get("candidate") == user:
            return index
    return None

def get_leaderboard_data_internal(exam, leaderboard_type, limit=10, schedule=None):
    """Internal function to get leaderboard data"""
    
    # Build filters based on leaderboard type
    filters = {
        "exam": exam,
        "status": "Submitted",
        "result_status": ["in", ["Passed", "Failed"]]  # Only include evaluated submissions
    }
    
    if leaderboard_type == "Schedule Level" and schedule:
        filters["exam_schedule"] = schedule
    
    # Get submissions with candidate details
    submissions = frappe.get_all(
        "Exam Submission",
        filters=filters,
        fields=[
            "name",
            "candidate",
            "candidate_name", 
            "total_marks",
            "result_status",
            "modified as completion_time",
            "exam_schedule"
        ],
        order_by="total_marks desc, modified asc",
        limit=int(limit)
    )
    
    # Get exam max marks for display
    exam_doc = frappe.get_doc("Exam", exam)
    max_marks = exam_doc.total_marks or 0
    
    # Add max marks to each submission and calculate percentage
    for submission in submissions:
        submission["max_marks"] = max_marks
        
        # Calculate percentage from total_marks and max_marks
        if submission.get("total_marks") and max_marks:
            submission["percentage"] = (submission["total_marks"] / max_marks) * 100
        else:
            submission["percentage"] = 0.0
        
        # Format completion time
        if submission.get("completion_time"):
            submission["completion_time"] = frappe.utils.format_datetime(
                submission["completion_time"], "dd MMM yyyy, hh:mm a"
            )

    # Calculate statistics
    stats = calculate_stats(filters, exam_doc.pass_percentage or 50)
    return {
        "data": submissions,
        "stats": stats
    }

def calculate_stats(filters, pass_percentage):
    """Calculate leaderboard statistics"""
    
    # Get all submissions matching filters
    all_submissions = frappe.get_all(
        "Exam Submission",
        filters=filters,
        fields=["total_marks", "result_status"]
    )
    
    if not all_submissions:
        return {
            "total_participants": 0,
            "average_score": 0,
            "highest_score": 0,
            "pass_rate": 0
        }
    
    # Get exam max marks for percentage calculation
    exam = filters.get("exam")
    max_marks = frappe.get_value("Exam", exam, "total_marks") or 1  # Avoid division by zero
    
    # Calculate statistics
    total_participants = len(all_submissions)
    
    # Calculate percentages from total_marks
    percentages = [(s.get("total_marks") or 0) / max_marks * 100 for s in all_submissions]
    
    average_score = sum(percentages) / total_participants if total_participants > 0 else 0
    highest_score = max(percentages) if percentages else 0
    
    # Calculate pass rate
    passed_count = len([s for s in all_submissions if s.get("result_status") == "Passed"])
    pass_rate = (passed_count / total_participants * 100) if total_participants > 0 else 0
    
    return {
        "total_participants": total_participants,
        "average_score": average_score,
        "highest_score": highest_score,
        "pass_rate": pass_rate
    }