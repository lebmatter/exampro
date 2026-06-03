# Copyright (c) 2026, Labeeb Mattra and contributors
# For license information, please see license.txt
"""Import / Export an Exam (with its question bank) as JSON.

JSON format (format_version 1.0):
{
  "format_version": "1.0",
  "exported_at": "<iso datetime>",
  "exam": { <allowlisted exam fields>, "image_data": "data:image/...;base64,..." },
  "categories": [ {"name": "...", "title": "..."} ],
  "select_questions": [ {"question_category": "...", "no_of_questions": N, "mark_per_question": M} ],
  "questions": [
    {
      "question": "...", "category": "...", "mark": N, "type": "Choices|User Input",
      "description_image_data": "data:image/...;base64,...",
      "option_1": "...", "option_1_image_data": "data:...", "is_correct_1": 0|1, "explanation_1": "...",
      ... (options 2-4 similarly) ...
      "possibility_1": "...", ... "possibility_4": "...",
      "multiple": 0|1,
      "help_show": "Do not show|Before question|After wrong answer|After any answer",
      "help_minimum_reading_time": 15,
      "help_text": "...",
      "help_quiz": [ {"quiz_question": "...", "choice_1": "...", "choice_2": "...", "choice_3": "...", "correct_choice": "1|2|3"} ]
    }
  ]
}
"""

import base64
import binascii
import json
from datetime import datetime

import frappe
from frappe import _
from frappe.utils.html_utils import sanitize_html


FORMAT_VERSION = "1.0"

EXAM_FIELDS = [
	"title", "description", "instructions",
	"duration", "pass_percentage",
	"start_time_type", "flexible_time_ends_in",
	"enable_video_proctoring", "enable_calculator", "enable_chat",
	"max_warning_count", "show_result", "show_result_after_date",
	"leaderboard", "leaderboard_rows",
	"question_type", "randomize_questions",
	"evaluation_required", "evaluation_ends_in_days",
	"enable_certification", "expiry", "certificate_template",
]

QUESTION_SCALAR_FIELDS = [
	"question", "category", "mark", "type",
	"option_1", "option_2", "option_3", "option_4",
	"is_correct_1", "is_correct_2", "is_correct_3", "is_correct_4",
	"explanation_1", "explanation_2", "explanation_3", "explanation_4",
	"possibility_1", "possibility_2", "possibility_3", "possibility_4",
	"multiple",
	"help_show", "help_minimum_reading_time", "help_text",
]

QUESTION_IMAGE_FIELDS = [
	"description_image", "option_1_image", "option_2_image", "option_3_image", "option_4_image",
]

HTML_FIELDS_EXAM = {"description", "instructions"}
HTML_FIELDS_QUESTION = {"question", "help_text"}

ALLOWED_IMAGE_MIME = {"image/png", "image/jpeg", "image/gif", "image/webp"}
IMAGE_MAGIC = [
	(b"\x89PNG\r\n\x1a\n", "image/png"),
	(b"\xff\xd8\xff", "image/jpeg"),
	(b"GIF87a", "image/gif"),
	(b"GIF89a", "image/gif"),
]
MAX_IMAGE_BYTES = 2 * 1024 * 1024          # 2 MB / image
MAX_JSON_BYTES = 50 * 1024 * 1024          # 50 MB total payload
MAX_QUESTIONS = 5000
MAX_CATEGORIES = 1000


# ---------- helpers ---------------------------------------------------------

def _file_to_data_url(file_url):
	"""Return a data URL for a stored Frappe file, or None on failure."""
	if not file_url:
		return None
	try:
		f = frappe.get_doc("File", {"file_url": file_url})
		content = f.get_content()
		if not isinstance(content, (bytes, bytearray)):
			return None
		mime = _detect_mime(bytes(content[:16]))
		if not mime:
			return None
		return f"data:{mime};base64," + base64.b64encode(content).decode("ascii")
	except Exception:
		return None


def _detect_mime(head_bytes):
	for magic, mime in IMAGE_MAGIC:
		if head_bytes.startswith(magic):
			return mime
	if head_bytes[:4] == b"RIFF" and head_bytes[8:12] == b"WEBP":
		return "image/webp"
	return None


