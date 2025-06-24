import frappe
from frappe import _

@frappe.whitelist()
def duplicate_question(question):
    """
    Duplicate an exam question
    
    Args:
        question (str): Name of the question to duplicate
    """
    # Check if user has Exam Manager role
    if "Exam Manager" not in frappe.get_roles(frappe.session.user):
        return {"success": False, "error": _("You are not authorized to access this page")}

    try:
        # Get the original question
        source = frappe.get_doc("Exam Question", question)
        
        # Create a new question with the same properties
        new_question = frappe.copy_doc(source)
        new_question.insert(ignore_permissions=True)
        frappe.db.commit()
        
        return {"success": True, "name": new_question.name}
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error duplicating question {question}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def delete_question(question):
    """
    Delete an exam question
    
    Args:
        question (str): Name of the question to delete
    """
    # Check if user has Exam Manager role
    if "Exam Manager" not in frappe.get_roles(frappe.session.user):
        return {"success": False, "error": _("You are not authorized to access this page")}

    
    try:
        # Check if question is used in any exams
        added_questions = frappe.get_all("Exam Added Question", filters={"exam_question": question})
        if added_questions:
            return {"success": False, "error": _("Cannot delete question that is used in exams")}
        
        # Delete the question
        frappe.delete_doc("Exam Question", question)
        frappe.db.commit()
        
        return {"success": True}
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error deleting question {question}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def get_question_preview(question):
    """
    Get HTML preview of a question for the modal
    
    Args:
        question (str): Name of the question to preview
    """
    # Check if user has Exam Manager role
    if "Exam Manager" not in frappe.get_roles(frappe.session.user):
        return {"success": False, "error": _("You are not authorized to access this page")}


    try:
        # Get the question
        q = frappe.get_doc("Exam Question", question)
        
        # Build HTML preview
        html = f'<div class="question-preview mb-4">'
        html += f'<h5 class="mb-3">{q.question}</h5>'
        
        if q.description_image:
            html += f'<div class="mb-3"><img src="{q.description_image}" class="img-fluid" /></div>'
        
        # Show options based on question type
        if q.type == "Multiple Choice" or q.type == "Multiple Select":
            html += '<div class="options-list">'
            
            for i in range(1, 5):
                option_text = getattr(q, f"option_{i}", "")
                option_image = getattr(q, f"option_{i}_image", "")
                is_correct = getattr(q, f"is_correct_{i}", 0)
                
                if not option_text and not option_image:
                    continue
                
                html += f'<div class="option-item mb-2 p-2 {is_correct and "border-success" or ""}">'
                html += f'<div class="d-flex align-items-center">'
                html += f'<div class="mr-2">'
                
                if q.type == "Multiple Choice":
                    html += f'<input type="radio" disabled {is_correct and "checked" or ""} />'
                else:
                    html += f'<input type="checkbox" disabled {is_correct and "checked" or ""} />'
                
                html += '</div>'
                html += f'<div class="option-content">{option_text}</div>'
                html += '</div>'
                
                if option_image:
                    html += f'<div class="mt-2"><img src="{option_image}" class="img-fluid" style="max-height: 150px;" /></div>'
                
                html += '</div>'
            
            html += '</div>'
        elif q.type == "Text":
            html += '<div class="form-group">'
            html += '<textarea class="form-control" rows="3" disabled placeholder="Text answer..."></textarea>'
            html += '</div>'
        
        # Add metadata
        html += '<div class="question-meta mt-4 pt-3 border-top">'
        html += f'<div><strong>Category:</strong> {q.category}</div>'
        html += f'<div><strong>Type:</strong> {q.type}</div>'
        html += f'<div><strong>Marks:</strong> {q.mark}</div>'
        html += '</div>'
        
        html += '</div>'
        
        return {"success": True, "html": html}
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error getting question preview for {question}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def add_question_category(title):
    """
    Add a new question category
    
    Args:
        title (str): Title of the new category
    """
    # Check if user has Exam Manager role
    if "Exam Manager" not in frappe.get_roles(frappe.session.user):
        return {"success": False, "error": _("You are not authorized to access this page")}

    
    try:
        # Check if category already exists
        if frappe.db.exists("Exam Question Category", {"title": title}):
            return {"success": False, "error": _("Category already exists")}
        
        # Create new category
        category = frappe.new_doc("Exam Question Category")
        category.title = title
        category.insert(ignore_permissions=True)
        frappe.db.commit()
        
        return {"success": True, "name": category.name, "title": category.title}
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error creating category: {title}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def create_question(question_data):
    """
    Create a new exam question from the modal form
    
    Args:
        question_data (dict): JSON string of question data
    """
    # Check if user has Exam Manager role
    if "Exam Manager" not in frappe.get_roles(frappe.session.user):
        return {"success": False, "error": _("You are not authorized to access this page")}

    
    try:
        if isinstance(question_data, str):
            import json
            question_data = json.loads(question_data)
        
        # Validate required fields
        if not question_data.get("question"):
            return {"success": False, "error": _("Question text is required")}
        if not question_data.get("category"):
            return {"success": False, "error": _("Category is required")}
        if not question_data.get("type"):
            return {"success": False, "error": _("Question type is required")}
        
        # For Multiple Choice/Select questions, validate options
        if question_data.get("type") in ["Multiple Choice", "Multiple Select"]:
            # Check if at least two options are provided
            options_count = sum(1 for i in range(1, 5) if question_data.get(f"option_{i}"))
            if options_count < 2:
                return {"success": False, "error": _("At least two options are required")}
            
            # Check if at least one option is marked as correct
            correct_count = sum(1 for i in range(1, 5) if question_data.get(f"is_correct_{i}"))
            if correct_count == 0:
                return {"success": False, "error": _("At least one correct answer must be selected")}
            
            # For Multiple Choice, only one correct answer should be selected
            if question_data.get("type") == "Multiple Choice" and correct_count > 1:
                return {"success": False, "error": _("Multiple Choice questions can have only one correct answer")}
        
        # Create new question
        question = frappe.new_doc("Exam Question")
        question.question = question_data.get("question")
        question.category = question_data.get("category")
        question.type = question_data.get("type")
        question.mark = question_data.get("mark", 1)
        
        # Set description image if provided
        if question_data.get("description_image"):
            question.description_image = question_data.get("description_image")
        
        # Set options for Multiple Choice/Select questions
        if question_data.get("type") in ["Multiple Choice", "Multiple Select"]:
            for i in range(1, 5):
                if question_data.get(f"option_{i}"):
                    setattr(question, f"option_{i}", question_data.get(f"option_{i}"))
                    setattr(question, f"is_correct_{i}", question_data.get(f"is_correct_{i}", 0))
                    
                    if question_data.get(f"option_{i}_image"):
                        setattr(question, f"option_{i}_image", question_data.get(f"option_{i}_image"))
        
        # For Text questions, set possible answers
        if question_data.get("type") == "Text":
            for i in range(1, 5):
                if question_data.get(f"possibility_{i}"):
                    setattr(question, f"possibility_{i}", question_data.get(f"possibility_{i}"))
        
        question.insert(ignore_permissions=True)
        frappe.db.commit()
        
        return {"success": True, "name": question.name}
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error creating question: {str(e)}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def delete_question_category(category_name):
    """
    Delete a question category
    
    Args:
        category_name (str): Name of the category to delete
    """
    # Check if user has Exam Manager role
    if "Exam Manager" not in frappe.get_roles(frappe.session.user):
        return {"success": False, "error": _("You are not authorized to access this page")}

    
    try:
        # Check if category is used in any questions
        questions = frappe.get_all("Exam Question", filters={"category": category_name})
        if questions:
            return {
                "success": False, 
                "error": _("Cannot delete category that is used in questions"),
                "question_count": len(questions)
            }
        
        # Delete the category
        frappe.delete_doc("Exam Question Category", category_name)
        frappe.db.commit()
        
        return {"success": True}
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error deleting category {category_name}")
        return {"success": False, "error": str(e)}

def get_questions():
    """Get all exam questions with relevant details"""
    
    # Get all questions
    questions = frappe.get_all(
        "Exam Question",
        fields=[
            "name", 
            "question", 
            "category", 
            "type", 
            "mark"
        ]
    )
    
    return questions

def get_categories():
    """Get all question categories"""
    
    # Get all Exam Question Categories
    categories = frappe.get_all(
        "Exam Question Category",
        fields=["name", "title"],
        order_by="title"
    )
    
    return categories

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
    context.questions = get_questions()
    context.categories = get_categories()
    
    context.metatags = {
        "title": _("Manage Exam Questions"),
        "description": "Manage exam question bank"
    }
