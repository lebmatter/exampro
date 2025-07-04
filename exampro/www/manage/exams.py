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
def get_examiners(exam):
    """Get all examiners for a given exam."""
    if not frappe.has_permission("Examiner", "read"):
        frappe.throw(_("Not permitted to read Examiners"), frappe.PermissionError)
    
    return frappe.get_all(
        "Examiner",
        fields=["name", "examiner_user", "can_proctor", "can_evaluate"],
        filters={"parent": exam, "parenttype": "Exam"}
    )

@frappe.whitelist()
def update_examiners(exam, examiners):
    """Update the list of examiners for an exam."""
    if not frappe.has_permission("Exam", "write"):
        frappe.throw(_("Not permitted to write to Exam"), frappe.PermissionError)

    try:
        # Delete existing examiners for this exam
        existing_examiners = frappe.get_all("Examiner", filters={"parent": exam, "parenttype": "Exam"})
        for ex in existing_examiners:
            frappe.delete_doc("Examiner", ex.name, ignore_permissions=True)

        # Add new examiners from the provided list
        import json
        examiners_list = json.loads(examiners)

        for ex_data in examiners_list:
            new_examiner = frappe.new_doc("Examiner")
            new_examiner.parent = exam
            new_examiner.parenttype = "Exam"
            new_examiner.examiner_user = ex_data.get("examiner_user")
            new_examiner.can_proctor = ex_data.get("can_proctor", 0)
            new_examiner.can_evaluate = ex_data.get("can_evaluate", 0)
            new_examiner.insert(ignore_permissions=True)
        
        frappe.db.commit()
        return {"success": True}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error updating examiners")
        frappe.db.rollback()
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def create_schedule(exam, name, start_date_time, schedule_type, schedule_expire_in_days=None):
    """
    Create a new exam schedule.
    """
    if not frappe.has_permission("Exam Schedule", "create"):
        return {"success": False, "error": _("Not permitted to create Exam Schedules")}

    try:
        new_schedule = frappe.new_doc("Exam Schedule")
        new_schedule.exam = exam
        new_schedule.name = name
        new_schedule.start_date_time = start_date_time
        new_schedule.schedule_type = schedule_type
        if schedule_type == 'Flexible':
            new_schedule.schedule_expire_in_days = schedule_expire_in_days
        new_schedule.insert()
        frappe.db.commit()
        return {"success": True, "name": new_schedule.name}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error creating schedule")
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

