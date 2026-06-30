import base64
import json
import re

import frappe
from frappe.utils import now_datetime
import requests


CACHE_KEY_PREFIX = "exam_studio_state:"
CACHE_TTL = 86400  # 24 hours

IMAGE_STYLE_PROMPTS = {
	"realistic": "Photorealistic style, high detail, natural lighting, like a professional photograph. Do NOT include any text, words, letters, numbers, labels, captions, watermarks, or writing of any kind in the image.",
	"cartoon": "Cartoon illustration style, clean lines, vibrant colors, friendly and approachable like a textbook illustration. Do NOT include any text, words, letters, numbers, labels, captions, watermarks, or writing of any kind in the image.",
	"exampro_slider": "Flat vector illustration in the style of Humaans. Use a yellow (#F5C344) and black (#212529) color palette with subtle gray accents. Minimalist, geometric, modern, clean background. Do NOT include any text, words, letters, numbers, labels, captions, watermarks, or writing of any kind in the image.",
}


@frappe.whitelist()
def get_cached_state():
	key = CACHE_KEY_PREFIX + frappe.session.user
	data = frappe.cache.get_value(key)
	return data or {}


@frappe.whitelist()
def set_cached_state(state):
	if isinstance(state, str):
		state = json.loads(state)
	key = CACHE_KEY_PREFIX + frappe.session.user
	frappe.cache.set_value(key, state, expires_in_sec=CACHE_TTL)
	return {"ok": True}


@frappe.whitelist()
def clear_cached_state():
	key = CACHE_KEY_PREFIX + frappe.session.user
	frappe.cache.delete_value(key)
	return {"ok": True}


@frappe.whitelist()
def get_category_questions(category):
	if "Exam Manager" not in frappe.get_roles():
		frappe.throw("You are not authorized to perform this action", frappe.PermissionError)

	questions = frappe.get_all(
		"Exam Question",
		filters={"category": category},
		fields=[
			"name", "question", "type", "category", "mark", "difficulty",
			"option_1", "option_2", "option_3", "option_4",
			"is_correct_1", "is_correct_2", "is_correct_3", "is_correct_4",
			"explanation_1", "explanation_2", "explanation_3", "explanation_4",
			"possibility_1", "possibility_2", "possibility_3", "possibility_4",
			"help_show", "help_type", "help_text", "help_link",
			"description_image", "option_1_image", "option_2_image",
			"option_3_image", "option_4_image", "helper_text_image",
		],
		order_by="modified desc",
	)

	result = []
	for q in questions:
		item = {
			"name": q.name,
			"question": q.question,
			"type": q.type,
			"category": q.category,
			"mark": q.mark,
			"difficulty": q.difficulty or "",
			"_existing": True,
			"help_show": q.help_show or "Do not show",
			"help_type": q.help_type or "Text",
			"help_text": q.help_text or "",
			"help_link": q.help_link or "",
			"help_quiz": [],
			"description_image": q.description_image or "",
			"helper_text_image": q.helper_text_image or "",
		}

		if q.type == "Choices":
			item["options"] = []
			for i in range(1, 5):
				text = q.get(f"option_{i}")
				if text:
					item["options"].append({
						"text": text,
						"is_correct": bool(q.get(f"is_correct_{i}")),
						"explanation": q.get(f"explanation_{i}") or "",
						"image": q.get(f"option_{i}_image") or "",
					})
		elif q.type == "User Input":
			item["possible_answers"] = [
				q.get(f"possibility_{i}") for i in range(1, 5)
				if q.get(f"possibility_{i}")
			]

		doc = frappe.get_doc("Exam Question", q.name)
		if doc.help_quiz:
			for hq in doc.help_quiz:
				item["help_quiz"].append({
					"quiz_question": hq.quiz_question,
					"choice_1": hq.choice_1,
					"choice_2": hq.choice_2,
					"choice_3": hq.choice_3 or "",
					"correct_choice": hq.correct_choice,
				})

		result.append(item)

	return {"questions": result}


