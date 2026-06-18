import frappe
from frappe.model.document import Document


def generate_short_uuid():
	import uuid
	return str(uuid.uuid4()).replace("-", "")[:8]


class QuickQuizSubmission(Document):

	def before_insert(self):
		if not self.short_uuid:
			self.short_uuid = generate_short_uuid()
