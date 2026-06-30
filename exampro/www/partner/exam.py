import frappe
from frappe import _

from exampro.exam_pro.api.utils import assert_partner_access


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    partner_name = assert_partner_access()

    exam_name = frappe.form_dict.get("exam_name")
    if not exam_name:
        frappe.throw(_("Exam not specified."), frappe.PageDoesNotExistError)

    exam = frappe.get_doc("Exam", exam_name, ignore_permissions=True)

    # Ensure this exam belongs to the partner
    if exam.partner != partner_name:
        frappe.throw(_("You do not have permission to access this exam."), frappe.PermissionError)

    # Question management must be enabled for partners to access this page
    if not exam.partner_manages_questions:
        frappe.throw(_("Question management for this exam is handled by the exam administrator."), frappe.PermissionError)

    # Fetch question categories
    categories = frappe.get_all(
        "Exam Question Category",
        fields=["name", "title"],
        ignore_permissions=True,
        order_by="title",
    )

    # Fetch questions linked to this exam via Exam Added Question
    added_questions = []
    if exam.added_questions:
        q_names = [row.exam_question for row in exam.added_questions]
        if q_names:
            questions = frappe.get_all(
                "Exam Question",
                filters={"name": ["in", q_names]},
                fields=["name", "question", "question_category", "mark"],
                ignore_permissions=True,
            )
            added_questions = questions

    context.exam = exam
    context.categories = categories
    context.added_questions = added_questions
    context.total_questions = len(added_questions)
    context.title = f"Questions — {exam.title}"
    context.no_cache = 1


@frappe.whitelist()
def get_questions_by_category(exam_name, category):
    """Return questions in a category that are not already in the exam."""
    partner_name = assert_partner_access()
    exam = frappe.get_doc("Exam", exam_name, ignore_permissions=True)
    if exam.partner != partner_name or not exam.partner_manages_questions:
        frappe.throw(_("Permission denied."), frappe.PermissionError)

    existing = {row.exam_question for row in (exam.added_questions or [])}

    questions = frappe.get_all(
        "Exam Question",
        filters={"question_category": category},
        fields=["name", "question", "mark"],
        ignore_permissions=True,
    )
    return [q for q in questions if q["name"] not in existing]


@frappe.whitelist()
def add_question_to_exam(exam_name, question_name):
    """Add a question to the exam's added_questions table."""
    partner_name = assert_partner_access()
    exam = frappe.get_doc("Exam", exam_name, ignore_permissions=True)
    if exam.partner != partner_name or not exam.partner_manages_questions:
        frappe.throw(_("Permission denied."), frappe.PermissionError)

    existing = {row.exam_question for row in (exam.added_questions or [])}
    if question_name in existing:
        frappe.throw(_("Question already added to this exam."))

    exam.append("added_questions", {"exam_question": question_name})
    exam.save(ignore_permissions=True)
    return {"success": True, "total": len(exam.added_questions)}


@frappe.whitelist()
def remove_question_from_exam(exam_name, question_name):
    """Remove a question from the exam's added_questions table."""
    partner_name = assert_partner_access()
    exam = frappe.get_doc("Exam", exam_name, ignore_permissions=True)
    if exam.partner != partner_name or not exam.partner_manages_questions:
        frappe.throw(_("Permission denied."), frappe.PermissionError)

    exam.added_questions = [row for row in exam.added_questions if row.exam_question != question_name]
    exam.save(ignore_permissions=True)
    return {"success": True, "total": len(exam.added_questions)}