@frappe.whitelist()
def generate_questions(category, count, difficulty, question_type, prompt="", mark=1, file_content=""):
	if "Exam Manager" not in frappe.get_roles():
		frappe.throw("You are not authorized to perform this action", frappe.PermissionError)

	count = int(count)
	if count < 1 or count > 20:
		frappe.throw("Number of questions must be between 1 and 20")
	if difficulty not in ("Simple", "Medium", "Hard"):
		frappe.throw("Invalid difficulty level")
	if question_type not in ("Choices", "User Input"):
		frappe.throw("Invalid question type")

	prompt = (prompt or "").strip()
	file_content = (file_content or "").strip()

	if not prompt and not file_content:
		frappe.throw("Please provide a topic/instructions or upload a file.")

	settings = frappe.get_single("Exam Settings")
	api_key, model = settings.get_openrouter_config()

	system_prompt = build_system_prompt(count, difficulty, question_type, category)
	user_prompt = build_user_prompt(prompt, file_content, count, difficulty, question_type, category)

	try:
		response = requests.post(
			"https://openrouter.ai/api/v1/chat/completions",
			headers={
				"Authorization": f"Bearer {api_key}",
				"Content-Type": "application/json",
			},
			json={
				"model": model,
				"messages": [
					{"role": "system", "content": system_prompt},
					{"role": "user", "content": user_prompt},
				],
				"temperature": 0.7,
			},
			timeout=120,
		)
	except requests.exceptions.Timeout:
		frappe.throw("Request timed out. Try reducing the number of questions or try again later.")
	except requests.exceptions.RequestException as e:
		frappe.throw(f"Network error: {str(e)}")

	if response.status_code == 401 or response.status_code == 403:
		frappe.throw("Invalid OpenRouter API key. Check your key in Exam Settings > AI Settings.")
	if response.status_code == 429:
		frappe.throw("Rate limited by OpenRouter. Please wait a moment and try again.")
	if response.status_code != 200:
		frappe.throw(f"OpenRouter API error (HTTP {response.status_code}). Please try again.")

	try:
		data = response.json()
		content = data["choices"][0]["message"]["content"]
	except (KeyError, IndexError, json.JSONDecodeError):
		frappe.throw("Unexpected response from AI. Please try again.")

	questions = parse_questions_json(content)
	if not questions:
		frappe.throw("Could not parse AI response. Please try again with a different prompt.")

	for q in questions:
		q["category"] = category
		q["type"] = question_type
		q["difficulty"] = difficulty
		q["mark"] = int(mark)

	return {"questions": questions}


@frappe.whitelist()
def save_questions(questions):
	if "Exam Manager" not in frappe.get_roles():
		frappe.throw("You are not authorized to perform this action", frappe.PermissionError)

	if isinstance(questions, str):
		questions = json.loads(questions)

	created = 0
	failed = []

	for q in questions:
		try:
			doc = frappe.get_doc({
				"doctype": "Exam Question",
				"question": q.get("question", ""),
				"category": q.get("category", ""),
				"type": q.get("type", "Choices"),
				"mark": q.get("mark", 1),
				"difficulty": q.get("difficulty", ""),
				"help_show": q.get("help_show", "Do not show"),
				"help_text": q.get("help_text", ""),
				"description_image": q.get("description_image", ""),
				"helper_text_image": q.get("helper_text_image", ""),
			})

			for hq in q.get("help_quiz", []):
				if hq.get("quiz_question"):
					doc.append("help_quiz", {
						"quiz_question": hq["quiz_question"],
						"choice_1": hq.get("choice_1", ""),
						"choice_2": hq.get("choice_2", ""),
						"choice_3": hq.get("choice_3", ""),
						"correct_choice": hq.get("correct_choice", "1"),
					})

			if q.get("type") == "Choices":
				options = q.get("options", [])
				for i, opt in enumerate(options[:4], 1):
					doc.set(f"option_{i}", opt.get("text", ""))
					doc.set(f"is_correct_{i}", 1 if opt.get("is_correct") else 0)
					doc.set(f"explanation_{i}", opt.get("explanation", ""))
					doc.set(f"option_{i}_image", opt.get("image", ""))
			elif q.get("type") == "User Input":
				answers = q.get("possible_answers", [])
				for i, ans in enumerate(answers[:4], 1):
					doc.set(f"possibility_{i}", ans)

			doc.insert()
			created += 1
		except Exception as e:
			preview = q.get("question", "")[:80]
			failed.append({"question": preview, "error": str(e)})

	return {"created": created, "failed": failed}


