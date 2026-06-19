import json
import re

import frappe
import requests


CACHE_KEY_PREFIX = "quiz_studio_state:"
CACHE_TTL = 86400  # 24 hours


def _check_exam_manager():
	if "Exam Manager" not in frappe.get_roles():
		frappe.throw("You are not authorized to perform this action", frappe.PermissionError)


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
def get_quiz_list():
	_check_exam_manager()

	quizzes = frappe.get_all(
		"Quick Quiz",
		fields=[
			"name", "title", "quiz_mode", "status", "access_type",
			"total_questions", "short_uuid", "theme", "modified",
		],
		order_by="modified desc",
	)

	for quiz in quizzes:
		quiz["submission_count"] = frappe.db.count(
			"Quick Quiz Submission", {"quiz": quiz.name}
		)

	return {"quizzes": quizzes}


@frappe.whitelist()
def get_quiz_detail(name):
	_check_exam_manager()

	doc = frappe.get_doc("Quick Quiz", name)

	questions = []
	for q in doc.questions:
		questions.append({
			"name": q.name,
			"question": q.question,
			"question_image": q.question_image or "",
			"option_1": q.option_1,
			"option_2": q.option_2,
			"option_3": q.option_3 or "",
			"option_4": q.option_4 or "",
			"is_correct_1": q.is_correct_1,
			"is_correct_2": q.is_correct_2,
			"is_correct_3": q.is_correct_3,
			"is_correct_4": q.is_correct_4,
		})

	return {
		"name": doc.name,
		"title": doc.title,
		"short_uuid": doc.short_uuid,
		"quiz_mode": doc.quiz_mode,
		"status": doc.status,
		"access_type": doc.access_type,
		"pin_code": doc.pin_code or "",
		"image": doc.image or "",
		"timer_enabled": doc.timer_enabled,
		"timer_seconds": doc.timer_seconds,
		"theme": doc.theme,
		"randomize_questions": doc.randomize_questions,
		"show_correct_after_answer": doc.show_correct_after_answer,
		"marks_per_question": doc.marks_per_question or 1,
		"description": doc.description or "",
		"total_questions": doc.total_questions,
		"questions": questions,
	}


@frappe.whitelist()
def save_quiz(data):
	_check_exam_manager()

	if isinstance(data, str):
		data = json.loads(data)

	questions_data = data.pop("questions", [])

	if data.get("name") and frappe.db.exists("Quick Quiz", data["name"]):
		# Update existing quiz
		doc = frappe.get_doc("Quick Quiz", data["name"])

		for field in (
			"title", "quiz_mode", "status", "access_type", "pin_code",
			"image", "timer_enabled", "timer_seconds", "theme",
			"marks_per_question", "randomize_questions",
			"show_correct_after_answer", "description",
		):
			if field in data:
				doc.set(field, data[field])

		doc.questions = []
		for q in questions_data:
			doc.append("questions", {
				"question": q.get("question", ""),
				"question_image": q.get("question_image", ""),
				"option_1": q.get("option_1", ""),
				"option_2": q.get("option_2", ""),
				"option_3": q.get("option_3", ""),
				"option_4": q.get("option_4", ""),
				"is_correct_1": q.get("is_correct_1", 0),
				"is_correct_2": q.get("is_correct_2", 0),
				"is_correct_3": q.get("is_correct_3", 0),
				"is_correct_4": q.get("is_correct_4", 0),
			})

		doc.save()
	else:
		# Create new quiz
		doc_dict = {
			"doctype": "Quick Quiz",
			"title": data.get("title", ""),
			"quiz_mode": data.get("quiz_mode", "Simple"),
			"status": data.get("status", "Draft"),
			"access_type": data.get("access_type", "PIN"),
			"pin_code": data.get("pin_code", ""),
			"image": data.get("image", ""),
			"timer_enabled": data.get("timer_enabled", 0),
			"timer_seconds": data.get("timer_seconds", 30),
			"theme": data.get("theme", "Default"),
			"marks_per_question": data.get("marks_per_question", 1),
			"randomize_questions": data.get("randomize_questions", 0),
			"show_correct_after_answer": data.get("show_correct_after_answer", 1),
			"description": data.get("description", ""),
			"questions": [],
		}

		for q in questions_data:
			doc_dict["questions"].append({
				"question": q.get("question", ""),
				"question_image": q.get("question_image", ""),
				"option_1": q.get("option_1", ""),
				"option_2": q.get("option_2", ""),
				"option_3": q.get("option_3", ""),
				"option_4": q.get("option_4", ""),
				"is_correct_1": q.get("is_correct_1", 0),
				"is_correct_2": q.get("is_correct_2", 0),
				"is_correct_3": q.get("is_correct_3", 0),
				"is_correct_4": q.get("is_correct_4", 0),
			})

		doc = frappe.get_doc(doc_dict).insert()

	return {"name": doc.name, "short_uuid": doc.short_uuid}


