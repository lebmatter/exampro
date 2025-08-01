import frappe
from frappe import _

from exampro.exam_pro.api.utils import submit_candidate_pending_exams

def get_context(context):
    """
    Handle exam invite context
    """
    # Check if invite code is provided
    invite_code = frappe.form_dict.get("invite_code")
    if not invite_code:
        context.invite_valid = False
        context.message = _("Invalid invitation link. No invitation code provided.")
        return context

    if frappe.session.user == "Guest":
        # Use Frappe's native redirect to login with return URL
        frappe.local.flags.redirect_location = f"/login?redirect-to={frappe.local.request.path}"
        raise frappe.Redirect

    # Check if submission already exists for this user and schedule
    if frappe.session.user != "Administrator":
        # Check if user has Exam Candidate role, add if not present
        user_roles = frappe.get_roles(frappe.session.user)
        if "Exam Candidate" not in user_roles:
            user = frappe.get_doc("User", frappe.session.user)
            user.append("roles", {
                "role": "Exam Candidate"
            })
            user.save(ignore_permissions=True)
            frappe.db.commit()    

    submit_candidate_pending_exams()
    
    try:
        # Look up the exam schedule by short_uuid
        schedule_name = frappe.db.get_value("Exam Schedule", {"short_uuid": invite_code}, "name")
        
        if not schedule_name:
            context.message = _("Invalid invitation link. The invitation code could not be found.")
            context.invite_valid = False
            return context
        
        # Get the exam schedule document
        schedule = frappe.get_doc("Exam Schedule", schedule_name)
        
        # Ensure the schedule exists and is valid
        if not schedule:
            context.message = _("Invalid invitation link.")
            return context
        if not schedule.schedule_invite_link:
            context.message = _("Invalid invitation link.")
            return context
        if schedule.get_status() == "Completed":
            context.message = _("This exam schedule has already been completed.")
            return context
        else:
            context.has_submission = False
            context.submission_id = None
        
        # Get the exam data
        exam = frappe.get_doc("Exam", schedule.exam)
        
        # Set context variables for the template
        context.exam_schedule = schedule
        context.exam = exam
        context.schedule_name = schedule_name
        context.invite_code = invite_code
        context.invite_valid = True
        context.status = schedule.get_status()
        
        # Check if user is logged in
        context.is_logged_in = frappe.session.user != "Guest"
        
        existing_submission = frappe.db.exists("Exam Submission", {
            "exam_schedule": schedule_name,
            "candidate": frappe.session.user
        })
        context.has_submission = bool(existing_submission)
        context.submission_id = existing_submission if existing_submission else None
            
    except Exception as e:
        frappe.log_error(f"Error processing exam invite: {str(e)}")
        context.message = _("There was an error processing your invitation. Please contact the administrator.")
        
    return context

@frappe.whitelist()
def accept_invitation(schedule_name):
    """
    Create a new exam submission for the current user
    """
    if frappe.session.user == "Guest":
        frappe.throw(_("Please login to accept the invitation."), frappe.AuthenticationError)
    
    try:
        # Check if a submission already exists
        existing_submission = frappe.db.exists("Exam Submission", {
            "exam_schedule": schedule_name,
            "candidate": frappe.session.user
        })
        
        if existing_submission:
            return {
                "success": True, 
                "message": _("You have already accepted this invitation."),
                "submission_id": existing_submission
            }
            
        # Get the schedule and exam
        schedule = frappe.get_doc("Exam Schedule", schedule_name)
        
        # Create new submission
        submission = frappe.new_doc("Exam Submission")
        submission.exam_schedule = schedule_name
        submission.exam = schedule.exam
        submission.candidate = frappe.session.user
        submission.status = "Registered"
        submission.insert(ignore_permissions=True)
        
        return {
            "success": True, 
            "message": _("Invitation accepted successfully."),
            "submission_id": submission.name
        }
        
    except Exception as e:
        frappe.log_error(f"Error accepting exam invitation: {str(e)}")
        return {"success": False, "message": _("Error accepting invitation. Please try again.")}