@frappe.whitelist()
def update_question(name, data):
	if "Exam Manager" not in frappe.get_roles():
		frappe.throw("You are not authorized to perform this action", frappe.PermissionError)

	if isinstance(data, str):
		data = json.loads(data)

	doc = frappe.get_doc("Exam Question", name)

	doc.question = data.get("question", doc.question)
	doc.mark = data.get("mark", doc.mark)
	doc.difficulty = data.get("difficulty", doc.difficulty)
	doc.description_image = data.get("description_image", doc.description_image)
	doc.helper_text_image = data.get("helper_text_image", doc.helper_text_image)

	if doc.type == "Choices":
		options = data.get("options", [])
		for i in range(1, 5):
			if i <= len(options):
				opt = options[i - 1]
				doc.set(f"option_{i}", opt.get("text", ""))
				doc.set(f"is_correct_{i}", 1 if opt.get("is_correct") else 0)
				doc.set(f"explanation_{i}", opt.get("explanation", ""))
				doc.set(f"option_{i}_image", opt.get("image", ""))
	elif doc.type == "User Input":
		answers = data.get("possible_answers", [])
		for i in range(1, 5):
			doc.set(f"possibility_{i}", answers[i - 1] if i <= len(answers) else "")

	doc.help_show = data.get("help_show", doc.help_show)
	doc.help_type = data.get("help_type", doc.help_type)
	doc.help_text = data.get("help_text", doc.help_text)
	doc.help_link = data.get("help_link", doc.help_link)

	if "help_quiz" in data:
		doc.help_quiz = []
		for hq in data.get("help_quiz", []):
			if hq.get("quiz_question"):
				doc.append("help_quiz", {
					"quiz_question": hq["quiz_question"],
					"choice_1": hq.get("choice_1", ""),
					"choice_2": hq.get("choice_2", ""),
					"choice_3": hq.get("choice_3", ""),
					"correct_choice": hq.get("correct_choice", "1"),
				})

	doc.save()
	return {"ok": True}


@frappe.whitelist()
def generate_help_text(question, options=None, possible_answers=None, question_type="Choices", category="", text_size="medium"):
	if "Exam Manager" not in frappe.get_roles():
		frappe.throw("You are not authorized to perform this action", frappe.PermissionError)

	if text_size not in ("compact", "medium", "large"):
		frappe.throw("Invalid text size")

	settings = frappe.get_single("Exam Settings")
	api_key, model = settings.get_openrouter_config()

	size_guide = {
		"compact": "Keep it brief — 2-3 short paragraphs, under 150 words. Cover only the core concept.",
		"medium": "Write a moderate tutorial — 4-6 paragraphs, around 250-350 words. Explain the concept, why each option is right or wrong, and give a practical example.",
		"large": "Write a thorough tutorial — 8-12 paragraphs, around 500-700 words. Cover the concept in depth with examples, common misconceptions, edge cases, and practical tips.",
	}

	system_prompt = f"""You are an expert tutor creating learning material for exam preparation in the category "{category}".

Write a helper text that teaches the concept tested by the given question. The tone must be training/teaching — like a tutorial explaining the topic to someone studying for an exam.

{size_guide[text_size]}

Rules:
- Do NOT restate the question or list the options
- Do NOT reveal the correct answer directly — teach the underlying concept so the reader can figure it out
- Return valid HTML using <p>, <strong>, <em>, <ul>/<ol>/<li> tags for structure
- Do NOT use markdown — output HTML only
- Do NOT wrap in a root element or add <html>/<body> tags, just the content paragraphs
- Write in a clear, approachable teaching style
- Return ONLY the tutorial HTML, nothing else"""

	answer_context = ""
	if question_type == "Choices" and options:
		if isinstance(options, str):
			options = json.loads(options)
		parts = []
		for i, opt in enumerate(options, 1):
			correct = " (correct)" if opt.get("is_correct") else ""
			parts.append(f"  Option {i}: {opt.get('text', '')}{correct}")
		answer_context = "\nOptions:\n" + "\n".join(parts)
	elif question_type == "User Input" and possible_answers:
		if isinstance(possible_answers, str):
			possible_answers = json.loads(possible_answers)
		answer_context = "\nAccepted answers: " + ", ".join(possible_answers)

	user_prompt = f"Question: {question}{answer_context}"

	try:
		response = requests.post(
			"https://openrouter.ai/api/v1/chat/completions",
			headers={
				"Authorization": f"Bearer {api_key}",
				"Content-Type": "application/json",
			},
			json={
				"model": model,
				"messages": [
					{"role": "system", "content": system_prompt},
					{"role": "user", "content": user_prompt},
				],
				"temperature": 0.6,
			},
			timeout=120,
		)
	except requests.exceptions.Timeout:
		frappe.throw("Request timed out. Please try again.")
	except requests.exceptions.RequestException as e:
		frappe.throw(f"Network error: {str(e)}")

	if response.status_code != 200:
		frappe.throw(f"OpenRouter API error (HTTP {response.status_code}). Please try again.")

	try:
		data = response.json()
		text = data["choices"][0]["message"]["content"].strip()
	except (KeyError, IndexError, json.JSONDecodeError):
		frappe.throw("Unexpected response from AI. Please try again.")

	return {"help_text": text}


