import frappe

from exampro.exam_pro.api.examops import evaluation_values

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
	frappe.msgprint("Sample exams, questions, and certificate template created successfully.")

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
	This is useful for exams that are not submitted automatically.
	"""
	submissions = frappe.get_all(
		"Exam Submission",
		{
			"candidate": member or frappe.session.user,
			"status": ["in", ["Registered", "Started"]]
		}, 
		["name", "exam_schedule", "status", "additional_time_given"],
		ignore_permissions=True
	)
	for submission in submissions:
		sched = frappe.get_doc("Exam Schedule", submission["exam_schedule"], ignore_permissions=True)
		if sched.get_status(additional_time=submission["additional_time_given"]) == "Completed":
			doc = frappe.get_doc("Exam Submission", submission["name"], ignore_permissions=True)
			if doc.status == "Started":
				doc.status = "Submitted"
			elif doc.status == "Registered":
				doc.status = "Not Attempted"
			total_marks, evaluation_status, result_status = evaluation_values(
				doc.exam, doc.submitted_answers
			)
			doc.total_marks = total_marks
			doc.evaluation_status = evaluation_status
			doc.result_status = result_status
			doc.save(ignore_permissions=True)
			frappe.db.commit()