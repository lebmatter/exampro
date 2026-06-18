import re
import frappe
from frappe.model.document import Document

RE_SLUG_NOTALLOWED = re.compile("[^a-z0-9]+")


def generate_short_uuid():
	import uuid
	return str(uuid.uuid4()).replace("-", "")[:8]


def generate_slug(title, doctype):
	result = frappe.get_all(doctype, fields=["name"])
	slugs = {row["name"] for row in result}
	slug = RE_SLUG_NOTALLOWED.sub("-", title.lower()).strip("-")
	if slug not in slugs:
		return slug
	count = 2
	while True:
		new_slug = f"{slug}-{count}"
		if new_slug not in slugs:
			return new_slug
		count += 1


class QuickQuiz(Document):

	def before_insert(self):
		if not self.short_uuid:
			self.short_uuid = generate_short_uuid()

	def autoname(self):
		if not self.name:
			self.name = generate_slug(self.title or "quick-quiz", "Quick Quiz")

	def validate(self):
		self.total_questions = len(self.questions or [])

		if self.access_type == "PIN" and self.pin_code:
			if not self.pin_code.isdigit() or len(self.pin_code) < 4:
				frappe.throw("PIN must be at least 4 digits")

		if self.status == "Published" and not self.questions:
			frappe.throw("Cannot publish a quiz with no questions")

		for i, q in enumerate(self.questions or [], 1):
			correct_count = sum([
				q.is_correct_1 or 0,
				q.is_correct_2 or 0,
				q.is_correct_3 or 0,
				q.is_correct_4 or 0,
			])
			if correct_count != 1:
				frappe.throw(f"Question {i} must have exactly one correct answer")