@frappe.whitelist()
def generate_image(prompt, style, field_context="description_image"):
	if "Exam Manager" not in frappe.get_roles():
		frappe.throw("You are not authorized to perform this action", frappe.PermissionError)

	if style not in IMAGE_STYLE_PROMPTS:
		frappe.throw("Invalid image style")

	prompt = (prompt or "").strip()
	if not prompt:
		frappe.throw("Please provide text content to generate an image for.")

	settings = frappe.get_single("Exam Settings")
	api_key = settings.get_password("openrouter_api_key")
	if not api_key:
		frappe.throw("OpenRouter API key is not configured. Go to Exam Settings > AI Settings to add it.")

	image_model = settings.get_image_model()
	style_prompt = IMAGE_STYLE_PROMPTS[style]
	full_prompt = f"Generate a purely visual, representational image for the following exam content. The image must contain NO text, words, letters, numbers, or writing of any kind — it should be a visual representation only.\n\n{prompt}\n\nStyle: {style_prompt}"

	try:
		response = requests.post(
			"https://openrouter.ai/api/v1/chat/completions",
			headers={
				"Authorization": f"Bearer {api_key}",
				"Content-Type": "application/json",
			},
			data=json.dumps({
				"model": image_model,
				"messages": [
					{"role": "user", "content": full_prompt},
				],
				"modalities": ["image"],
			}),
			timeout=120,
		)
	except requests.exceptions.Timeout:
		frappe.throw("Image generation timed out. Please try again.")
	except requests.exceptions.RequestException as e:
		frappe.throw(f"Network error: {str(e)}")

	if response.status_code == 401 or response.status_code == 403:
		frappe.throw("Invalid OpenRouter API key. Check your key in Exam Settings > AI Settings.")
	if response.status_code == 429:
		frappe.throw("Rate limited by OpenRouter. Please wait a moment and try again.")
	if response.status_code != 200:
		frappe.throw(f"Image generation failed (HTTP {response.status_code}). Please try again.")

	try:
		data = response.json()
		message = data["choices"][0]["message"]
	except (KeyError, IndexError, json.JSONDecodeError):
		frappe.throw("Unexpected response from image generation API. Please try again.")

	image_b64_url = None
	if message.get("images"):
		image_b64_url = message["images"][0].get("image_url", {}).get("url")

	if not image_b64_url:
		image_b64_url = _extract_image_url(message.get("content", ""))

	if not image_b64_url:
		frappe.throw("No image was generated. Please try again with a different prompt.")

	if image_b64_url.startswith("data:"):
		header, b64_data = image_b64_url.split(",", 1)
		image_bytes = base64.b64decode(b64_data)
	elif image_b64_url.startswith("http"):
		try:
			img_response = requests.get(image_b64_url, timeout=60)
			img_response.raise_for_status()
			image_bytes = img_response.content
		except requests.exceptions.RequestException:
			frappe.throw("Failed to download generated image. Please try again.")
	else:
		image_bytes = base64.b64decode(image_b64_url)

	file_name = f"{field_context}_{frappe.generate_hash()[:8]}.png"
	file_doc = frappe.get_doc({
		"doctype": "File",
		"file_name": file_name,
		"content": image_bytes,
		"is_private": 0,
	})
	file_doc.save()

	return {"file_url": file_doc.file_url}


def _extract_image_url(content):
	if isinstance(content, list):
		for part in content:
			if isinstance(part, dict):
				if part.get("type") == "image_url":
					url = part.get("image_url", {})
					if isinstance(url, dict):
						return url.get("url", "")
					return url or ""
	if isinstance(content, str):
		match = re.search(r'https?://[^\s"\'<>]+\.(?:png|jpg|jpeg|webp|gif)', content)
		if match:
			return match.group(0)
	return None


# --- Exams tab API ---


@frappe.whitelist()
def get_exams():
	if "Exam Manager" not in frappe.get_roles():
		frappe.throw("You are not authorized to perform this action", frappe.PermissionError)

	return _get_recent_exams()


def _get_recent_exams(limit=10):
	rows = frappe.db.sql(
		"""
		SELECT DISTINCT e.name, e.title, e.exam_mode, e.duration,
			   e.question_type, e.total_questions, e.total_marks, e.certificate_template
		FROM `tabExam` e
		LEFT JOIN `tabExam Schedule` s ON s.exam = e.name
		ORDER BY COALESCE(s.start_date_time, e.modified) DESC
		LIMIT %(limit)s
		""",
		{"limit": limit},
		as_dict=True,
	)
	return rows


@frappe.whitelist()
def search_categories(query):
	if "Exam Manager" not in frappe.get_roles():
		frappe.throw("You are not authorized to perform this action", frappe.PermissionError)

	query = (query or "").strip()
	if not query or len(query) < 2:
		return []

	like = f"%{query}%"
	rows = frappe.db.sql(
		"""
		SELECT c.name, c.title,
		       (SELECT COUNT(*) FROM `tabExam Question` q WHERE q.category = c.name) AS question_count
		FROM `tabExam Question Category` c
		WHERE c.title LIKE %(like)s
		ORDER BY c.modified DESC
		LIMIT 20
		""",
		{"like": like},
		as_dict=True,
	)
	return rows


