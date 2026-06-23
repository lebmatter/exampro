import frappe
from frappe.utils import format_datetime, strip_html

from exampro.exam_pro.doctype.exam_schedule.exam_schedule import get_schedule_status

RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX_REQUESTS = 30


def _check_rate_limit():
    ip = frappe.local.request_ip
    cache_key = f"public_api_rate:{ip}"
    count = frappe.cache().get_value(cache_key) or 0
    if count >= RATE_LIMIT_MAX_REQUESTS:
        frappe.throw(
            "Rate limit exceeded. Try again later.",
            frappe.RateLimitExceededError,
        )
    frappe.cache().set_value(cache_key, count + 1, expires_in_sec=RATE_LIMIT_WINDOW)


def _short_desc(html, length=160):
    if not html:
        return ""
    text = strip_html(html).strip()
    if len(text) > length:
        text = text[: length - 1].rstrip() + "…"
    return text


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_exams():
    """Return public exams with their upcoming/ongoing schedules."""
    _check_rate_limit()

    exams = frappe.get_all(
        "Exam",
        filters={"is_public": 1},
        fields=[
            "name", "title", "short_uuid", "description", "image",
            "duration", "question_type", "total_questions", "total_marks",
            "pass_percentage", "exam_mode", "enable_payment", "price",
            "enable_certification",
        ],
        ignore_permissions=True,
    )

    for exam in exams:
        exam["description"] = _short_desc(exam.get("description"))

        schedules = frappe.get_all(
            "Exam Schedule",
            filters={"exam": exam["name"]},
            fields=[
                "name", "short_uuid", "start_date_time", "schedule_type",
                "duration", "schedule_expire_in_days", "badge",
            ],
            ignore_permissions=True,
        )

        active_schedules = []
        for sched in schedules:
            status = get_schedule_status(sched["name"])
            if status == "Completed":
                continue
            if sched["schedule_type"] == "Fixed" and status != "Upcoming":
                continue
            active_schedules.append({
                "name": sched["name"],
                "short_uuid": sched["short_uuid"],
                "start_date_time": format_datetime(
                    sched["start_date_time"], "dd MMM YYYY, HH:mm"
                ),
                "schedule_type": sched["schedule_type"],
                "duration": sched["duration"],
                "badge": sched["badge"] or "Exam",
                "status": status,
            })

        exam["schedules"] = active_schedules

    return [e for e in exams if e["schedules"]]


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_exam_schedules(exam):
    """Return upcoming/ongoing schedules for a specific public exam."""
    _check_rate_limit()

    if not exam or not isinstance(exam, str) or len(exam) > 140:
        frappe.throw("Invalid exam parameter.", frappe.ValidationError)

    is_public = frappe.db.get_value("Exam", exam, "is_public")
    if not is_public:
        frappe.throw("Exam not found.", frappe.DoesNotExistError)

    schedules = frappe.get_all(
        "Exam Schedule",
        filters={"exam": exam},
        fields=[
            "name", "short_uuid", "start_date_time", "schedule_type",
            "duration", "schedule_expire_in_days", "badge",
        ],
        ignore_permissions=True,
    )

    result = []
    for sched in schedules:
        status = get_schedule_status(sched["name"])
        if status == "Completed":
            continue
        if sched["schedule_type"] == "Fixed" and status != "Upcoming":
            continue
        result.append({
            "name": sched["name"],
            "short_uuid": sched["short_uuid"],
            "start_date_time": format_datetime(
                sched["start_date_time"], "dd MMM YYYY, HH:mm"
            ),
            "schedule_type": sched["schedule_type"],
            "duration": sched["duration"],
            "badge": sched["badge"] or "Exam",
            "status": status,
        })

    return result
