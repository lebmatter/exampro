import frappe

def redirect_to_exams_list():
    frappe.local.flags.redirect_location = "/my-exams"
    raise frappe.Redirect

def cleanup_request():
    """
    Clean up resources at the end of a request.
    This function cleans up any resources that were used during the request.
    Currently, it:
    1. Clears the S3 client from frappe.local to prevent memory leaks
    """
    if hasattr(frappe.local, "s3_client"):
        delattr(frappe.local, "s3_client")

def get_website_context(context):
    user_roles = frappe.get_roles(frappe.session.user)
    top_bar_items = []
    
    if "Exam Proctor" in user_roles:
        top_bar_items.append({"label": "Proctor Exam", "url": "/proctor"})
    
    if "Exam Evaluator" in user_roles:
        top_bar_items.append({"label": "Evaluate Exam", "url": "/evaluate"})
    
    if "Exam Manager" in user_roles:
        top_bar_items.append({
            "label": "Manage",
            "url": "#",  # Add a URL or use "#" for dropdown parent
            "right": True,
            "child_items": [  # Use child_items instead of dropdown_items
                {"label": "Users", "url": "/manage/users"},
                {"label": "Questions", "url": "/manage/questions"}
            ]
        })
    
    if "System Manager" in user_roles:
        top_bar_items.append({
            "label": "Admin",
            "url": "#",  # Add a URL or use "#" for dropdown parent
            "right": True,
            "child_items": [  # Use child_items instead of dropdown_items
                {"label": "Desk", "url": "/app"},
                {"label": "Exam Dashboard", "url": "/app/exam-dashboard"},
            ]
        })
    context.top_bar_items = top_bar_items
    return context

def create_sample_exams():
    if frappe.db.exists("Exam", "World Capitals Quiz"):
        return

    # Create question categories
    capitals_category = "World Capitals"
    space_category = "Earth and Space"
    if not frappe.db.exists("Exam Question Category", capitals_category):
        frappe.get_doc({"doctype": "Exam Question Category", "title": capitals_category}).insert()
    if not frappe.db.exists("Exam Question Category", space_category):
        frappe.get_doc({"doctype": "Exam Question Category", "title": space_category}).insert()

    # Multiple choice questions
    mcq_questions = [
        {"question": "What is the capital of France?", "options": ["Paris", "London", "Berlin", "Madrid"], "answer": "Paris", "category": capitals_category},
        {"question": "What is the capital of Japan?", "options": ["Tokyo", "Beijing", "Seoul", "Bangkok"], "answer": "Tokyo", "category": capitals_category},
        {"question": "What is the capital of Australia?", "options": ["Canberra", "Sydney", "Melbourne", "Perth"], "answer": "Canberra", "category": capitals_category},
        {"question": "What is the capital of Canada?", "options": ["Ottawa", "Toronto", "Vancouver", "Montreal"], "answer": "Ottawa", "category": capitals_category},
        {"question": "What is the capital of Brazil?", "options": ["Brasília", "Rio de Janeiro", "São Paulo", "Salvador"], "answer": "Brasília", "category": capitals_category},
        {"question": "Which planet is known as the Red Planet?", "options": ["Mars", "Venus", "Jupiter", "Saturn"], "answer": "Mars", "category": space_category},
        {"question": "What is the largest planet in our solar system?", "options": ["Jupiter", "Saturn", "Neptune", "Uranus"], "answer": "Jupiter", "category": space_category},
        {"question": "What is the name of the galaxy our solar system is in?", "options": ["Milky Way", "Andromeda", "Triangulum", "Whirlpool"], "answer": "Milky Way", "category": space_category},
        {"question": "How many moons does Earth have?", "options": ["1", "2", "3", "4"], "answer": "1", "category": space_category},
        {"question": "What is the closest star to Earth?", "options": ["Sun", "Proxima Centauri", "Alpha Centauri A", "Sirius"], "answer": "Sun", "category": space_category},
    ]

    for q in mcq_questions:
        # Check if the question already exists in the category
        existing_question = frappe.db.exists("Exam Question", 
            {"question": q["question"], "category": q["category"]})
        
        if existing_question:
            continue  # Skip this question if it already exists
            
        frappe.get_doc({
            "doctype": "Exam Question",
            "question": q["question"],
            "category": q["category"],
            "mark": 1,
            "type": "Choices",
            "option_1": q["options"][0],
            "is_correct_1": 1 if q["options"][0] == q["answer"] else 0,
            "option_2": q["options"][1],
            "is_correct_2": 1 if q["options"][1] == q["answer"] else 0,
            "option_3": q["options"][2],
            "is_correct_3": 1 if q["options"][2] == q["answer"] else 0,
            "option_4": q["options"][3],
            "is_correct_4": 1 if q["options"][3] == q["answer"] else 0,
        }).insert()

    # User input questions
    user_input_questions = [
        {"question": "What is the capital of Italy?", "answer": "Rome", "category": capitals_category},
        {"question": "What is the capital of Spain?", "answer": "Madrid", "category": capitals_category},
        {"question": "What is the capital of Germany?", "answer": "Berlin", "category": capitals_category},
        {"question": "What is the name of the force that holds us to the Earth?", "answer": "Gravity", "category": space_category},
        {"question": "What is the fifth planet from the sun?", "answer": "Jupiter", "category": space_category},
    ]

    for q in user_input_questions:
        # Check if the question already exists in the category
        existing_question = frappe.db.exists("Exam Question", 
            {"question": q["question"], "category": q["category"]})
        
        if existing_question:
            continue  # Skip this question if it already exists
            
        frappe.get_doc({
            "doctype": "Exam Question",
            "question": q["question"],
            "category": q["category"],
            "mark": 2,
            "type": "User Input",
            "possibility_1": q["answer"]
        }).insert()

    frappe.db.commit()
    # Create the exams
    # Create the exams if they don't already exist
    if not frappe.db.exists("Exam", "World Capitals Quiz"):
        frappe.get_doc({
            "doctype": "Exam",
            "title": "World Capitals Quiz",
            "description": "Test your knowledge of world capitals.",
            "duration": 15,
            "question_type": "Mixed",
            "pass_percentage": 100,
            "select_questions": [
                {"question_category": capitals_category, "no_of_questions": 3, "mark_per_question": 2},
                {"question_category": capitals_category, "no_of_questions": 2, "mark_per_question": 1},
            ]
        }).insert()

    if not frappe.db.exists("Exam", "Earth and Space Quiz"):
        frappe.get_doc({
            "doctype": "Exam",
            "title": "Earth and Space Quiz",
            "description": "Test your knowledge of Earth and space.",
            "duration": 15,
            "question_type": "Choices",
            "pass_percentage": 100,
            "select_questions": [
                {"question_category": space_category, "no_of_questions": 5, "mark_per_question": 1},
            ]
        }).insert()

    frappe.db.commit()