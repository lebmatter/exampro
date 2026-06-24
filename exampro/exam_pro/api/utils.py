from datetime import datetime
import frappe

from exampro.exam_pro.api.examops import evaluation_values

def redirect_to_exams_list():
    frappe.local.flags.redirect_location = "/dashboard"
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

    is_proctor = "Exam Proctor" in user_roles
    is_evaluator = "Exam Evaluator" in user_roles
    is_manager = "Exam Manager" in user_roles

    if is_proctor:
        top_bar_items.append({"label": "Proctor Exam", "url": "/proctor"})

    if is_evaluator:
        top_bar_items.append({"label": "Evaluate Exam", "url": "/evaluate"})

    if is_manager:
        top_bar_items.append({"label": "Manage", "url": "/app/exam"})

    context.top_bar_items = top_bar_items
    context.is_proctor = is_proctor
    context.is_evaluator = is_evaluator
    context.is_manager = is_manager
    return context

def create_sample_exams():
    # Create question categories
    capitals_category = "World Capitals"
    space_category = "Earth and Space"
    if not frappe.db.exists("Exam Question Category", capitals_category):
        frappe.get_doc({"doctype": "Exam Question Category", "title": capitals_category}).insert()
    if not frappe.db.exists("Exam Question Category", space_category):
        frappe.get_doc({"doctype": "Exam Question Category", "title": space_category}).insert()

    # Multiple choice questions
    mcq_questions = [
        {"question": "What is the capital of France?", "options": ["Paris", "London", "Berlin", "Madrid"], "answer": "Paris", "category": capitals_category,
         "help_show": "Before question",
         "help_text": "<p>Paris has been the capital of France since 987 AD. Sitting on the Seine River, it is often called the <em>City of Light</em> and is home to the Eiffel Tower and the Louvre.</p>",
         "help_quiz": [
             {"quiz_question": "Which river runs through Paris?", "choice_1": "Seine", "choice_2": "Rhône", "choice_3": "Loire", "correct_choice": "1"},
         ]},
        {"question": "What is the capital of Japan?", "options": ["Tokyo", "Beijing", "Seoul", "Bangkok"], "answer": "Tokyo", "category": capitals_category,
         "help_show": "After wrong answer",
         "help_text": "<p>Tokyo became Japan's capital in 1868 during the Meiji Restoration, replacing Kyoto. It was originally a fishing village known as <em>Edo</em>.</p>",
         "help_quiz": [
             {"quiz_question": "What was Tokyo previously known as?", "choice_1": "Edo", "choice_2": "Kyoto", "choice_3": "Osaka", "correct_choice": "1"},
         ]},
        {"question": "What is the capital of Australia?", "options": ["Canberra", "Sydney", "Melbourne", "Perth"], "answer": "Canberra", "category": capitals_category,
         "help_show": "Before question",
         "help_text": "<p>Canberra was purpose-built as a compromise between rival cities Sydney and Melbourne, becoming Australia's capital in 1927. Its name derives from a local Ngunnawal word meaning <em>meeting place</em>.</p>",
         "help_quiz": [
             {"quiz_question": "Why was Canberra chosen as capital?", "choice_1": "It was the largest city", "choice_2": "Compromise between Sydney and Melbourne", "choice_3": "It was the oldest city", "correct_choice": "2"},
         ]},
        {"question": "What is the capital of Canada?", "options": ["Ottawa", "Toronto", "Vancouver", "Montreal"], "answer": "Ottawa", "category": capitals_category,
         "help_show": "After wrong answer",
         "help_text": "<p>Ottawa was selected as Canada's capital by Queen Victoria in 1857 due to its strategic location on the border of English-speaking Ontario and French-speaking Quebec.</p>",
         "help_quiz": [
             {"quiz_question": "Who chose Ottawa as Canada's capital?", "choice_1": "King George III", "choice_2": "Queen Victoria", "choice_3": "Prime Minister Macdonald", "correct_choice": "2"},
         ]},
        {"question": "What is the capital of Brazil?", "options": ["Brasília", "Rio de Janeiro", "São Paulo", "Salvador"], "answer": "Brasília", "category": capitals_category,
         "help_show": "Before question",
         "help_text": "<p>Brasília was inaugurated as Brazil's capital on 21 April 1960, replacing Rio de Janeiro. The city was planned and built from scratch in just 41 months and is a UNESCO World Heritage Site.</p>",
         "help_quiz": [
             {"quiz_question": "Which city did Brasília replace as capital?", "choice_1": "São Paulo", "choice_2": "Salvador", "choice_3": "Rio de Janeiro", "correct_choice": "3"},
         ]},
        {"question": "What is the capital of Egypt?", "options": ["Cairo", "Alexandria", "Giza", "Luxor"], "answer": "Cairo", "category": capitals_category,
         "help_show": "After wrong answer",
         "help_text": "<p>Cairo, founded in 969 AD by the Fatimid dynasty, is Egypt's capital and the largest city in the Arab world. It sits on the banks of the Nile near the ancient pyramids of Giza.</p>",
         "help_quiz": [
             {"quiz_question": "Which river does Cairo sit on?", "choice_1": "Tigris", "choice_2": "Euphrates", "choice_3": "Nile", "correct_choice": "3"},
         ]},
        {"question": "What is the capital of South Korea?", "options": ["Seoul", "Busan", "Incheon", "Daegu"], "answer": "Seoul", "category": capitals_category,
         "help_show": "After wrong answer",
         "help_text": "<p>Seoul has served as Korea's capital for over 600 years, since the founding of the Joseon dynasty in 1394. It sits on the Han River and is home to roughly half of South Korea's population.</p>",
         "help_quiz": [
             {"quiz_question": "Which dynasty established Seoul as the capital in 1394?", "choice_1": "Goryeo", "choice_2": "Joseon", "choice_3": "Silla", "correct_choice": "2"},
         ]},
        {"question": "What is the capital of Argentina?", "options": ["Buenos Aires", "Córdoba", "Rosario", "Mendoza"], "answer": "Buenos Aires", "category": capitals_category,
         "help_show": "After wrong answer",
         "help_text": "<p>Buenos Aires, meaning <em>good airs</em> in Spanish, has been Argentina's capital since 1880. It is the most populous city in the country and a major South American cultural hub.</p>",
         "help_quiz": [
             {"quiz_question": "What does 'Buenos Aires' mean in Spanish?", "choice_1": "Good airs", "choice_2": "Silver river", "choice_3": "New port", "correct_choice": "1"},
         ]},
        {"question": "What is the capital of Turkey?", "options": ["Ankara", "Istanbul", "Izmir", "Antalya"], "answer": "Ankara", "category": capitals_category,
         "help_show": "After wrong answer",
         "help_text": "<p>Ankara replaced Istanbul as Turkey's capital in 1923 when Mustafa Kemal Atatürk founded the modern Turkish Republic. Istanbul remains the country's largest city, but Ankara is the seat of government.</p>",
         "help_quiz": [
             {"quiz_question": "Who founded the modern Turkish Republic?", "choice_1": "Suleiman the Magnificent", "choice_2": "Mustafa Kemal Atatürk", "choice_3": "Mehmed II", "correct_choice": "2"},
         ]},
        {"question": "What is the capital of Russia?", "options": ["Moscow", "Saint Petersburg", "Kazan", "Novosibirsk"], "answer": "Moscow", "category": capitals_category,
         "help_show": "After wrong answer",
         "help_text": "<p>Moscow has been Russia's capital since 1918, when the Bolsheviks moved the seat of government back from Saint Petersburg. The Kremlin, on the banks of the Moskva River, is the official residence of the Russian president.</p>",
         "help_quiz": [
             {"quiz_question": "Which city was Russia's capital before Moscow took over again in 1918?", "choice_1": "Kazan", "choice_2": "Saint Petersburg", "choice_3": "Novosibirsk", "correct_choice": "2"},
         ]},
        {"question": "What is the capital of South Africa (administrative)?", "options": ["Pretoria", "Cape Town", "Johannesburg", "Durban"], "answer": "Pretoria", "category": capitals_category,
         "help_show": "After wrong answer",
         "help_text": "<p>South Africa has three capitals. <strong>Pretoria</strong> is the administrative (executive) capital; Cape Town is legislative and Bloemfontein is judicial. This arrangement dates back to the Union of South Africa in 1910.</p>",
         "help_quiz": [
             {"quiz_question": "How many capital cities does South Africa have?", "choice_1": "One", "choice_2": "Two", "choice_3": "Three", "correct_choice": "3"},
         ]},
        {"question": "Which planet is known as the Red Planet?", "options": ["Mars", "Venus", "Jupiter", "Saturn"], "answer": "Mars", "category": space_category},
        {"question": "What is the largest planet in our solar system?", "options": ["Jupiter", "Saturn", "Neptune", "Uranus"], "answer": "Jupiter", "category": space_category},
        {"question": "What is the name of the galaxy our solar system is in?", "options": ["Milky Way", "Andromeda", "Triangulum", "Whirlpool"], "answer": "Milky Way", "category": space_category},
        {"question": "How many moons does Earth have?", "options": ["1", "2", "3", "4"], "answer": "1", "category": space_category},
        {"question": "What is the closest star to Earth?", "options": ["Sun", "Proxima Centauri", "Alpha Centauri A", "Sirius"], "answer": "Sun", "category": space_category},
    ]

    for q in mcq_questions:
        existing_question = frappe.db.exists("Exam Question",
            {"question": q["question"], "category": q["category"]})

        if existing_question:
            if q.get("help_text"):
                existing_doc = frappe.get_doc("Exam Question", existing_question)
                existing_doc.help_text = q["help_text"]
                existing_doc.help_show = q.get("help_show", "Before question")
                existing_doc.help_quiz = []
                for row in q.get("help_quiz", []):
                    existing_doc.append("help_quiz", row)
                existing_doc.save(ignore_permissions=True)
            continue

        doc = {
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
        }
        if q.get("help_text"):
            doc["help_text"] = q["help_text"]
            doc["help_show"] = q.get("help_show", "Before question")
            if q.get("help_quiz"):
                doc["help_quiz"] = q["help_quiz"]
        frappe.get_doc(doc).insert()

    # User input questions
    user_input_questions = [
        {"question": "What is the capital of Italy?", "answer": "Rome", "category": capitals_category,
         "help_show": "After any answer",
         "help_text": "<p>Rome has been the capital of unified Italy since 1871. The city was the heart of the Roman Empire and is home to Vatican City, the seat of the Catholic Church.</p>",
         "help_quiz": [
             {"quiz_question": "Vatican City, located inside Rome, is the seat of which religion?", "choice_1": "Orthodox Christianity", "choice_2": "Catholicism", "choice_3": "Protestantism", "correct_choice": "2"},
         ]},
        {"question": "What is the capital of Spain?", "answer": "Madrid", "category": capitals_category,
         "help_show": "Before question",
         "help_text": "<p>Madrid became Spain's capital in 1561 under King Philip II. It sits near the geographic centre of the Iberian Peninsula at an elevation of about 650 metres.</p>",
         "help_quiz": [
             {"quiz_question": "Which Spanish king moved the capital to Madrid in 1561?", "choice_1": "Charles V", "choice_2": "Philip II", "choice_3": "Ferdinand II", "correct_choice": "2"},
         ]},
        {"question": "What is the capital of Germany?", "answer": "Berlin", "category": capitals_category,
         "help_show": "After any answer",
         "help_text": "<p>Berlin was restored as the capital of a reunified Germany in 1990, taking over from Bonn. The Berlin Wall, which divided the city from 1961, fell in November 1989.</p>",
         "help_quiz": [
             {"quiz_question": "Which city served as West Germany's capital before reunification?", "choice_1": "Frankfurt", "choice_2": "Bonn", "choice_3": "Munich", "correct_choice": "2"},
         ]},
        {"question": "What is the name of the force that holds us to the Earth?", "answer": "Gravity", "category": space_category},
        {"question": "What is the fifth planet from the sun?", "answer": "Jupiter", "category": space_category},
    ]

    for q in user_input_questions:
        existing_question = frappe.db.exists("Exam Question",
            {"question": q["question"], "category": q["category"]})

        if existing_question:
            if q.get("help_text"):
                existing_doc = frappe.get_doc("Exam Question", existing_question)
                existing_doc.help_text = q["help_text"]
                existing_doc.help_show = q.get("help_show", "Before question")
                existing_doc.help_quiz = []
                for row in q.get("help_quiz", []):
                    existing_doc.append("help_quiz", row)
                existing_doc.save(ignore_permissions=True)
            continue

        doc = {
            "doctype": "Exam Question",
            "question": q["question"],
            "category": q["category"],
            "mark": 2,
            "type": "User Input",
            "possibility_1": q["answer"],
        }
        if q.get("help_text"):
            doc["help_text"] = q["help_text"]
            doc["help_show"] = q.get("help_show", "Before question")
            if q.get("help_quiz"):
                doc["help_quiz"] = q["help_quiz"]
        frappe.get_doc(doc).insert()

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

    # Create sample certificate template
    if not frappe.db.exists("Exam Certificate Template", "Sample Certificate Template"):
        sample_html_template = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {
                        font-family: 'Times New Roman', serif;
                        margin: 0;
                        padding: 50px;
                        background-color: #f9f9f9;
                    }
                    .certificate {
                        background: white;
                        border: 10px solid #1e3a8a;
                        border-radius: 20px;
                        padding: 80px 60px;
                        text-align: center;
                        box-shadow: 0 0 20px rgba(0,0,0,0.1);
                        max-width: 800px;
                        margin: 0 auto;
                    }
                    .header {
                        font-size: 48px;
                        color: #1e3a8a;
                        font-weight: bold;
                        margin-bottom: 20px;
                        text-transform: uppercase;
                        letter-spacing: 3px;
                    }
                    .subtitle {
                        font-size: 24px;
                        color: #666;
                        margin-bottom: 40px;
                    }
                    .recipient {
                        font-size: 36px;
                        color: #333;
                        font-weight: bold;
                        margin: 40px 0;
                        text-decoration: underline;
                    }
                    .achievement {
                        font-size: 20px;
                        color: #333;
                        margin: 30px 0;
                        line-height: 1.6;
                    }
                    .exam-details {
                        font-size: 18px;
                        color: #555;
                        margin: 20px 0;
                    }
                    .signature-section {
                        display: flex;
                        justify-content: space-between;
                        margin-top: 80px;
                        font-size: 16px;
                    }
                    .signature {
                        text-align: center;
                        width: 200px;
                    }
                    .signature-line {
                        border-top: 2px solid #333;
                        margin: 10px 0 5px 0;
                    }
                    .date {
                        text-align: right;
                        margin-top: 40px;
                        font-size: 14px;
                        color: #666;
                    }
                </style>
            </head>
            <body>
                <div class="certificate">
                    <div class="header">Certificate of Achievement</div>
                    <div class="subtitle">This is to certify that</div>
                    
                    <div class="recipient">{{ student_name or "Student Name" }}</div>
                    
                    <div class="achievement">
                        has successfully completed the examination
                    </div>
                    
                    <div class="exam-details">
                        <strong>{{ exam_title or "Exam Title" }}</strong><br>
                        Score: {{ score or "0" }}% ({{ marks_obtained or "0" }}/{{ total_marks or "0" }} marks)<br>
                        {% if pass_percentage %}Passing Grade: {{ pass_percentage }}%{% endif %}
                    </div>
                    
                    <div class="achievement">
                        and has demonstrated proficiency in the subject matter
                    </div>
                    
                    <div class="signature-section">
                        <div class="signature">
                            <div class="signature-line"></div>
                            <div>Instructor</div>
                        </div>
                        <div class="signature">
                            <div class="signature-line"></div>
                            <div>Administrator</div>
                        </div>
                    </div>
                    
                    <div class="date">
                        Date: {{ completion_date or frappe.utils.format_date(frappe.utils.nowdate(), "dd MMM yyyy") }}
                    </div>
                </div>
            </body>
            </html>
        """
        
        sample_wkhtmltopdf_params = """{
            "page-size": "A4",
            "orientation": "Landscape",
            "margin-top": "0.5in",
            "margin-right": "0.5in",
            "margin-bottom": "0.5in",
            "margin-left": "0.5in",
            "encoding": "UTF-8",
            "no-outline": null,
            "enable-local-file-access": null
        }"""
        
        frappe.get_doc({
            "doctype": "Exam Certificate Template",
            "title": "Sample Certificate Template",
            "html_template": sample_html_template.strip(),
            "wkhtmltopdf_params": sample_wkhtmltopdf_params
        }).insert()

    frappe.db.commit()

    create_sample_quizzes()

    frappe.msgprint("Sample exams, questions, and certificate template created successfully.")


def create_sample_quizzes():
    kahoot_quiz_title = "World Capitals Speed Round"
    if not frappe.db.exists("Quick Quiz", {"title": kahoot_quiz_title}):
        frappe.get_doc({
            "doctype": "Quick Quiz",
            "title": kahoot_quiz_title,
            "quiz_mode": "Kahoot",
            "status": "Published",
            "access_type": "PIN",
            "pin_code": "1234",
            "timer_enabled": 1,
            "timer_seconds": 15,
            "theme": "Fun Neon",
            "randomize_questions": 0,
            "show_correct_after_answer": 1,
            "description": "Race against the clock! How many world capitals can you get right?",
            "questions": [
                {
                    "question": "What is the capital of France?",
                    "option_1": "Paris", "option_2": "London", "option_3": "Berlin", "option_4": "Madrid",
                    "is_correct_1": 1, "is_correct_2": 0, "is_correct_3": 0, "is_correct_4": 0,
                    "explanation": "Paris has been the capital of France since 987 AD.",
                    "points": 100,
                },
                {
                    "question": "What is the capital of Japan?",
                    "option_1": "Beijing", "option_2": "Tokyo", "option_3": "Seoul", "option_4": "Bangkok",
                    "is_correct_1": 0, "is_correct_2": 1, "is_correct_3": 0, "is_correct_4": 0,
                    "explanation": "Tokyo became Japan's capital in 1868 during the Meiji Restoration.",
                    "points": 100,
                },
                {
                    "question": "What is the capital of Australia?",
                    "option_1": "Sydney", "option_2": "Melbourne", "option_3": "Canberra", "option_4": "Perth",
                    "is_correct_1": 0, "is_correct_2": 0, "is_correct_3": 1, "is_correct_4": 0,
                    "explanation": "Canberra was purpose-built as a compromise between Sydney and Melbourne.",
                    "points": 100,
                },
                {
                    "question": "What is the capital of Brazil?",
                    "option_1": "Rio de Janeiro", "option_2": "São Paulo", "option_3": "Salvador", "option_4": "Brasília",
                    "is_correct_1": 0, "is_correct_2": 0, "is_correct_3": 0, "is_correct_4": 1,
                    "explanation": "Brasília was inaugurated as the capital in 1960, replacing Rio de Janeiro.",
                    "points": 100,
                },
                {
                    "question": "What is the capital of Canada?",
                    "option_1": "Toronto", "option_2": "Vancouver", "option_3": "Ottawa", "option_4": "Montreal",
                    "is_correct_1": 0, "is_correct_2": 0, "is_correct_3": 1, "is_correct_4": 0,
                    "explanation": "Ottawa was selected by Queen Victoria in 1857.",
                    "points": 100,
                },
            ],
        }).insert(ignore_permissions=True)

    simple_quiz_title = "Science Quick Check"
    if not frappe.db.exists("Quick Quiz", {"title": simple_quiz_title}):
        frappe.get_doc({
            "doctype": "Quick Quiz",
            "title": simple_quiz_title,
            "quiz_mode": "Simple",
            "status": "Published",
            "access_type": "Auth",
            "timer_enabled": 0,
            "theme": "Default",
            "randomize_questions": 0,
            "show_correct_after_answer": 1,
            "description": "A quick science check — test your basic science knowledge.",
            "questions": [
                {
                    "question": "Which planet is known as the Red Planet?",
                    "option_1": "Mars", "option_2": "Venus", "option_3": "Jupiter", "option_4": "Saturn",
                    "is_correct_1": 1, "is_correct_2": 0, "is_correct_3": 0, "is_correct_4": 0,
                    "explanation": "Mars appears red due to iron oxide (rust) on its surface.",
                    "points": 100,
                },
                {
                    "question": "What is the chemical symbol for water?",
                    "option_1": "CO2", "option_2": "H2O", "option_3": "O2", "option_4": "NaCl",
                    "is_correct_1": 0, "is_correct_2": 1, "is_correct_3": 0, "is_correct_4": 0,
                    "explanation": "H2O represents two hydrogen atoms bonded to one oxygen atom.",
                    "points": 100,
                },
                {
                    "question": "What gas do plants absorb from the atmosphere?",
                    "option_1": "Oxygen", "option_2": "Nitrogen", "option_3": "Carbon Dioxide", "option_4": "Hydrogen",
                    "is_correct_1": 0, "is_correct_2": 0, "is_correct_3": 1, "is_correct_4": 0,
                    "explanation": "Plants use CO2 in photosynthesis to produce oxygen and glucose.",
                    "points": 100,
                },
                {
                    "question": "What is the largest organ in the human body?",
                    "option_1": "Heart", "option_2": "Liver", "option_3": "Brain", "option_4": "Skin",
                    "is_correct_1": 0, "is_correct_2": 0, "is_correct_3": 0, "is_correct_4": 1,
                    "explanation": "The skin covers about 20 square feet in adults.",
                    "points": 100,
                },
                {
                    "question": "How many bones are in the adult human body?",
                    "option_1": "106", "option_2": "206", "option_3": "306", "option_4": "406",
                    "is_correct_1": 0, "is_correct_2": 1, "is_correct_3": 0, "is_correct_4": 0,
                    "explanation": "Adults have 206 bones; babies are born with about 270 that fuse over time.",
                    "points": 100,
                },
            ],
        }).insert(ignore_permissions=True)

    frappe.db.commit()


def validate_user_email(doc, method=None):
    """
    Validate the email with optional list in Exam Settings
    """
    if not doc.email:
        return

    # Get the list of allowed emails from Exam Settings
    allowed_emails = frappe.get_single("Exam Settings").restrict_user_account_domains or ""
    allowed_emails = [email.strip() for email in allowed_emails.split(",") if email.strip()]
    if allowed_emails:
        # Check if the user's email domain is in the allowed list
        user_email_domain = doc.email.split('@')[-1]
        if user_email_domain not in allowed_emails:
            frappe.throw(f"Email domain '{user_email_domain}' is not allowed.")

def submit_candidate_pending_exams(member=None):
    """
    Submit any pending exams for the user.
    Uses lightweight queries instead of full doc.save() to avoid
    loading and re-saving all child Exam Answer rows.
    """
    submissions = frappe.get_all(
        "Exam Submission",
        {
            "candidate": member or frappe.session.user,
            "status": ["in", ["Registered", "Started"]]
        },
        ["name", "exam_schedule", "exam", "status", "additional_time_given"],
        ignore_permissions=True
    )
    for submission in submissions:
        sched = frappe.get_doc("Exam Schedule", submission["exam_schedule"])
        if sched.get_status(additional_time=submission["additional_time_given"]) != "Completed":
            continue

        new_status = "Submitted" if submission["status"] == "Started" else "Not Attempted"

        answers = frappe.get_all(
            "Exam Answer",
            filters={"parent": submission["name"]},
            fields=["mark", "is_correct", "evaluation_status"],
        )
        total_marks, evaluation_status, result_status = evaluation_values(
            submission["exam"], answers
        )

        frappe.db.set_value("Exam Submission", submission["name"], {
            "status": new_status,
            "exam_submitted_time": frappe.utils.now(),
            "total_marks": total_marks,
            "evaluation_status": evaluation_status,
            "result_status": result_status,
        })

        cache_key = f"tracking_data:{submission['name']}"
        frappe.cache().delete_value(cache_key)

        frappe.db.commit()

def can_show_exam_results_for_leaderboard(exam_doc, submission_doc):
    """Check if exam results can be shown for leaderboard based on show_result settings"""
    
    # If submission is not yet submitted or evaluated, don't show leaderboard
    if submission_doc.status != "Submitted" or submission_doc.evaluation_status == "Pending":
        return False
    
    # Check result display settings
    show_result = exam_doc.show_result
    
    if show_result == "After Specific Date":
        if datetime.now() < exam_doc.show_result_after_date:
            return False
        return True
    elif show_result == "Do Not Show Score":
        return False
    elif show_result == "After Exam Submission":
        return True
    elif show_result == "After Schedule Completion":
        schedule = frappe.get_doc("Exam Schedule", submission_doc.exam_schedule)
        return schedule.get_status(additional_time=submission_doc.additional_time_given) == "Completed"

    # Default: don't show if no valid setting found
    return False


def calculate_attention_score(exam_submission):
    """
    Calculate attention score for exam proctoring
    
    Args:
        exam_submission (str): Name of the exam submission document
        face_changes (int): Number of face count changes detected
        total_away_time (int): Total seconds with no face detected
        total_distracted_time (int): Total seconds looking away/distracted
        config (dict, optional): Configuration overrides
    
    Returns:
        dict: Score and breakdown
    """
    
    # Default configuration
    default_config = {
        'away_weight': 0.45,
        'changes_weight': 0.30,
        'distracted_weight': 0.25,
        'max_away_percent': 5.0,
        'max_changes_per_hour': 3.0,
        'max_distracted_percent': 20.0
    }
    
    # Merge with user config
    cfg = default_config.copy()
    # if config:
    #     cfg.update(config)

    values = frappe.db.get_value(
        "Exam Submission", exam_submission,
        "exam_started_time, total_away_time, total_distracted_time, face_count_changes"
    )
    exam_started_time, total_away_time, total_distracted_time, face_changes = \
        values or (None, 0, 0, 0)

    # Without a start time there is nothing meaningful to score. Return quietly
    # instead of throwing — this runs inside the answer-save path and must never
    # surface as an internal error to the candidate.
    if not exam_started_time:
        frappe.logger().warning(
            f"calculate_attention_score: {exam_submission} has no start time; skipping."
        )
        return None

    # Coerce possibly-null metrics to numbers.
    total_away_time = total_away_time or 0
    total_distracted_time = total_distracted_time or 0
    face_changes = face_changes or 0

    # Calculate exam duration in seconds
    duration_seconds = (datetime.now() - exam_started_time).total_seconds()
    if duration_seconds <= 0:
        # Exam just started (or clock skew): no measurable window yet to score.
        frappe.logger().warning(
            f"calculate_attention_score: {exam_submission} duration<=0; skipping."
        )
        return None
    duration_hours = duration_seconds / 3600

    # Calculate percentages and rates
    away_percent = (total_away_time / duration_seconds) * 100
    distracted_percent = (total_distracted_time / duration_seconds) * 100
    changes_per_hour = face_changes / duration_hours if duration_hours > 0 else 0
    
    # Calculate component scores (0-100)
    away_score = max(0, 100 - max(0, away_percent - cfg['max_away_percent']) * 5)
    changes_score = max(0, 100 - max(0, changes_per_hour - cfg['max_changes_per_hour']) * 15)
    distracted_score = max(0, 100 - max(0, distracted_percent - cfg['max_distracted_percent']) * 2)
    
    # Calculate weighted final score
    final_score = (
        away_score * cfg['away_weight'] +
        changes_score * cfg['changes_weight'] +
        distracted_score * cfg['distracted_weight']
    )
    
    # Round to 1 decimal place
    final_score = round(final_score, 1)
    frappe.db.set_value("Exam Submission", exam_submission, {
        "attention_score": final_score
    })
    frappe.db.commit()
    
    return {
        'score': final_score,
        'away_percent': round(away_percent, 1),
        'distracted_percent': round(distracted_percent, 1),
        'changes_per_hour': round(changes_per_hour, 1),
        'duration_minutes': round(duration_seconds / 60, 1)
    }