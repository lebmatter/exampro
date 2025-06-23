import frappe
from frappe import _

@frappe.whitelist()
def duplicate_question(question):
    """
    Duplicate an exam question
    
    Args:
        question (str): Name of the question to duplicate
    """
    if not frappe.has_permission("Exam Question", "write"):
        return {"success": False, "error": _("Not permitted")}
    
    try:
        # Get the original question
        source = frappe.get_doc("Exam Question", question)
        
        # Create a new question with the same properties
        new_question = frappe.copy_doc(source)
        new_question.insert()
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
    if not frappe.has_permission("Exam Question", "delete"):
        return {"success": False, "error": _("Not permitted")}
    
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

def get_questions():
    """Get all exam questions with relevant details"""
    
    # Check if user has permission to view Exam Questions
    if not frappe.has_permission("Exam Question", "read"):
        return []
    
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
    
    # Get unique categories from questions
    categories = frappe.db.sql("""
        SELECT DISTINCT category as name 
        FROM `tabExam Question` 
        ORDER BY category
    """, as_dict=True)
    
    return categories

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
    context.questions = get_questions()
    context.categories = get_categories()
    
    context.metatags = {
        "title": _("Manage Exam Questions"),
        "description": "Manage exam question bank"
    }
