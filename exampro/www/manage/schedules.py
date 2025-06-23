import frappe
from frappe import _
from datetime import datetime
from frappe.utils import now

import frappe
from frappe import _
from datetime import datetime
from frappe.utils import now

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


def get_schedule_status(start_time, duration):
    """Determine schedule status based on start time and duration"""
    current_time = datetime.strptime(now(), '%Y-%m-%d %H:%M:%S.%f')
    
    if start_time > current_time:
        return "Upcoming"
    
    end_time = start_time.replace(minute=start_time.minute + duration)
    
    if start_time <= current_time <= end_time:
        return "Ongoing"
    else:
        return "Completed"

def get_schedules():
    """Get all exam schedules with relevant details"""
    
    # Check if user has permission to view Exam Schedules
    if not frappe.has_permission("Exam Schedule", "read"):
        return []
    
    # Get all schedules
    schedules = frappe.get_all(
        "Exam Schedule",
        fields=[
            "name", 
            "exam", 
            "visibility", 
            "start_date_time", 
            "duration"
        ]
    )
    
    # Add status based on time
    for schedule in schedules:
        schedule["status"] = get_schedule_status(
            schedule.start_date_time,
            schedule.duration
        )
    
    return schedules

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
    context.schedules = get_schedules()
    
    context.metatags = {
        "title": _("Manage Exam Schedules"),
        "description": "Manage exam schedules and sessions"
    }