@frappe.whitelist()
def delete_quiz(name):
	_check_exam_manager()

	doc = frappe.get_doc("Quick Quiz", name)
	doc.status = "Archived"
	doc.save()

	return {"ok": True}


@frappe.whitelist()
def duplicate_quiz(name):
	_check_exam_manager()

	source = frappe.get_doc("Quick Quiz", name)

	new_doc_dict = {
		"doctype": "Quick Quiz",
		"title": f"{source.title} (Copy)",
		"quiz_mode": source.quiz_mode,
		"status": "Draft",
		"access_type": source.access_type,
		"pin_code": source.pin_code or "",
		"image": source.image or "",
		"timer_enabled": source.timer_enabled,
		"timer_seconds": source.timer_seconds,
		"theme": source.theme,
		"marks_per_question": source.marks_per_question or 1,
		"randomize_questions": source.randomize_questions,
		"show_correct_after_answer": source.show_correct_after_answer,
		"description": source.description or "",
		"questions": [],
	}

	for q in source.questions:
		new_doc_dict["questions"].append({
			"question": q.question,
			"question_image": q.question_image or "",
			"option_1": q.option_1,
			"option_2": q.option_2,
			"option_3": q.option_3 or "",
			"option_4": q.option_4 or "",
			"is_correct_1": q.is_correct_1,
			"is_correct_2": q.is_correct_2,
			"is_correct_3": q.is_correct_3,
			"is_correct_4": q.is_correct_4,
		})

	new_doc = frappe.get_doc(new_doc_dict).insert()

	return {"name": new_doc.name}


@frappe.whitelist()
def generate_quiz_questions(topic, count, tone="fun"):
	_check_exam_manager()

	count = int(count)
	if count < 1 or count > 20:
		frappe.throw("Number of questions must be between 1 and 20")

	if tone not in ("fun", "serious"):
		frappe.throw("Invalid tone. Must be 'fun' or 'serious'.")

	settings = frappe.get_single("Exam Settings")
	api_key, model = settings.get_openrouter_config()

	system_prompt = (
		f"You are a quiz question generator. Generate exactly {count} multiple-choice "
		f"questions about {topic}. Tone: {tone} (fun = playful/engaging language, "
		f"serious = straightforward). Return ONLY a valid JSON array. Each object: "
		f'{{\"question\", \"option_1\", \"option_2\", \"option_3\", \"option_4\", '
		f'\"correct_option\" (1-4)}}. Rules: exactly 4 options per '
		f"question, one correct, all plausible. No markdown fences."
	)

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
					{"role": "user", "content": f"Generate {count} quiz questions about: {topic}"},
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

	questions = _parse_quiz_json(content)
	if not questions:
		frappe.throw("Could not parse AI response. Please try again with a different prompt.")

	# Transform to Quick Quiz Question format
	result = []
	for q in questions:
		correct = int(q.get("correct_option", 1))
		result.append({
			"question": q.get("question", ""),
			"option_1": q.get("option_1", ""),
			"option_2": q.get("option_2", ""),
			"option_3": q.get("option_3", ""),
			"option_4": q.get("option_4", ""),
			"is_correct_1": 1 if correct == 1 else 0,
			"is_correct_2": 1 if correct == 2 else 0,
			"is_correct_3": 1 if correct == 3 else 0,
			"is_correct_4": 1 if correct == 4 else 0,
		})

	return {"questions": result}


