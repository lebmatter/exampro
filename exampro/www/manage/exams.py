import frappe
from frappe import _
from datetime import datetime
from frappe.utils import now

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
        # Delete any associated schedules first
        schedules = frappe.get_all("Exam Schedule", filters={"exam": exam})
        for sched in schedules:
            try:
                # Check if schedule can be deleted (no submissions)
                submissions = frappe.get_all("Exam Submission", filters={"exam_schedule": sched.name})
                if not submissions:
                    frappe.delete_doc("Exam Schedule", sched.name)
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"Error deleting schedule {sched.name}")

        # Delete the exam
        frappe.delete_doc("Exam", exam)
        frappe.db.commit()
        
        return {"success": True}
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error deleting exam {exam}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def duplicate_schedule(schedule):
    """
    Duplicate an exam schedule
    
    Args:
        schedule (str): Name of the schedule to duplicate
    """
    if not frappe.has_permission("Exam Schedule", "write"):
        return {"success": False, "error": _("Not permitted")}
    
    try:
        # Get the original schedule
        source = frappe.get_doc("Exam Schedule", schedule)
        
        # Create a new schedule with the same properties
        new_schedule = frappe.copy_doc(source)
        new_schedule.start_date_time = source.start_date_time  # Copy the date
        new_schedule.name = f"{source.name} (Copy)"
        new_schedule.insert()
        
        # Copy examiners if any
        if hasattr(source, 'examiners'):
            for examiner in source.examiners:
                new_schedule.append("examiners", {
                    "user": examiner.user,
                    "role": examiner.role
                })
            
            new_schedule.save()
        
        frappe.db.commit()
        
        return {"success": True, "name": new_schedule.name}
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error duplicating schedule {schedule}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def delete_schedule(schedule):
    """
    Delete an exam schedule
    
    Args:
        schedule (str): Name of the schedule to delete
    """
    if not frappe.has_permission("Exam Schedule", "delete"):
        return {"success": False, "error": _("Not permitted")}
    
    try:
        # Check if schedule can be deleted (no submissions)
        submissions = frappe.get_all("Exam Submission", filters={"exam_schedule": schedule})
        if submissions:
            return {"success": False, "error": _("Cannot delete schedule with existing submissions")}
        
        # Delete the schedule
        frappe.delete_doc("Exam Schedule", schedule)
        frappe.db.commit()
        
        return {"success": True}
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error deleting schedule {schedule}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def get_schedules_for_exam(exam):
    """
    Get all schedules for a given exam with registered user count.
    
    Args:
        exam (str): Name of the exam to get schedules for.
    """
    if not frappe.has_permission("Exam Schedule", "read"):
        frappe.throw(_("Not permitted to read Exam Schedules"), frappe.PermissionError)

    schedules = frappe.get_all(
        "Exam Schedule",
        filters={"exam": exam},
        fields=["name", "start_date_time"]
    )

    for sched in schedules:
        schedule_doc = frappe.get_doc("Exam Schedule", sched.name)
        sched["status"] = schedule_doc.get_status()
        
        # Get user count from exam submissions for this schedule
        submission_count = frappe.db.count(
            "Exam Submission", 
            filters={"exam_schedule": sched.name}
        )
        
        sched["registered_users"] = submission_count

    return schedules

def get_exams_with_schedules():
    """Get all exams with their associated schedules"""
    
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
            "upcoming"
        ]
    )
    
    total_schedules = 0
    
    # For each exam, get its schedules
    for exam in exams:
        schedules = frappe.get_all(
            "Exam Schedule",
            filters={"exam": exam.name},
            fields=[
                "name", 
                "exam",
                "visibility", 
                "start_date_time", 
                "duration"
            ]
        )
        # update status in schedules
        for sched in schedules:
            sched_doc = frappe.get_doc("Exam Schedule", sched.name)
            sched["status"] = sched_doc.get_status()        
        exam["schedules"] = schedules
        total_schedules += len(schedules)
    
    return exams, total_schedules

def get_context(context):
    """Setup page context"""
    
    # Redirect guest users to login
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect
    
    # Check if user has Exam Manager role
    if "Exam Manager" not in frappe.get_roles(frappe.session.user):
        frappe.throw(_("You are not authorized to access this page"))
    
    # Set page data
    context.no_cache = 1
    context.exams, context.total_schedules = get_exams_with_schedules()
    
    context.metatags = {
        "title": _("Manage Exams & Schedules"),
        "description": "Manage exams and exam schedules"
    }
