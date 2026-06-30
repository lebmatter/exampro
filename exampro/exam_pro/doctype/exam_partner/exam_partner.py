# Copyright (c) 2026, Labeeb Mattra and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ExamPartner(Document):

    def on_update(self):
        for row in self.users:
            _ensure_partner_role(row.user)


def _ensure_partner_role(user):
    user_doc = frappe.get_doc("User", user)
    if not any(r.role == "Exam Partner" for r in user_doc.roles):
        user_doc.append("roles", {"role": "Exam Partner"})
        user_doc.save(ignore_permissions=True)
