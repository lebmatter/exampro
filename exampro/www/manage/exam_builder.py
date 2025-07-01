import frappe
from frappe import _
import json

def has_exam_manager_role():
    """
    Check if the current user has Exam Manager role
    """
    return "Exam Manager" in frappe.get_roles()

def get_context(context):
    """
    Get context for the exam builder page
    """
    # Check if user has Exam Manager role
    if not has_exam_manager_role():
        frappe.throw(_("Not permitted"), frappe.PermissionError)
        
    context.exams = frappe.get_list("Exam", fields=["name", "title"], order_by="creation desc")
    return context

@frappe.whitelist()
def get_exam_details(exam):
    """
    Get detailed information about an exam including question configuration
    
    Args:
        exam (str): Name of the exam to get details for
    """
    if not has_exam_manager_role():
        return {"success": False, "error": _("Not permitted")}
    
    try:
        exam_doc = frappe.get_doc("Exam", exam)
        exam_data = exam_doc.as_dict()
        
        # Get question configuration
        question_config = {
            "question_type": exam_doc.question_type,
            "randomize_questions": exam_doc.randomize_questions,
            "total_questions": exam_doc.total_questions,
            "select_questions": []
        }
        
        # Get category settings
        for category_setting in exam_doc.select_questions:
            question_config["select_questions"].append({
                "question_category": category_setting.question_category,
                "no_of_questions": category_setting.no_of_questions,
                "mark_per_question": category_setting.mark_per_question
            })
        
        exam_data["question_config"] = question_config
        return exam_data
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
    if not has_exam_manager_role():
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
    if not has_exam_manager_role():
        return {"success": False, "error": _("Not permitted")}
    
    try:
        schedules = frappe.get_list(
            "Exam Schedule",
            filters={"exam": exam},
            fields=["name", "start_date_time", "status"],
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
    if not has_exam_manager_role():
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
    if not has_exam_manager_role():
        return {"success": False, "error": _("Not permitted")}
    
    try:
        questions = frappe.get_list(
            "Exam Question",
            fields=["name", "question", "question_type", "mark"],
            order_by="creation desc"
        )
        
        result = []
        for q in questions:
            result.append({
                "name": q.name,
                "question_text": q.question,
                "question_type": q.question_type,
                "mark": q.mark
            })
        
        return result
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error fetching available questions")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def get_users():
    """
    Get all users who have Exam Candidate role along with their batch info
    """
    if not has_exam_manager_role():
        return {"success": False, "error": _("Not permitted")}
    
    try:
        # Get all users with Exam Candidate role
        users_with_role = frappe.get_all(
            "Has Role", 
            filters={"role": "Exam Candidate", "parenttype": "User"},
            fields=["parent as name"]
        )
        
        # Get the user details for these users
        user_names = [u.name for u in users_with_role]
        if not user_names:
            return []
            
        users = frappe.get_list(
            "User",
            fields=["name", "full_name", "email"],
            filters={"enabled": 1, "name": ["in", user_names]},
            order_by="full_name asc"
        )
        
        # Get batch information for each user
        for user in users:
            batch_links = frappe.get_all(
                "Exam Batch User",
                filters={"candidate": user.name},
                fields=["exam_batch"]
            )
            user.batches = [b.exam_batch for b in batch_links]

        return users
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error fetching users with Exam Candidate role")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def get_registrations(schedule):
    """
    Get all users with Exam Candidate role with their registration status and batch info
    
    Args:
        schedule (str): Name of the schedule to get submissions for
    """
    if not has_exam_manager_role():
        return {"success": False, "error": _("Not permitted")}
    
    try:
        # Get all users with Exam Candidate role
        users_with_role = frappe.get_all(
            "Has Role", 
            filters={"role": "Exam Candidate", "parenttype": "User"},
            fields=["parent as name"]
        )
        
        user_names = [u.name for u in users_with_role]
        if not user_names:
            return []
            
        # Get all user details
        users = frappe.get_list(
            "User",
            fields=["name", "full_name", "email"],
            filters={"enabled": 1, "name": ["in", user_names]},
            order_by="full_name asc"
        )
        
        # Get existing registrations for this schedule
        registrations = frappe.get_list(
            "Exam Submission", 
            filters={"exam_schedule": schedule},
            fields=["name as submission_id", "candidate", "status", "creation"]
        )
        
        # Create registration status lookup
        registered_users = {}
        for reg in registrations:
            registered_users[reg.candidate] = {
                "registered": True,
                "status": reg.status,
                "submission_id": reg.submission_id,
                "creation": reg.creation
            }
        
        # Get batch information for all users
        user_batches = {}
        batch_entries = frappe.get_all(
            "Exam Batch User",
            filters={"candidate": ["in", user_names]},
            fields=["candidate", "exam_batch"]
        )
        
        # Organize batch data by user
        for entry in batch_entries:
            if entry.candidate not in user_batches:
                user_batches[entry.candidate] = []
            
            batch_name = frappe.get_value("Exam Batch", entry.exam_batch, "batch_name")
            user_batches[entry.candidate].append({
                "id": entry.exam_batch,
                "name": batch_name or entry.exam_batch
            })
        
        # Merge all data
        result = []
        for user in users:
            # Get registration status
            registration_info = registered_users.get(user.name, {
                "registered": False,
                "status": "Not Registered",
                "submission_id": None,
                "creation": None
            })
            
            # Get batch info
            batches = user_batches.get(user.name, [])
            
            # Create combined user object
            user_data = {
                "name": user.name,
                "full_name": user.full_name,
                "email": user.email,
                "registered": registration_info["registered"],
                "status": registration_info["status"],
                "submission_id": registration_info["submission_id"],
                "creation": registration_info["creation"],
                "batches": batches
            }
            
            result.append(user_data)
                
        return result
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error fetching users with registration status for schedule {schedule}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def add_registration(schedule, email):
    """
    Add a new exam submission to a schedule
    
    Args:
        schedule (str): Name of the schedule
        email (str): Email of the user to register
    """
    if not has_exam_manager_role():
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
            "Exam Submission",
            filters={"exam_schedule": schedule, "candidate": user_name},
            limit=1
        )
        
        if existing:
            return {"success": False, "error": _("User is already registered for this exam")}
            
        # Create submission
        reg_doc = frappe.get_doc({
            "doctype": "Exam Submission",
            "exam_schedule": schedule,
            "candidate": user_name,
            "candidate_name": frappe.db.get_value("User", user_name, "full_name"),
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
                "candidate": user_name,
                "status": "Registered",
                "creation": reg_doc.creation
            }
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error adding exam submission for {email} to schedule {schedule}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def remove_registration(schedule, user):
    """
    Remove an exam submission from a schedule
    
    Args:
        schedule (str): Name of the schedule
        user (str): User to remove (will be used as candidate)
    """
    if not has_exam_manager_role():
        return {"success": False, "error": _("Not permitted")}
    
    try:
        # Find submission
        submissions = frappe.get_list(
            "Exam Submission",
            filters={"exam_schedule": schedule, "candidate": user}
        )
        
        if not submissions:
            return {"success": False, "error": _("Exam submission not found")}
            
        # Delete submission
        for sub in submissions:
            frappe.delete_doc("Exam Submission", sub.name)
            
        return {"success": True}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error removing exam submission for user {user} from schedule {schedule}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def get_question_categories_with_counts():
    """
    Get all question categories with question counts grouped by type and marks
    """
    if not has_exam_manager_role():
        return {"success": False, "error": _("Not permitted")}
    
    try:
        # Get question counts grouped by category, type, and marks
        questions_data = frappe.db.sql("""
            SELECT 
                category,
                type,
                mark,
                COUNT(*) as question_count
            FROM `tabExam Question`
            GROUP BY category, type, mark
            ORDER BY category, type, mark
        """, as_dict=True)
        
        # Group by category for easier frontend handling
        categories = {}
        for item in questions_data:
            category = item.category
            if category not in categories:
                categories[category] = []
            
            categories[category].append({
                "type": item.type,
                "mark": item.mark,
                "question_count": item.question_count
            })
        
        # If no categories found, provide sample data for debugging
        if not categories:
            frappe.log_error("No categories found - providing sample data for testing", "Debug info")
            # Sample data for testing UI
            categories = {
                "Mathematics": [
                    {"type": "Choices", "mark": 1, "question_count": 15},
                    {"type": "Choices", "mark": 2, "question_count": 10},
                    {"type": "User Input", "mark": 5, "question_count": 5}
                ],
                "Science": [
                    {"type": "Choices", "mark": 1, "question_count": 20},
                    {"type": "User Input", "mark": 2, "question_count": 10}
                ],
                "General Knowledge": [
                    {"type": "Choices", "mark": 1, "question_count": 30}
                ]
            }
        
        return categories
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error fetching question categories with counts")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def get_questions_by_category_and_type(question_type):
    """
    Get questions grouped by category and mark for a specific question type
    
    Args:
        question_type (str): Question type (Choices/User Input)
        
    Returns:
        list: List of dictionaries with category, mark, and no_of_qs
    """
    if not has_exam_manager_role():
        return {"success": False, "error": _("Not permitted")}
    
    try:
        # Get question counts grouped by category and marks for the specific type
        grouped_data = frappe.db.sql("""
            SELECT 
                category,
                mark,
                COUNT(*) as no_of_qs
            FROM `tabExam Question`
            WHERE type = %s
            GROUP BY category, mark
            ORDER BY category, mark
        """, (question_type,), as_dict=True)
        
        return grouped_data
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error fetching questions for type {question_type}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def get_questions_for_exam(category, question_type, mark, limit):
    """
    Get actual questions for adding to exam
    
    Args:
        category (str): Question category
        question_type (str): Question type (Choices/User Input)
        mark (int): Mark value
        limit (int): Maximum number of questions to return
    """
    if not has_exam_manager_role():
        return {"success": False, "error": _("Not permitted")}
    
    try:
        filters = {
            "category": category,
            "type": question_type,
            "mark": mark
        }
        
        questions = frappe.get_list(
            "Exam Question",
            fields=["name", "question", "type", "mark", "category"],
            filters=filters,
            order_by="creation desc",
            limit=limit
        )
        
        return questions
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error fetching questions for exam")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def get_questions_preview(category, question_type, mark):
    """
    Get questions for preview in the selection modal
    
    Args:
        category (str): Question category
        question_type (str): Question type (Choices/User Input)
        mark (int): Mark value
    """
    if not has_exam_manager_role():
        return {"success": False, "error": _("Not permitted")}
    
    try:
        filters = {
            "category": category,
            "type": question_type,
            "mark": mark
        }
        
        questions = frappe.get_list(
            "Exam Question",
            fields=["name", "question"],
            filters=filters,
            order_by="creation desc"
        )
        
        # If no questions found, provide sample data for testing
        if not questions:
            frappe.log_error(f"No questions found for {category}, {question_type}, {mark} - providing sample data", "Debug info")
            
            # Generate sample questions based on category and type
            sample_questions = []
            num_samples = 5  # Number of sample questions to generate
            
            for i in range(1, num_samples + 1):
                if question_type == "Choices":
                    sample_questions.append({
                        "name": f"SAMPLE-{i}",
                        "question": f"Sample multiple choice question #{i} for {category} worth {mark} mark(s)?"
                    })
                else:  # User Input
                    sample_questions.append({
                        "name": f"SAMPLE-{i}",
                        "question": f"Sample written answer question #{i} for {category} worth {mark} mark(s)."
                    })
            
            return sample_questions
        
        return questions
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error fetching questions preview")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def save_exam_from_builder(exam_data):
    """
    Save or update exam from the exam builder
    
    Args:
        exam_data (str): JSON string of exam data from the builder
    """
    if not has_exam_manager_role():
        return {"success": False, "error": _("Not permitted")}
    
    try:
        # Parse JSON string to dict
        import json
        if isinstance(exam_data, str):
            exam_data = json.loads(exam_data)
        
        frappe.logger().info(f"Processing exam data: {exam_data}")
        
        if exam_data.get("type") == "existing":
            # Update existing exam
            exam_name = exam_data.get("name")
            exam_doc = frappe.get_doc("Exam", exam_name)
            
            # Update question configuration
            if exam_data.get("questions"):
                questions_config = exam_data["questions"]
                
                if questions_config.get("type") == "Random":
                    exam_doc.randomize_questions = 1
                    exam_doc.total_questions = int(questions_config.get("total_questions", 0))
                    exam_doc.question_type = questions_config.get("question_type_filter", "Mixed")
                    # Clear category settings for random questions
                    exam_doc.select_questions = []
                else:
                    # Fixed questions
                    exam_doc.randomize_questions = 0
                    exam_doc.question_type = questions_config.get("question_type_filter", "Mixed")
                    
                    # Update category settings
                    exam_doc.select_questions = []
                    for category in questions_config.get("categories", []):
                        exam_doc.append("select_questions", {
                            "question_category": category["category"],
                            "no_of_questions": int(category["selectedCount"]),
                            "mark_per_question": int(category["mark"])
                        })
                
                exam_doc.save()
                
            return {"success": True, "exam_name": exam_name, "message": "Exam updated successfully"}
            
        else:
            # Create new exam
            exam_doc = frappe.new_doc("Exam")
            exam_doc.title = exam_data.get("title")
            exam_doc.duration = int(exam_data.get("duration", 0))
            exam_doc.pass_percentage = float(exam_data.get("pass_percentage", 0))
            exam_doc.description = exam_data.get("description")
            exam_doc.instructions = exam_data.get("instructions", "")
            
            # Add examiners
            if exam_data.get("examiners"):
                for examiner_data in exam_data["examiners"]:
                    exam_doc.append("examiners", {
                        "examiner": examiner_data["examiner"],
                        "can_proctor": examiner_data.get("can_proctor", 1),
                        "can_evaluate": examiner_data.get("can_evaluate", 1)
                    })
            
            # Add question configuration
            if exam_data.get("questions"):
                questions_config = exam_data["questions"]
                
                if questions_config.get("type") == "Random":
                    exam_doc.randomize_questions = 1
                    exam_doc.total_questions = int(questions_config.get("total_questions", 0))
                    exam_doc.question_type = questions_config.get("question_type_filter", "Mixed")
                else:
                    # Fixed questions
                    exam_doc.randomize_questions = 0
                    exam_doc.question_type = questions_config.get("question_type_filter", "Mixed")
                    
                    # Add category settings
                    for category in questions_config.get("categories", []):
                        exam_doc.append("select_questions", {
                            "question_category": category["category"],
                            "no_of_questions": int(category["selectedCount"]),
                            "mark_per_question": int(category["mark"])
                        })
            
            exam_doc.insert()
            
            return {"success": True, "exam_name": exam_doc.name, "message": "Exam created successfully"}
            
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error saving exam from builder")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def get_exams():
    """
    Get list of exams for the exam builder
    """
    if not has_exam_manager_role():
        return {"success": False, "error": _("Not permitted")}
    
    try:
        exams = frappe.get_list(
            "Exam",
            fields=["name", "title", "duration", "pass_percentage"],
            order_by="modified desc"
        )
        return exams
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error fetching exams")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def get_exam_batches():
    """
    Get list of all exam batches
    """
    if not has_exam_manager_role():
        return {"success": False, "error": _("Not permitted")}
    
    try:
        batches = frappe.get_list(
            "Exam Batch",
            fields=["name", "batch_name"],
            order_by="batch_name asc"
        )
        return batches
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error fetching exam batches")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def add_registrations(schedule, users):
    """
    Add multiple exam submissions to a schedule
    
    Args:
        schedule (str): Name of the schedule
        users (str): JSON string of user emails to register
    """
    if not has_exam_manager_role():
        return {"success": False, "error": _("Not permitted")}
    
    try:
        users_list = json.loads(users)
        results = []
        errors = []
        
        for email in users_list:
            # Check if user exists
            user = frappe.get_list("User", filters={"email": email}, limit=1)
            
            if not user:
                errors.append(f"User not found: {email}")
                continue
                
            user_name = user[0].name
            
            # Check if already registered
            existing = frappe.get_list(
                "Exam Submission",
                filters={"exam_schedule": schedule, "candidate": user_name},
                limit=1
            )
            
            if existing:
                continue
            
            # Create submission
            reg_doc = frappe.get_doc({
                "doctype": "Exam Submission",
                "exam_schedule": schedule,
                "candidate": user_name,
                "candidate_name": frappe.db.get_value("User", user_name, "full_name"),
                "status": "Registered"
            })
            reg_doc.insert()
            
            # Get user details for the response
            user_details = frappe.get_doc("User", user_name)
            results.append({
                "user": user_name,
                "user_name": user_details.full_name,
                "candidate": user_name,
                "status": "Registered",
                "creation": reg_doc.creation
            })
        
        return {
            "success": True,
            "results": results,
            "errors": errors
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error in bulk registration for schedule {schedule}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def save_schedule_from_builder(schedule_data):
    """
    Save or update schedule from the exam builder
    
    Args:
        schedule_data (str): JSON string of schedule data from the builder
    """
    if not has_exam_manager_role():
        return {"success": False, "error": _("Not permitted")}
    
    try:
        # Parse JSON string to dict
        import json
        from datetime import datetime
        if isinstance(schedule_data, str):
            schedule_data = json.loads(schedule_data)
        
        frappe.logger().info(f"Processing schedule data: {schedule_data}")
        
        if schedule_data.get("type") == "existing":
            # Return existing schedule info
            schedule_name = schedule_data.get("name")
            return {"success": True, "schedule_name": schedule_name, "message": "Using existing schedule"}
            
        else:
            # Extract required data
            exam = schedule_data.get("exam")
            schedule_name = schedule_data.get("schedule_name")
            
            if not exam or not schedule_name:
                return {"success": False, "error": "Missing required fields: exam or schedule_name"}
                
            if not schedule_data.get("start_datetime"):
                return {"success": False, "error": "Start date and time are required"}
            
            # Create a unique name for the document
            # This is important for Frappe document creation
            unique_id = frappe.generate_hash(length=10)
            doc_name = f"{exam}_{schedule_name}_{unique_id}"
            
            # Create new schedule with explicit name
            schedule_doc = frappe.new_doc("Exam Schedule")
            schedule_doc.name = doc_name
            schedule_doc.exam = exam
            schedule_doc.schedule_name = schedule_name
            
            # First, get the actual field structure of Exam Schedule
            fields_meta = frappe.get_meta("Exam Schedule").get("fields")
            field_names = [f.fieldname for f in fields_meta]
            frappe.logger().info(f"Exam Schedule fields: {field_names}")
            
            # Parse date and time from start_datetime
            if schedule_data.get("start_datetime"):
                try:
                    # Handle the start_datetime format from HTML datetime-local input
                    dt_str = schedule_data.get("start_datetime")
                    
                    # Parse datetime string
                    dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M")
                    formatted_datetime = dt.strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Set all possible date/time fields that might exist in the doctype
                    if "start_date_time" in field_names:
                        schedule_doc.start_date_time = formatted_datetime
                    
                    # From error message, it seems the field is actually just "start_date"
                    if "start_date" in field_names:
                        schedule_doc.start_date = dt.date()
                        
                    # Alternate format as a string
                    if "start_time" in field_names:
                        schedule_doc.start_time = dt.time().strftime("%H:%M:%S")
                        
                    # Individual date and time fields
                    if "schedule_date" in field_names:
                        schedule_doc.schedule_date = dt.date()
                        
                    if "schedule_time" in field_names:
                        schedule_doc.schedule_time = dt.time().strftime("%H:%M:%S")
                    
                except Exception as e:
                    frappe.logger().error(f"Error parsing datetime: {e}")
                    return {"success": False, "error": f"Invalid date format: {e}"}
            
            # Remove visibility and related fields
            # schedule_doc.visibility = schedule_data.get("visibility")
            
            # Add expire_days if it exists for recurring schedules
            if schedule_data.get("schedule_type") == "Recurring" and schedule_data.get("expire_days"):
                schedule_doc.expire_after = schedule_data.get("expire_days")
            
            # Insert with explicit naming
            frappe.logger().info(f"Inserting schedule document: {schedule_doc.as_dict()}")
            schedule_doc.insert(ignore_permissions=True)
            frappe.db.commit()
            
            return {
                "success": True, 
                "schedule_name": schedule_doc.name, 
                "message": "Schedule created successfully"
            }
            
            schedule_doc.schedule_type = schedule_data.get("schedule_type")
            # schedule_doc.visibility = schedule_data.get("visibility")
            
            # Add expire_days if it exists for recurring schedules
            if schedule_data.get("schedule_type") == "Recurring" and schedule_data.get("expire_days"):
                schedule_doc.expire_after = schedule_data.get("expire_days")
            
            # Insert with explicit naming
            frappe.logger().info(f"Inserting schedule document: {schedule_doc.as_dict()}")
            schedule_doc.insert(ignore_permissions=True)
            frappe.db.commit()
            
            return {
                "success": True, 
                "schedule_name": schedule_doc.name, 
                "message": "Schedule created successfully"
            }
            
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error saving schedule from builder")
        return {"success": False, "error": str(e)}
