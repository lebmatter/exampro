import frappe
from frappe import _
from datetime import datetime
from frappe.utils import now

def get_context(context):
    """
    Handle exam registration page context
    """
    context.no_cache = 1

    # Get exam from URL parameter
    exam_name = frappe.form_dict.get("exam")

    if not exam_name:
        context.show_error = True
        context.error_message = _("No exam specified. Please provide a valid exam.")
        return context

    # Check if exam exists
    if not frappe.db.exists("Exam", exam_name):
        context.show_error = True
        context.error_message = _("Invalid exam. The specified exam does not exist.")
        return context

    # Get exam details
    exam = frappe.get_doc("Exam", exam_name)

    # Check if exam is public
    if exam.visibility != "Public":
        context.show_error = True
        context.error_message = _("This exam is not available for public registration.")
        return context

    context.exam = exam
    context.show_error = False

    # Get available exam schedules for this exam
    schedules = frappe.db.sql("""
        SELECT name, exam, start_date_time, duration, schedule_type, schedule_expire_in_days
        FROM `tabExam Schedule`
        WHERE exam = %s AND public_registration = 1
        ORDER BY start_date_time DESC
    """, exam_name, as_dict=1)

    # Calculate status for each schedule
    available_schedules = []
    for schedule in schedules:
        doc = frappe.get_doc("Exam Schedule", schedule.name)
        status = doc.get_status()
        schedule["status"] = status
        # Only show schedules that are upcoming or ongoing
        if status in ["Upcoming", "Ongoing"]:
            available_schedules.append(schedule)

    context.schedules = available_schedules
    context.has_schedules = len(available_schedules) > 0

    # Check if user is logged in
    context.is_logged_in = frappe.session.user != "Guest"
    context.current_user = frappe.session.user if context.is_logged_in else None

    # Get user details if logged in
    if context.is_logged_in:
        user = frappe.get_doc("User", frappe.session.user)
        context.user_full_name = user.full_name or ""
        context.user_email = user.email or ""
        context.user_phone = user.phone or ""
    else:
        context.user_full_name = ""
        context.user_email = ""
        context.user_phone = ""

    # Get current page URL for login redirect
    from frappe.utils import get_url
    context.current_page_url = get_url(frappe.request.path + "?" + frappe.request.query_string.decode() if frappe.request.query_string else frappe.request.path)

    return context


@frappe.whitelist()
def register_for_exam(schedule_name, name, email, phone):
    """
    Register a candidate for an exam schedule
    """
    if not schedule_name or not name or not email:
        return {
            "success": False,
            "message": _("Schedule, name, and email are required.")
        }

    # Validate email format
    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return {
            "success": False,
            "message": _("Please provide a valid email address.")
        }

    # Check if schedule exists
    if not frappe.db.exists("Exam Schedule", schedule_name):
        return {
            "success": False,
            "message": _("Invalid exam schedule.")
        }

    # Get schedule details
    schedule = frappe.get_doc("Exam Schedule", schedule_name)

    # Check if schedule is open for public registration
    if not schedule.public_registration:
        return {
            "success": False,
            "message": _("This exam schedule is not open for public registration.")
        }

    # Check if associated exam is public
    exam = frappe.get_doc("Exam", schedule.exam)
    if exam.visibility != "Public":
        return {
            "success": False,
            "message": _("This exam is not available for public registration.")
        }

    # Check if schedule is available for registration
    status = schedule.get_status()
    if status not in ["Upcoming", "Ongoing"]:
        return {
            "success": False,
            "message": _("This exam schedule is not available for registration.")
        }

    try:
        # Check if user is logged in
        is_logged_in = frappe.session.user != "Guest"

        if is_logged_in:
            # For logged-in users, use their session email and update their details
            user_email = frappe.session.user
            user = frappe.get_doc("User", user_email)

            # Update user details
            user.full_name = name
            if phone:
                user.phone = phone
            user.save(ignore_permissions=True)
        else:
            # For non-logged-in users, create or get user
            if frappe.db.exists("User", email):
                user_email = email
                # Update phone number and name if provided
                user = frappe.get_doc("User", email)
                user.full_name = name
                if phone:
                    user.phone = phone
                user.save(ignore_permissions=True)
            else:
                # Create new user
                from exampro.exam_pro.doctype.exam_submission.exam_submission import create_website_user
                user_email = create_website_user(name, email)

                # Set phone number if provided
                if phone:
                    frappe.db.set_value("User", user_email, "phone", phone)

        # Ensure user has Exam Candidate role
        user = frappe.get_doc("User", user_email)
        roles = [ro.role for ro in user.roles]
        if "Exam Candidate" not in roles:
            user.add_roles("Exam Candidate")
            user.save(ignore_permissions=True)

        # Check if submission already exists
        existing_submission = frappe.db.exists("Exam Submission", {
            "candidate": user_email,
            "exam_schedule": schedule_name
        })

        if existing_submission:
            return {
                "success": True,
                "message": _("You are already registered for this exam."),
                "submission_id": existing_submission
            }

        # Create new exam submission
        submission = frappe.new_doc("Exam Submission")
        submission.exam_schedule = schedule_name
        submission.exam = schedule.exam
        submission.candidate = user_email
        submission.status = "Registered"
        submission.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "success": True,
            "message": _("Registration successful! You have been registered for the exam."),
            "submission_id": submission.name
        }

    except Exception as e:
        frappe.log_error(f"Error registering candidate: {str(e)}", "register_for_exam")
        return {
            "success": False,
            "message": _("An error occurred during registration. Please try again.")
        }