def _decode_data_url(data_url, owner_doctype, owner_name, fieldname):
	"""Validate a base64 data URL and save it as a File doc; return file_url or None."""
	if not data_url or not isinstance(data_url, str):
		return None
	if not data_url.startswith("data:"):
		return None
	try:
		header, b64 = data_url.split(",", 1)
	except ValueError:
		return None
	# header form:  data:<mime>;base64
	if ";base64" not in header:
		return None
	declared_mime = header[5:].split(";", 1)[0].strip().lower()
	if declared_mime not in ALLOWED_IMAGE_MIME:
		frappe.throw(_("Disallowed image type: {0}").format(declared_mime))

	# strip whitespace to defend against pretty-printed JSON
	b64 = "".join(b64.split())
	if len(b64) > (MAX_IMAGE_BYTES * 4 // 3) + 16:
		frappe.throw(_("Image exceeds size limit ({0} MB)").format(MAX_IMAGE_BYTES // (1024 * 1024)))
	try:
		raw = base64.b64decode(b64, validate=True)
	except (binascii.Error, ValueError):
		frappe.throw(_("Invalid base64 image data"))
	if len(raw) > MAX_IMAGE_BYTES:
		frappe.throw(_("Image exceeds size limit ({0} MB)").format(MAX_IMAGE_BYTES // (1024 * 1024)))

	actual_mime = _detect_mime(raw[:16])
	if not actual_mime or actual_mime != declared_mime:
		frappe.throw(_("Image content does not match declared type"))

	ext = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif", "image/webp": "webp"}[actual_mime]
	fname = f"{owner_doctype.lower().replace(' ', '_')}_{owner_name}_{fieldname}.{ext}"

	file_doc = frappe.get_doc({
		"doctype": "File",
		"file_name": fname,
		"attached_to_doctype": owner_doctype,
		"attached_to_name": owner_name,
		"attached_to_field": fieldname,
		"is_private": 0,
		"content": raw,
		"decode": False,
	}).insert(ignore_permissions=False)
	return file_doc.file_url


def _clean_html(value):
	if not value:
		return value
	# sanitize_html strips scripts, event handlers, javascript: URLs, dangerous attrs.
	return sanitize_html(str(value), always_sanitize=True)


def _require_permission(doctype, ptype):
	if not frappe.has_permission(doctype, ptype):
		frappe.throw(_("Not permitted: {0} {1}").format(ptype, doctype), frappe.PermissionError)


# ---------- export ----------------------------------------------------------

@frappe.whitelist()
def export_exam(exam):
	_require_permission("Exam", "read")
	_require_permission("Exam Question", "read")
	exam_doc = frappe.get_doc("Exam", exam)

	payload = {
		"format_version": FORMAT_VERSION,
		"exported_at": frappe.utils.now(),
		"exam": {f: exam_doc.get(f) for f in EXAM_FIELDS},
		"categories": [],
		"select_questions": [],
		"questions": [],
	}
	if exam_doc.image:
		data_url = _file_to_data_url(exam_doc.image)
		if data_url:
			payload["exam"]["image_data"] = data_url

	# select_questions table
	cat_names = set()
	for row in exam_doc.select_questions or []:
		payload["select_questions"].append({
			"question_category": row.question_category,
			"no_of_questions": row.no_of_questions,
			"mark_per_question": row.mark_per_question,
		})
		cat_names.add(row.question_category)

	# include every question in any referenced category so the importer
	# has a real bank to randomly sample from
	question_names = set()
	if cat_names:
		qs = frappe.get_all(
			"Exam Question",
			filters={"category": ["in", list(cat_names)]},
			pluck="name",
		)
		question_names.update(qs)

	# Also include any specifically-added questions (covers exams configured before/without categories)
	for row in exam_doc.added_questions or []:
		if row.exam_question:
			question_names.add(row.exam_question)

	for qname in sorted(question_names):
		q = frappe.get_doc("Exam Question", qname)
		cat_names.add(q.category)
		q_out = {f: q.get(f) for f in QUESTION_SCALAR_FIELDS}
		for img_field in QUESTION_IMAGE_FIELDS:
			data_url = _file_to_data_url(q.get(img_field))
			if data_url:
				q_out[f"{img_field}_data"] = data_url
		q_out["help_quiz"] = [
			{
				"quiz_question": r.quiz_question,
				"choice_1": r.choice_1,
				"choice_2": r.choice_2,
				"choice_3": r.choice_3,
				"correct_choice": r.correct_choice,
			}
			for r in (q.help_quiz or [])
		]
		payload["questions"].append(q_out)

	# categories (resolve titles)
	for cname in sorted(cat_names):
		try:
			cdoc = frappe.get_doc("Exam Question Category", cname)
			payload["categories"].append({"name": cdoc.name, "title": cdoc.title})
		except frappe.DoesNotExistError:
			continue

	return payload


# ---------- import ----------------------------------------------------------

@frappe.whitelist()
def import_exam(json_text):
	"""Import an exam from JSON. Returns name of created Exam.

	The call is wrapped in a savepoint so any validation failure rolls the
	partial import back cleanly.
	"""
	_require_permission("Exam", "create")
	_require_permission("Exam Question", "create")
	_require_permission("Exam Question Category", "create")

	if not isinstance(json_text, str):
		frappe.throw(_("Invalid payload"))
	if len(json_text.encode("utf-8")) > MAX_JSON_BYTES:
		frappe.throw(_("Import file too large (max {0} MB)").format(MAX_JSON_BYTES // (1024 * 1024)))

	try:
		data = json.loads(json_text)
	except json.JSONDecodeError as e:
		frappe.throw(_("Invalid JSON: {0}").format(str(e)))

	if not isinstance(data, dict):
		frappe.throw(_("Top-level JSON must be an object"))

	if data.get("format_version") != FORMAT_VERSION:
		frappe.throw(_("Unsupported format_version: {0}").format(data.get("format_version")))

	exam_in = data.get("exam") or {}
	if not isinstance(exam_in, dict):
		frappe.throw(_("Missing 'exam' object"))

	categories = data.get("categories") or []
	questions = data.get("questions") or []
	select_questions = data.get("select_questions") or []

	if not isinstance(categories, list) or len(categories) > MAX_CATEGORIES:
		frappe.throw(_("Invalid or oversize 'categories' list"))
	if not isinstance(questions, list) or len(questions) > MAX_QUESTIONS:
		frappe.throw(_("Invalid or oversize 'questions' list (max {0})").format(MAX_QUESTIONS))
	if not isinstance(select_questions, list):
		frappe.throw(_("Invalid 'select_questions' list"))

	frappe.db.savepoint("exam_import")
	try:
		# 1. Categories — create only those that don't exist
		for cat in categories:
			if not isinstance(cat, dict):
				frappe.throw(_("Invalid category entry"))
			name = (cat.get("name") or "").strip()
			title = (cat.get("title") or name or "").strip()
			if not name:
				continue
			if not frappe.db.exists("Exam Question Category", name):
				frappe.get_doc({
					"doctype": "Exam Question Category",
					"title": title or name,
				}).insert(ignore_permissions=False)

		# 2. Questions
		for q in questions:
			if not isinstance(q, dict):
				frappe.throw(_("Invalid question entry"))
			_create_question(q)

		# 3. Exam itself
		exam_doc = frappe.new_doc("Exam")
		title = (exam_in.get("title") or "").strip()
		if not title:
			frappe.throw(_("Exam title is required"))
		exam_doc.title = title + " (Imported)"
		for f in EXAM_FIELDS:
			if f == "title":
				continue
			if f in exam_in and exam_in[f] is not None:
				val = exam_in[f]
				if f in HTML_FIELDS_EXAM:
					val = _clean_html(val)
				exam_doc.set(f, val)
		# default required fields
		if not exam_doc.duration:
			frappe.throw(_("Exam duration is required"))
		if not exam_doc.description:
			frappe.throw(_("Exam description is required"))

		for sq in select_questions:
			if not isinstance(sq, dict):
				continue
			exam_doc.append("select_questions", {
				"question_category": sq.get("question_category"),
				"no_of_questions": int(sq.get("no_of_questions") or 0),
				"mark_per_question": int(sq.get("mark_per_question") or 0),
			})

		exam_doc.insert(ignore_permissions=False)

		if exam_in.get("image_data"):
			file_url = _decode_data_url(exam_in["image_data"], "Exam", exam_doc.name, "image")
			if file_url:
				exam_doc.db_set("image", file_url, update_modified=False)

		frappe.db.commit()
		return {"name": exam_doc.name, "title": exam_doc.title}
	except Exception:
		frappe.db.rollback(save_point="exam_import")
		raise


def _create_question(q):
	q_type = q.get("type")
	if q_type not in ("Choices", "User Input"):
		frappe.throw(_("Invalid question type: {0}").format(q_type))

	category = (q.get("category") or "").strip()
	if not category:
		frappe.throw(_("Question is missing 'category'"))
	if not frappe.db.exists("Exam Question Category", category):
		# auto-create using the same id as title
		frappe.get_doc({"doctype": "Exam Question Category", "title": category}).insert(
			ignore_permissions=False
		)

	doc = frappe.new_doc("Exam Question")
	for f in QUESTION_SCALAR_FIELDS:
		if f not in q or q[f] is None:
			continue
		val = q[f]
		if f in HTML_FIELDS_QUESTION:
			val = _clean_html(val)
		doc.set(f, val)

	# help_quiz
	for r in q.get("help_quiz") or []:
		if not isinstance(r, dict):
			continue
		doc.append("help_quiz", {
			"quiz_question": r.get("quiz_question"),
			"choice_1": r.get("choice_1"),
			"choice_2": r.get("choice_2"),
			"choice_3": r.get("choice_3"),
			"correct_choice": r.get("correct_choice"),
		})

	doc.insert(ignore_permissions=False)

	# images: insert as File docs attached to the question
	dirty = False
	for img_field in QUESTION_IMAGE_FIELDS:
		data_url = q.get(f"{img_field}_data")
		if not data_url:
			continue
		file_url = _decode_data_url(data_url, "Exam Question", doc.name, img_field)
		if file_url:
			doc.set(img_field, file_url)
			dirty = True
	if dirty:
		doc.save(ignore_permissions=False)
