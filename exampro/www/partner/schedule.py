import frappe
from frappe import _
from frappe.utils import format_datetime

from exampro.exam_pro.api.utils import assert_partner_access, get_current_user_partner
from exampro.exam_pro.doctype.exam_schedule.exam_schedule import (
    get_schedule_status,
    bulk_add_submissions,
    send_certificates,
)


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    partner_name = assert_partner_access()

    schedule_name = frappe.form_dict.get("schedule_name")
    if not schedule_name:
        frappe.throw(_("Schedule not specified."), frappe.PageDoesNotExistError)

    schedule = frappe.get_doc("Exam Schedule", schedule_name, ignore_permissions=True)
    exam = frappe.get_doc("Exam", schedule.exam, ignore_permissions=True)

    # Ensure this schedule belongs to the partner
    if exam.partner != partner_name:
        frappe.throw(_("You do not have permission to access this schedule."), frappe.PermissionError)

    context.schedule = schedule
    context.exam = exam
    context.schedule_status = get_schedule_status(schedule_name)
    context.start_display = format_datetime(schedule.start_date_time, "dd MMM yyyy, HH:mm") if schedule.start_date_time else "—"

    # Fetch candidates
    submissions = frappe.get_all(
        "Exam Submission",
        filters={"exam_schedule": schedule_name},
        fields=["name", "candidate", "candidate_name", "status", "result_status", "total_marks", "issued_certificate"],
        order_by="candidate_name",
        ignore_permissions=True,
    )
    context.submissions = submissions
    context.total_candidates = len(submissions)
    context.passed_count = sum(1 for s in submissions if s.get("result_status") == "Passed")
    context.failed_count = sum(1 for s in submissions if s.get("result_status") == "Failed")

    context.can_manage = True

    context.title = f"{exam.title} — {context.schedule_status}"
    context.no_cache = 1


@frappe.whitelist()
def partner_bulk_add_candidates(schedule_name, email_list):
    """Add candidates to a schedule."""
    partner_name = assert_partner_access()

    schedule = frappe.get_doc("Exam Schedule", schedule_name, ignore_permissions=True)
    exam = frappe.get_doc("Exam", schedule.exam, ignore_permissions=True)
    if exam.partner != partner_name:
        frappe.throw(_("You do not have permission to manage this schedule."), frappe.PermissionError)

    return bulk_add_submissions(schedule_name, email_list)


@frappe.whitelist()
def partner_send_certificates(schedule_name):
    """Send certificates for a completed schedule."""
    partner_name = assert_partner_access()

    schedule = frappe.get_doc("Exam Schedule", schedule_name, ignore_permissions=True)
    exam = frappe.get_doc("Exam", schedule.exam, ignore_permissions=True)
    if exam.partner != partner_name:
        frappe.throw(_("You do not have permission to manage this schedule."), frappe.PermissionError)

    return send_certificates(schedule_name)