@frappe.whitelist()
def search_exams(query):
	if "Exam Manager" not in frappe.get_roles():
		frappe.throw("You are not authorized to perform this action", frappe.PermissionError)

	query = (query or "").strip()
	if not query or len(query) < 2:
		return []

	like = f"%{query}%"
	return frappe.db.sql(
		"""
		SELECT name, title, exam_mode, duration, question_type,
			   total_questions, total_marks
		FROM `tabExam`
		WHERE title LIKE %(like)s
		ORDER BY modified DESC
		LIMIT 20
		""",
		{"like": like},
		as_dict=True,
	)


@frappe.whitelist()
def get_exam_detail(name):
	if "Exam Manager" not in frappe.get_roles():
		frappe.throw("You are not authorized to perform this action", frappe.PermissionError)

	doc = frappe.get_doc("Exam", name)
	return {
		"name": doc.name,
		"title": doc.title,
		"exam_mode": doc.exam_mode,
		"duration": doc.duration,
		"pass_percentage": doc.pass_percentage,
		"question_type": doc.question_type,
		"description": doc.description or "",
		"instructions": doc.instructions or "",
		"randomize_questions": bool(doc.randomize_questions),
		"select_questions": [
			{
				"question_category": sq.question_category,
				"no_of_questions": sq.no_of_questions,
				"mark_per_question": sq.mark_per_question,
			}
			for sq in (doc.select_questions or [])
		],
	}


@frappe.whitelist()
def get_exam_schedules(exam):
	if "Exam Manager" not in frappe.get_roles():
		frappe.throw("You are not authorized to perform this action", frappe.PermissionError)

	schedules = frappe.get_all(
		"Exam Schedule",
		filters={"exam": exam},
		fields=["name", "start_date_time", "schedule_type", "duration",
				"schedule_expire_in_days", "badge", "short_uuid", "certificate_template"],
		order_by="start_date_time desc",
	)

	now = now_datetime()
	for sch in schedules:
		sch["status"] = _compute_schedule_status(sch, now)
		sch["candidate_count"] = frappe.db.count(
			"Exam Submission", {"exam_schedule": sch["name"]}
		)

	return schedules


@frappe.whitelist()
def get_ongoing_schedules():
	if "Exam Manager" not in frappe.get_roles():
		frappe.throw("You are not authorized to perform this action", frappe.PermissionError)

	now = now_datetime()
	schedules = frappe.db.sql(
		"""
		SELECT es.name, es.exam, es.start_date_time, es.duration,
		       es.schedule_type, es.schedule_expire_in_days,
		       e.title as exam_title
		FROM `tabExam Schedule` es
		JOIN `tabExam` e ON e.name = es.exam
		ORDER BY es.start_date_time
		""",
		as_dict=True,
	)

	ongoing = []
	for sch in schedules:
		status = _compute_schedule_status(sch, now)
		if status == "Ongoing":
			sch["candidate_count"] = frappe.db.count(
				"Exam Submission", {"exam_schedule": sch["name"]}
			)
			ongoing.append(sch)

	return ongoing


def _compute_schedule_status(sch, now):
	from datetime import timedelta
	start = sch.get("start_date_time")
	if not start:
		return "Upcoming"
	if isinstance(start, str):
		start = frappe.utils.get_datetime(start)

	duration_mins = sch.get("duration") or 0
	expire_days = sch.get("schedule_expire_in_days") or 0
	schedule_type = sch.get("schedule_type") or "Fixed"

	end = start + timedelta(minutes=duration_mins)
	if schedule_type == "Flexible":
		end = start + timedelta(days=expire_days, minutes=duration_mins)

	if now < start:
		return "Upcoming"
	elif now <= end:
		return "Ongoing"
	else:
		return "Completed"


@frappe.whitelist()
def get_schedule_candidates(schedule):
	if "Exam Manager" not in frappe.get_roles():
		frappe.throw("You are not authorized to perform this action", frappe.PermissionError)

	candidates = frappe.get_all(
		"Exam Submission",
		filters={"exam_schedule": schedule},
		fields=["name", "candidate", "candidate_name", "status",
				"total_marks", "result_status", "issued_certificate"],
		order_by="creation desc",
	)

	exam_total = 0
	sch_doc = frappe.db.get_value("Exam Schedule", schedule, "exam")
	if sch_doc:
		exam_total = frappe.db.get_value("Exam", sch_doc, "total_marks") or 0

	for c in candidates:
		c["exam_total_marks"] = exam_total

	return candidates


