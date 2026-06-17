import base64
import json
import re

import frappe
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
			"help_show", "help_text",
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
			"help_text": q.help_text or "",
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
	doc.help_text = data.get("help_text", doc.help_text)

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