@frappe.whitelist()
def get_question_categories(exam):
    """
    Get all question categories with their counts and marks, along with the exam's current configuration.
    
    Args:
        exam (str): Name of the exam to get categories for
    """
    if not frappe.has_permission("Exam", "read"):
        return {"success": False, "error": _("Not permitted to view exam"), "categories": []}
    
    try:
        # Get the exam
        exam_doc = frappe.get_doc("Exam", exam)
        
        # Get categories with associated questions and marks
        # Group questions by category AND mark to show different rows for different mark values
        category_marks_questions = frappe.db.sql("""
            SELECT 
                eqc.name as category_id,
                eqc.title as category_name,
                IFNULL(eq.mark, 1) as marks_per_question,
                COUNT(eq.name) as question_count
            FROM 
                `tabExam Question Category` eqc
            LEFT JOIN 
                `tabExam Question` eq ON eq.category = eqc.name
            WHERE
                eq.name IS NOT NULL
            GROUP BY 
                eqc.name, eq.mark
            ORDER BY 
                eqc.title, eq.mark
        """, as_dict=True)
        
        # Also get categories that don't have questions yet
        empty_categories = frappe.db.sql("""
            SELECT 
                eqc.name as category_id,
                eqc.title as category_name,
                1 as marks_per_question,
                0 as question_count
            FROM 
                `tabExam Question Category` eqc
            LEFT JOIN 
                `tabExam Question` eq ON eq.category = eqc.name
            WHERE
                eq.name IS NULL
            GROUP BY 
                eqc.name
            ORDER BY 
                eqc.title
        """, as_dict=True)
        
        # Combine both sets of categories
        categories = category_marks_questions + empty_categories
        
        # Create a dictionary of the exam's current configuration
        # We need to track both category and marks per question
        exam_config = {}
        if exam_doc.added_questions:
            for question in exam_doc.added_questions:
                try:
                    # Get both category and mark for each question
                    question_data = frappe.db.get_value(
                        "Exam Question", 
                        question.exam_question, 
                        ["category", "mark"], 
                        as_dict=True
                    )
                    
                    if not question_data or not question_data.category:
                        continue
                        
                    marks = question_data.mark or 1  # Default to 1 if mark is None
                    
                    # Create a composite key: category_id:marks_per_question
                    composite_key = f"{question_data.category}:{marks}"
                    exam_config[composite_key] = exam_config.get(composite_key, 0) + 1
                        
                except Exception as e:
                    frappe.log_error(f"Error processing question {question.exam_question}: {str(e)}")
                    continue
        
        # Format the categories for the frontend with composite keys
        formatted_categories = []
        for cat in categories:
            # Create a unique identifier for this category+marks combination
            composite_key = f"{cat.category_id}:{cat.marks_per_question}"
            formatted_cat = {
                "id": composite_key,  # Unique ID for this category+marks combination
                "category_id": cat.category_id,
                "category_name": cat.category_name,
                "marks_per_question": cat.marks_per_question,
                "question_count": cat.question_count
            }
            formatted_categories.append(formatted_cat)
            
        return {
            "success": True, 
            "categories": formatted_categories,
            "exam_config": exam_config
        }
    
    except Exception as e:
        error_msg = f"Error getting question categories for exam {exam}: {str(e)}"
        frappe.log_error(frappe.get_traceback(), error_msg)
        return {"success": False, "error": str(e), "categories": []}

@frappe.whitelist()
def update_exam_questions(exam, category_config):
    """
    Update the questions in an exam based on the provided category configuration
    
    Args:
        exam (str): Name of the exam to update
        category_config (dict): Dictionary mapping category names to the number of questions to include
    """
    if not frappe.has_permission("Exam", "write"):
        return {"success": False, "error": _("Not permitted to modify exam")}
    
    try:
        # Parse category config if it's a string
        if isinstance(category_config, str):
            import json
            category_config = json.loads(category_config)
        
        # Get the exam
        exam_doc = frappe.get_doc("Exam", exam)
        
        # Clear existing questions
        exam_doc.added_questions = []
        
        # Add new questions by category and marks
        for composite_key, count in category_config.items():
            count = int(count)
            if count <= 0:
                continue
            
            # Parse the composite key (category_id:marks_per_question)
            try:
                category_id, marks = composite_key.split(":")
                marks = float(marks)
            except ValueError:
                # If the key isn't in the expected format, skip it
                continue
                
            # Get random questions from this category with the specified mark
            questions = frappe.db.sql("""
                SELECT name, mark
                FROM `tabExam Question`
                WHERE category = %s AND mark = %s
                ORDER BY RAND()
                LIMIT %s
            """, (category_id, marks, count), as_dict=True)
            
            # Use the actual marks from the question
            marks_per_question = marks
            
            # Add questions to the exam
            for question in questions:
                exam_doc.append("added_questions", {
                    "exam_question": question.name,
                    "mark": marks_per_question
                })
        
        # Calculate total questions and marks
        total_questions = len(exam_doc.added_questions)
        total_marks = sum(q.mark for q in exam_doc.added_questions)
        
        # Update exam document
        exam_doc.total_questions = total_questions
        exam_doc.total_marks = total_marks
        
        # Save the exam
        exam_doc.save()
        frappe.db.commit()
        
        return {
            "success": True, 
            "total_questions": exam_doc.total_questions,
            "total_marks": exam_doc.total_marks
        }
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error updating questions for exam {exam}")
        return {"success": False, "error": str(e)}