@frappe.whitelist()
def import_from_question_bank(category, count=10):
	_check_exam_manager()

	count = int(count)

	questions = frappe.get_all(
		"Exam Question",
		filters={"category": category, "type": "Choices"},
		fields=[
			"name", "question",
			"option_1", "option_2", "option_3", "option_4",
			"is_correct_1", "is_correct_2", "is_correct_3", "is_correct_4",
		],
		limit=count,
		order_by="RAND()",
	)

	result = []
	for q in questions:
		result.append({
			"question": q.question,
			"option_1": q.option_1 or "",
			"option_2": q.option_2 or "",
			"option_3": q.option_3 or "",
			"option_4": q.option_4 or "",
			"is_correct_1": q.is_correct_1,
			"is_correct_2": q.is_correct_2,
			"is_correct_3": q.is_correct_3,
			"is_correct_4": q.is_correct_4,
		})

	return {"questions": result}


@frappe.whitelist()
def get_quiz_submissions(quiz_name):
	_check_exam_manager()

	submissions = frappe.get_all(
		"Quick Quiz Submission",
		filters={"quiz": quiz_name},
		fields=[
			"name", "participant_name", "participant_email",
			"score", "total_points", "correct_count", "total_questions",
			"time_taken_seconds", "status", "started_at", "completed_at",
		],
		order_by="score desc, time_taken_seconds asc",
	)

	return {"submissions": submissions}


@frappe.whitelist()
def get_quiz_analytics(quiz_name):
	_check_exam_manager()

	total_respondents = frappe.db.count(
		"Quick Quiz Submission",
		{"quiz": quiz_name, "status": "Completed"},
	)

	if not total_respondents:
		return {"total_respondents": 0, "questions": []}

	counts = frappe.db.sql("""
		SELECT a.question_idx, a.selected_option, COUNT(*) as count
		FROM `tabQuick Quiz Answer` a
		INNER JOIN `tabQuick Quiz Submission` s ON s.name = a.parent
		WHERE s.quiz = %s AND s.status = 'Completed' AND a.selected_option > 0
		GROUP BY a.question_idx, a.selected_option
		ORDER BY a.question_idx, a.selected_option
	""", (quiz_name,), as_dict=True)

	count_map = {}
	for row in counts:
		count_map.setdefault(row.question_idx, {})[row.selected_option] = row.count

	quiz = frappe.get_doc("Quick Quiz", quiz_name)
	questions = []
	for idx, q in enumerate(quiz.questions or []):
		q_counts = count_map.get(idx, {})
		total_for_q = sum(q_counts.values())
		options = []
		for n in range(1, 5):
			text = getattr(q, f"option_{n}", "") or ""
			if not text:
				continue
			c = q_counts.get(n, 0)
			pct = round(c / total_for_q * 100, 1) if total_for_q else 0
			options.append({
				"num": n,
				"text": text,
				"count": c,
				"pct": pct,
				"is_correct": bool(getattr(q, f"is_correct_{n}", 0)),
			})
		questions.append({
			"idx": idx,
			"question": q.question,
			"options": options,
		})

	return {"total_respondents": total_respondents, "questions": questions}


@frappe.whitelist()
def get_question_categories():
	_check_exam_manager()

	categories = frappe.get_all(
		"Exam Question Category",
		fields=["name", "title"],
	)

	return {"categories": categories}


def _parse_quiz_json(content):
	content = content.strip()

	# Strip markdown fences
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

	# Fallback: extract JSON array with regex
	array_match = re.search(r"\[.*\]", content, re.DOTALL)
	if array_match:
		try:
			return json.loads(array_match.group(0))
		except json.JSONDecodeError:
			pass

	return None