@frappe.whitelist()
def search_users(query):
	if "Exam Manager" not in frappe.get_roles():
		frappe.throw("You are not authorized to perform this action", frappe.PermissionError)

	query = (query or "").strip()
	if not query or len(query) < 2:
		return []

	like = f"%{query}%"
	return frappe.db.sql(
		"""
		SELECT DISTINCT u.name, u.full_name
		FROM `tabUser` u
		INNER JOIN `tabHas Role` r ON r.parent = u.name AND r.role = 'Exam Candidate'
		WHERE u.enabled = 1
		  AND u.name NOT IN ('Guest', 'Administrator')
		  AND (u.name LIKE %(like)s OR u.full_name LIKE %(like)s)
		ORDER BY u.full_name
		LIMIT 20
		""",
		{"like": like},
		as_dict=True,
	)


@frappe.whitelist()
def save_exam(data):
	if "Exam Manager" not in frappe.get_roles():
		frappe.throw("You are not authorized to perform this action", frappe.PermissionError)

	if isinstance(data, str):
		data = json.loads(data)

	name = data.get("name")
	if name:
		doc = frappe.get_doc("Exam", name)
	else:
		doc = frappe.new_doc("Exam")

	for field in ("title", "exam_mode", "duration", "pass_percentage",
				  "question_type", "description", "instructions"):
		if field in data:
			doc.set(field, data[field])

	if "randomize_questions" in data:
		doc.randomize_questions = 1 if data["randomize_questions"] else 0

	if "select_questions" in data:
		doc.select_questions = []
		for sq in data["select_questions"]:
			if sq.get("question_category"):
				doc.append("select_questions", {
					"question_category": sq["question_category"],
					"no_of_questions": sq.get("no_of_questions", 1),
					"mark_per_question": sq.get("mark_per_question", 1),
				})

	doc.save()
	return {
		"name": doc.name,
		"title": doc.title,
		"exam_mode": doc.exam_mode,
		"duration": doc.duration,
		"question_type": doc.question_type,
		"total_questions": doc.total_questions or 0,
		"total_marks": doc.total_marks or 0,
	}


@frappe.whitelist()
def duplicate_exam(name):
	if "Exam Manager" not in frappe.get_roles():
		frappe.throw("You are not authorized to perform this action", frappe.PermissionError)

	source = frappe.get_doc("Exam", name)
	new_doc = frappe.copy_doc(source)
	new_doc.title = f"{source.title} (Copy)"
	new_doc.short_uuid = ""
	new_doc.insert()

	return {
		"name": new_doc.name,
		"title": new_doc.title,
		"exam_mode": new_doc.exam_mode,
		"duration": new_doc.duration,
		"question_type": new_doc.question_type,
		"total_questions": new_doc.total_questions or 0,
		"total_marks": new_doc.total_marks or 0,
	}


@frappe.whitelist()
def save_schedule(data):
	if "Exam Manager" not in frappe.get_roles():
		frappe.throw("You are not authorized to perform this action", frappe.PermissionError)

	if isinstance(data, str):
		data = json.loads(data)

	name = data.get("name")
	if name:
		doc = frappe.get_doc("Exam Schedule", name)
	else:
		schedule_name = data.get("schedule_name")
		if not schedule_name:
			frappe.throw("Please set the schedule name")
		doc = frappe.new_doc("Exam Schedule")
		doc.__newname = schedule_name
		doc.exam = data.get("exam")

	update_fields = ["schedule_type", "schedule_expire_in_days", "badge"]
	if doc.is_new():
		update_fields.insert(0, "start_date_time")

	for field in update_fields:
		if field in data:
			doc.set(field, data[field])

	doc.save()

	now = now_datetime()
	sch_dict = {
		"name": doc.name,
		"start_date_time": doc.start_date_time,
		"schedule_type": doc.schedule_type,
		"duration": doc.duration,
		"schedule_expire_in_days": doc.schedule_expire_in_days or 0,
		"badge": doc.badge or "",
	}
	sch_dict["status"] = _compute_schedule_status(sch_dict, now)
	sch_dict["candidate_count"] = frappe.db.count(
		"Exam Submission", {"exam_schedule": doc.name}
	)
	return sch_dict


@frappe.whitelist()
def get_batches():
	if "Exam Manager" not in frappe.get_roles():
		frappe.throw("You are not authorized to perform this action", frappe.PermissionError)

	return frappe.get_all("Exam Batch", fields=["name"], order_by="name")


