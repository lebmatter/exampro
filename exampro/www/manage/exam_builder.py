import frappe
from frappe import _
import json

def get_context(context):
    """
    Get context for the exam builder page
    """
    # Check permissions
    if not frappe.has_permission("Exam", "write"):
        frappe.throw(_("Not permitted"), frappe.PermissionError)
        
    context.exams = frappe.get_list("Exam", fields=["name", "title"], order_by="creation desc")
    return context

@frappe.whitelist()
def get_exam_details(exam):
    """
    Get detailed information about an exam
    
    Args:
        exam (str): Name of the exam to get details for
    """
    if not frappe.has_permission("Exam", "read"):
        return {"success": False, "error": _("Not permitted")}
    
    try:
        exam_doc = frappe.get_doc("Exam", exam)
        return exam_doc.as_dict()
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error fetching exam details for {exam}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def get_exam_questions(exam):
    """
    Get questions associated with an exam
    
    Args:
        exam (str): Name of the exam to get questions for
    """
    if not frappe.has_permission("Exam", "read"):
        return {"success": False, "error": _("Not permitted")}
    
    try:
        exam_doc = frappe.get_doc("Exam", exam)
        questions = []
        
        for q in exam_doc.added_questions:
            question_doc = frappe.get_doc("Exam Question", q.exam_question)
            questions.append({
                "exam_question": q.exam_question,
                "question_text": question_doc.question,
                "mark": q.mark
            })
        
        return questions
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error fetching questions for exam {exam}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def get_exam_schedules(exam):
    """
    Get schedules associated with an exam
    
    Args:
        exam (str): Name of the exam to get schedules for
    """
    if not frappe.has_permission("Exam Schedule", "read"):
        return {"success": False, "error": _("Not permitted")}
    
    try:
        schedules = frappe.get_list(
            "Exam Schedule",
            filters={"exam": exam},
            fields=["name", "start_date_time", "visibility", "status"],
            order_by="creation desc"
        )
        
        # Add formatted name
        for s in schedules:
            s["schedule_name"] = s.name
            
        return schedules
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error fetching schedules for exam {exam}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def get_schedule_details(schedule):
    """
    Get detailed information about a schedule
    
    Args:
        schedule (str): Name of the schedule to get details for
    """
    if not frappe.has_permission("Exam Schedule", "read"):
        return {"success": False, "error": _("Not permitted")}
    
    try:
        schedule_doc = frappe.get_doc("Exam Schedule", schedule)
        return schedule_doc.as_dict()
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error fetching schedule details for {schedule}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def get_available_questions():
    """
    Get all available exam questions
    """
    if not frappe.has_permission("Exam Question", "read"):
        return {"success": False, "error": _("Not permitted")}
    
    try:
        questions = frappe.get_list(
            "Exam Question",
            fields=["name", "question", "question_type", "marks", "published"],
            filters={"published": 1},
            order_by="creation desc"
        )
        
        result = []
        for q in questions:
            result.append({
                "name": q.name,
                "question_text": q.question,
                "question_type": q.question_type,
                "marks": q.marks
            })
        
        return result
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error fetching available questions")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def get_users():
    """
    Get all users who can be assigned as examiners
    """
    if not frappe.has_permission("User", "read"):
        return {"success": False, "error": _("Not permitted")}
    
    try:
        users = frappe.get_list(
            "User",
            fields=["name", "full_name", "email"],
            filters={"enabled": 1},
            order_by="full_name asc"
        )
        
        return users
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error fetching users")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def get_registrations(schedule):
    """
    Get all registrations for a schedule
    
    Args:
        schedule (str): Name of the schedule to get registrations for
    """
    if not frappe.has_permission("Exam Schedule", "read"):
        return {"success": False, "error": _("Not permitted")}
    
    try:
        # Example query - adjust based on your actual schema
        registrations = frappe.get_list(
            "Exam Registration", 
            filters={"exam_schedule": schedule},
            fields=["name", "user", "email", "status", "creation"]
        )
        
        # Enrich with user info
        for reg in registrations:
            if reg.user:
                user_doc = frappe.get_doc("User", reg.user)
                reg["user_name"] = user_doc.full_name
                
        return registrations
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error fetching registrations for schedule {schedule}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def add_registration(schedule, email):
    """
    Add a new registration to a schedule
    
    Args:
        schedule (str): Name of the schedule
        email (str): Email of the user to register
    """
    if not frappe.has_permission("Exam Schedule", "write"):
        return {"success": False, "error": _("Not permitted")}
    
    try:
        # Check if user exists
        user = frappe.get_list("User", filters={"email": email}, limit=1)
        
        if not user:
            # Create a new user if not exists
            user_doc = frappe.get_doc({
                "doctype": "User",
                "email": email,
                "first_name": email.split("@")[0],
                "send_welcome_email": 0
            })
            user_doc.insert()
            user_name = user_doc.name
        else:
            user_name = user[0].name
            
        # Check if already registered
        existing = frappe.get_list(
            "Exam Registration",
            filters={"exam_schedule": schedule, "user": user_name},
            limit=1
        )
        
        if existing:
            return {"success": False, "error": _("User is already registered for this exam")}
            
        # Create registration
        reg_doc = frappe.get_doc({
            "doctype": "Exam Registration",
            "exam_schedule": schedule,
            "user": user_name,
            "email": email,
            "status": "Registered"
        })
        reg_doc.insert()
        
        # Get user details for the response
        user_details = frappe.get_doc("User", user_name)
        
        return {
            "success": True,
            "user": {
                "user": user_name,
                "user_name": user_details.full_name,
                "email": email,
                "status": "Registered",
                "creation": reg_doc.creation
            }
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error adding registration for {email} to schedule {schedule}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def remove_registration(schedule, user):
    """
    Remove a registration from a schedule
    
    Args:
        schedule (str): Name of the schedule
        user (str): User to remove
    """
    if not frappe.has_permission("Exam Schedule", "write"):
        return {"success": False, "error": _("Not permitted")}
    
    try:
        # Find registration
        registrations = frappe.get_list(
            "Exam Registration",
            filters={"exam_schedule": schedule, "user": user}
        )
        
        if not registrations:
            return {"success": False, "error": _("Registration not found")}
            
        # Delete registration
        for reg in registrations:
            frappe.delete_doc("Exam Registration", reg.name)
            
        return {"success": True}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error removing registration for user {user} from schedule {schedule}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def save_exam_builder_data(data):
    """
    Save all exam builder data
    
    Args:
        data (dict): Data from the exam builder form
    """
    if not frappe.has_permission("Exam", "write") or not frappe.has_permission("Exam Schedule", "write"):
        return {"success": False, "error": _("Not permitted")}
    
    try:
        if isinstance(data, str):
            data = json.loads(data)
        
        # Begin a database transaction
        frappe.db.begin()
        
        # Process exam data
        exam_name = None
        if data.get("exam", {}).get("type") == "existing":
            exam_name = data["exam"]["name"]
        else:
            # Create new exam
            exam_doc = frappe.new_doc("Exam")
            exam_doc.title = data["exam"]["title"]
            exam_doc.duration = data["exam"]["duration"]
            exam_doc.pass_percentage = data["exam"]["pass_percentage"]
            
            if data["exam"].get("candidates_per_exam"):
                exam_doc.candidates_per_exam = data["exam"]["candidates_per_exam"]
                
            exam_doc.video_link = data["exam"].get("video_link")
            # Note: Image would require additional processing
            
            exam_doc.published = data["exam"].get("published", 0)
            exam_doc.upcoming = data["exam"].get("upcoming", 0)
            exam_doc.description = data["exam"]["description"]
            exam_doc.instructions = data["exam"].get("instructions")
            
            # Add more fields as needed
            
            exam_doc.insert()
            exam_name = exam_doc.name
            
            # Add examiners
            if data["exam"].get("examiners"):
                for examiner_data in data["exam"]["examiners"]:
                    # Add examiners to the appropriate doctype based on your schema
                    examiner_doc = frappe.new_doc("Examiner")
                    examiner_doc.examiner = examiner_data["examiner"]
                    examiner_doc.can_proctor = examiner_data.get("can_proctor", 1)
                    examiner_doc.can_evaluate = examiner_data.get("can_evaluate", 1)
                    examiner_doc.parent = exam_name
                    examiner_doc.parenttype = "Exam"
                    examiner_doc.parentfield = "examiners"
                    examiner_doc.insert()
        
        # Process question data
        if data.get("questions", {}).get("type") == "Fixed" and exam_name:
            # Get the exam doc
            exam_doc = frappe.get_doc("Exam", exam_name)
            
            # If existing exam, clear previous questions
            if data.get("exam", {}).get("type") == "existing":
                # Remove existing questions from exam.added_questions table
                exam_doc.added_questions = []
            
            # Add selected questions
            for q in data["questions"].get("questions", []):
                exam_doc.append("added_questions", {
                    "exam_question": q["exam_question"],
                    "mark": q["mark"]
                })
                
            # Update question type
            exam_doc.question_type = "Fixed"
            
            # Calculate total marks
            total_marks = 0
            for q in exam_doc.added_questions:
                total_marks += float(q.mark)
                
            exam_doc.total_marks = total_marks
            exam_doc.save()
            
        elif data.get("questions", {}).get("type") == "Random" and exam_name:
            exam_doc = frappe.get_doc("Exam", exam_name)
            
            # Set randomized settings
            exam_doc.question_type = "Random"
            exam_doc.randomize_questions = 1
            exam_doc.total_questions = data["questions"]["total_questions"]
            
            exam_doc.save()
        
        # Process schedule data
        schedule_name = None
        
        if data.get("schedule", {}).get("type") == "existing":
            schedule_name = data["schedule"]["name"]
        else:
            # Create new schedule
            schedule_doc = frappe.new_doc("Exam Schedule")
            schedule_doc.name = data["schedule"]["name"]
            schedule_doc.exam = exam_name
            schedule_doc.start_date_time = data["schedule"]["start_date_time"]
            schedule_doc.visibility = data["schedule"]["visibility"]
            
            if data["schedule"].get("schedule_type") == "Recurring" and data["schedule"].get("schedule_expire_in_days"):
                schedule_doc.schedule_type = "Recurring"
                schedule_doc.schedule_expire_in_days = data["schedule"]["schedule_expire_in_days"]
                
            schedule_doc.insert()
            schedule_name = schedule_doc.name
        
        # Commit all changes
        frappe.db.commit()
        
        return {
            "success": True,
            "exam": exam_name,
            "schedule": schedule_name
        }
        
    except Exception as e:
        # Rollback on error
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Error saving exam builder data")
        return {"success": False, "error": str(e)}
