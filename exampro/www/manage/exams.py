import frappe
from frappe import _

import frappe
from frappe import _

@frappe.whitelist()
def duplicate_exam(exam):
    """
    Duplicate an exam with all its questions
    
    Args:
        exam (str): Name of the exam to duplicate
    """
    if not frappe.has_permission("Exam", "write"):
        return {"success": False, "error": _("Not permitted")}
    
    try:
        # Get the original exam
        source = frappe.get_doc("Exam", exam)
        
        # Create a new exam with the same properties
        new_exam = frappe.copy_doc(source)
        new_exam.title = f"{source.title} (Copy)"
        new_exam.published = 0  # Set as unpublished by default
        new_exam.insert()
        
        # Copy the question references
        for question in source.added_questions:
            new_exam.append("added_questions", {
                "exam_question": question.exam_question,
                "mark": question.mark
            })
        
        new_exam.save()
        frappe.db.commit()
        
        return {"success": True, "name": new_exam.name}
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error duplicating exam {exam}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def delete_exam(exam):
    """
    Delete an exam
    
    Args:
        exam (str): Name of the exam to delete
    """
    if not frappe.has_permission("Exam", "delete"):
        return {"success": False, "error": _("Not permitted")}
    
    try:
        # Check if exam can be deleted (no schedules or submissions)
        schedules = frappe.get_all("Exam Schedule", filters={"exam": exam})
        if schedules:
            return {"success": False, "error": _("Cannot delete exam with existing schedules")}
        
        # Delete the exam
        frappe.delete_doc("Exam", exam)
        frappe.db.commit()
        
        return {"success": True}
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error deleting exam {exam}")
        return {"success": False, "error": str(e)}


def get_exams():
    """Get all exams with relevant details"""
    
    # Check if user has permission to view Exams
    if not frappe.has_permission("Exam", "read"):
        return []
    
    # Get all exams
    exams = frappe.get_all(
        "Exam",
        fields=[
            "name", 
            "title", 
            "duration", 
            "total_questions", 
            "total_marks", 
            "published",
            "upcoming"
        ]
    )
    
    return exams

def get_context(context):
    """Setup page context"""
    
    # Redirect guest users to login
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect
    
    # Check if user has Exam Manager role
    if not "Exam Manager" in frappe.get_roles(frappe.session.user):
        frappe.throw(_("You are not authorized to access this page"))

    # Set page data
    context.no_cache = 1
    context.exams = get_exams()
    
    context.metatags = {
        "title": _("Manage Exams"),
        "description": "Manage exam system exams and configurations"
    }