@frappe.whitelist()
def add_candidates_to_schedule(schedule_name, emails=None, batch_name=None):
	if "Exam Manager" not in frappe.get_roles():
		frappe.throw("You are not authorized to perform this action", frappe.PermissionError)

	schedule = frappe.get_doc("Exam Schedule", schedule_name)
	added = 0
	duplicates = 0
	invalid_users = []

	if emails:
		if isinstance(emails, str):
			email_list = [e.strip() for e in re.split(r"[,;\n]+", emails) if e.strip()]
		else:
			email_list = [e.strip() for e in emails if isinstance(e, str) and e.strip()]
		for email in email_list:
			if not frappe.db.exists("User", email):
				invalid_users.append(email)
				continue

			existing = frappe.db.exists("Exam Submission", {
				"exam_schedule": schedule_name,
				"candidate": email,
				"status": ["not in", ["Terminated", "Registration Cancelled"]],
			})
			if existing:
				duplicates += 1
				continue

			doc = frappe.get_doc({
				"doctype": "Exam Submission",
				"exam": schedule.exam,
				"exam_schedule": schedule_name,
				"candidate": email,
				"status": "Registered",
			})
			doc.insert(ignore_permissions=True)
			added += 1

	if batch_name:
		batch_users = frappe.get_all(
			"Exam Batch User",
			filters={"exam_batch": batch_name},
			fields=["candidate"],
		)
		for bu in batch_users:
			existing = frappe.db.exists("Exam Submission", {
				"exam_schedule": schedule_name,
				"candidate": bu.candidate,
				"status": ["not in", ["Terminated", "Registration Cancelled"]],
			})
			if existing:
				duplicates += 1
				continue

			doc = frappe.get_doc({
				"doctype": "Exam Submission",
				"exam": schedule.exam,
				"exam_schedule": schedule_name,
				"candidate": bu.candidate,
				"status": "Registered",
			})
			doc.insert(ignore_permissions=True)
			added += 1

	frappe.db.commit()
	return {"added": added, "duplicates": duplicates, "invalid_users": invalid_users}


def build_user_prompt(prompt, file_content, count, difficulty, question_type, category):
	parts = []

	if prompt:
		parts.append(f"Topic/Instructions: {prompt}")

	if file_content:
		truncated = file_content[:50000]
		parts.append(
			f"The following file content contains questions, data, or reference material. "
			f"Use it to generate exam questions. The content may be structured (CSV) or unstructured (plain text), "
			f"and may or may not include answers.\n\n--- FILE CONTENT ---\n{truncated}\n--- END FILE CONTENT ---"
		)

	parts.append(
		f'Generate {count} {difficulty} difficulty {question_type} questions for category "{category}".'
	)

	return "\n\n".join(parts)


def build_system_prompt(count, difficulty, question_type, category):
	base = f"""You are an expert exam question generator. Generate exactly {count} {difficulty} difficulty questions of type "{question_type}" for the category "{category}".

Return ONLY a valid JSON array with no other text, no markdown fences, no explanation. Each object in the array must have:
- "question": The full question text (plain text, no HTML)"""

	if question_type == "Choices":
		base += """
- "options": An array of exactly 4 objects, each with:
  - "text": The option text
  - "is_correct": boolean (true/false)
  - "explanation": Brief explanation of why this option is correct or incorrect

Rules for Choices questions:
- Exactly one option must be marked is_correct: true unless the question genuinely has multiple correct answers
- All 4 options must be plausible
- Explanations should be educational and concise"""
	else:
		base += """
- "possible_answers": An array of 1-4 acceptable answer strings
- "explanation": Explanation of the correct answer"""

	base += f"""

General rules:
- Questions must be at {difficulty} difficulty level
- Each question must be unique and test different aspects of the topic
- Do not number the questions in the question text
- Return valid JSON only"""

	return base


def parse_questions_json(content):
	content = content.strip()
	fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", content, re.DOTALL)
	if fence_match:
		content = fence_match.group(1).strip()

	try:
		parsed = json.loads(content)
		if isinstance(parsed, list):
			return parsed
		if isinstance(parsed, dict) and "questions" in parsed:
			return parsed["questions"]
	except json.JSONDecodeError:
		pass

	array_match = re.search(r"\[.*\]", content, re.DOTALL)
	if array_match:
		try:
			return json.loads(array_match.group(0))
		except json.JSONDecodeError:
			pass

	return None


@frappe.whitelist()
def get_batches_with_counts():
	if "Exam Manager" not in frappe.get_roles():
		frappe.throw("You are not authorized to perform this action", frappe.PermissionError)

	batches = frappe.get_all(
		"Exam Batch",
		fields=["name", "batch_name", "description"],
		order_by="batch_name",
	)
	for b in batches:
		b["user_count"] = frappe.db.count("Exam Batch User", {"exam_batch": b.name})
	return batches


