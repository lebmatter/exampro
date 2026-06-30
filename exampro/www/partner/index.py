import frappe
from frappe import _
from frappe.utils import format_datetime

from exampro.exam_pro.api.utils import assert_partner_access
from exampro.exam_pro.doctype.exam_schedule.exam_schedule import get_schedule_status


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    partner_name = assert_partner_access()

    partner = frappe.get_doc("Exam Partner", partner_name, ignore_permissions=True)
    context.partner = partner

    # Fetch all exams belonging to this partner
    exams = frappe.get_all(
        "Exam",
        filters={"partner": partner_name},
        fields=["name", "title", "duration", "pass_percentage", "partner_manages_questions", "enable_certification"],
        ignore_permissions=True,
    )

    exam_map = {e.name: e for e in exams}
    exam_names = list(exam_map.keys())

    # Fetch all schedules for partner's exams
    schedules = []
    if exam_names:
        schedules = frappe.get_all(
            "Exam Schedule",
            filters={"exam": ["in", exam_names]},
            fields=["name", "exam", "start_date_time", "duration", "schedule_type"],
            order_by="start_date_time desc",
            ignore_permissions=True,
        )

    for s in schedules:
        s["exam_title"] = exam_map.get(s["exam"], {}).get("title", s["exam"])
        s["status"] = get_schedule_status(s["name"])
        s["start_display"] = format_datetime(s["start_date_time"], "dd MMM yyyy, HH:mm") if s["start_date_time"] else "—"

    context.exams = exams
    context.schedules = schedules

    # Stats
    all_submission_counts = {}
    if schedules:
        schedule_names = [s["name"] for s in schedules]
        submissions = frappe.get_all(
            "Exam Submission",
            filters={"exam_schedule": ["in", schedule_names]},
            fields=["exam_schedule", "result_status"],
            ignore_permissions=True,
        )
        for sub in submissions:
            sn = sub["exam_schedule"]
            if sn not in all_submission_counts:
                all_submission_counts[sn] = {"total": 0, "passed": 0}
            all_submission_counts[sn]["total"] += 1
            if sub["result_status"] == "Passed":
                all_submission_counts[sn]["passed"] += 1

    for s in schedules:
        counts = all_submission_counts.get(s["name"], {"total": 0, "passed": 0})
        s["total_candidates"] = counts["total"]
        s["passed_candidates"] = counts["passed"]

    total_candidates = sum(c["total"] for c in all_submission_counts.values())
    total_passed = sum(c["passed"] for c in all_submission_counts.values())

    context.stats = {
        "total_exams": len(exams),
        "total_schedules": len(schedules),
        "total_candidates": total_candidates,
        "total_passed": total_passed,
    }

    context.title = f"{partner.partner_name} — Partner Dashboard"
    context.no_cache = 1