@frappe.whitelist()
def get_batch_users(batch_name):
	if "Exam Manager" not in frappe.get_roles():
		frappe.throw("You are not authorized to perform this action", frappe.PermissionError)

	if not frappe.db.exists("Exam Batch", batch_name):
		frappe.throw("Batch not found", frappe.DoesNotExistError)

	return frappe.db.sql(
		"""
		SELECT bu.name as batch_user_name, bu.candidate,
		       u.full_name, u.enabled
		FROM `tabExam Batch User` bu
		LEFT JOIN `tabUser` u ON u.name = bu.candidate
		WHERE bu.exam_batch = %(batch)s
		ORDER BY u.full_name
		""",
		{"batch": batch_name},
		as_dict=True,
	)


@frappe.whitelist()
def create_batch(batch_name, description=""):
	if "Exam Manager" not in frappe.get_roles():
		frappe.throw("You are not authorized to perform this action", frappe.PermissionError)

	doc = frappe.get_doc({
		"doctype": "Exam Batch",
		"batch_name": batch_name,
		"description": description,
	})
	doc.insert()
	return {
		"name": doc.name,
		"batch_name": doc.batch_name,
		"description": doc.description,
		"user_count": 0,
	}


@frappe.whitelist()
def add_users_to_batch(batch_name, emails):
	if "Exam Manager" not in frappe.get_roles():
		frappe.throw("You are not authorized to perform this action", frappe.PermissionError)

	if not frappe.db.exists("Exam Batch", batch_name):
		frappe.throw("Batch not found", frappe.DoesNotExistError)

	email_list = [e.strip() for e in re.split(r"[,;\n]+", emails) if e.strip()]
	added = 0
	skipped = 0
	not_found = []

	for email in email_list:
		if not frappe.db.exists("User", email):
			not_found.append(email)
			continue

		if frappe.db.exists("Exam Batch User", {"exam_batch": batch_name, "candidate": email}):
			skipped += 1
			continue

		doc = frappe.get_doc({
			"doctype": "Exam Batch User",
			"exam_batch": batch_name,
			"candidate": email,
		})
		doc.insert(ignore_permissions=True)
		added += 1

	frappe.db.commit()
	return {"added": added, "skipped": skipped, "not_found": not_found}


@frappe.whitelist()
def create_users_and_add_to_batch(batch_name, users_data):
	if "Exam Manager" not in frappe.get_roles():
		frappe.throw("You are not authorized to perform this action", frappe.PermissionError)

	if not frappe.db.exists("Exam Batch", batch_name):
		frappe.throw("Batch not found", frappe.DoesNotExistError)

	if isinstance(users_data, str):
		users_data = json.loads(users_data)

	email_pattern = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
	created = 0
	existing_added = 0
	skipped = 0
	errors = []

	for entry in users_data:
		email = (entry.get("email") or "").strip().lower()
		first_name = (entry.get("first_name") or "").strip()
		last_name = (entry.get("last_name") or "").strip()

		if not email or not email_pattern.match(email):
			errors.append({"email": email, "error": "Invalid email format"})
			continue

		if not first_name:
			errors.append({"email": email, "error": "First name is required"})
			continue

		if frappe.db.exists("User", email):
			skipped += 1
			continue

		try:
			user_doc = frappe.get_doc({
				"doctype": "User",
				"email": email,
				"first_name": first_name,
				"last_name": last_name,
				"user_type": "Website User",
				"send_welcome_email": 1,
				"roles": [{"role": "Exam Candidate"}],
			})
			user_doc.insert(ignore_permissions=True)
			created += 1
		except Exception as e:
			errors.append({"email": email, "error": str(e)})
			continue

		if frappe.db.exists("Exam Batch User", {"exam_batch": batch_name, "candidate": email}):
			continue

		batch_user = frappe.get_doc({
			"doctype": "Exam Batch User",
			"exam_batch": batch_name,
			"candidate": email,
		})
		batch_user.insert(ignore_permissions=True)

	frappe.db.commit()
	return {
		"created": created,
		"skipped": skipped,
		"errors": errors,
	}


@frappe.whitelist()
def remove_user_from_batch(batch_name, email):
	if "Exam Manager" not in frappe.get_roles():
		frappe.throw("You are not authorized to perform this action", frappe.PermissionError)

	batch_user = frappe.db.get_value(
		"Exam Batch User",
		{"exam_batch": batch_name, "candidate": email},
		"name",
	)
	if not batch_user:
		frappe.throw("User not found in batch", frappe.DoesNotExistError)

	frappe.delete_doc("Exam Batch User", batch_user, ignore_permissions=True)
	frappe.db.commit()
	return {"success": True}
