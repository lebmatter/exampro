from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.utils import format_datetime, strip_html

from exampro.exam_pro.api.utils import submit_candidate_pending_exams
from exampro.exam_pro.doctype.exam_schedule.exam_schedule import get_schedule_status
from exampro.www.evaluate import get_evaluator_live_exams
from exampro.www.proctor import get_proctor_live_exams, get_proctor_upcoming_events


def _short_desc(html, length=160):
    if not html:
        return ""
    text = strip_html(html).strip()
    if len(text) > length:
        text = text[: length - 1].rstrip() + "…"
    return text


def _candidate_items():
    """Return (live, upcoming, has_live_fixed) candidate dashboard cards."""
    live, upcoming = [], []
    has_live_fixed = False
    submissions = frappe.get_all(
        "Exam Submission",
        filters={"candidate": frappe.session.user},
        fields=["name", "exam_schedule", "status", "additional_time_given"],
        ignore_permissions=True,
    )
    for sub in submissions:
        if sub["status"] in ("Registration Cancelled", "Aborted"):
            continue

        schedule = frappe.get_doc(
            "Exam Schedule", sub["exam_schedule"], ignore_permissions=True
        )
        exam = frappe.get_doc("Exam", schedule.exam, ignore_permissions=True)
        sched_status = schedule.get_status()

        if sched_status == "Completed":
            continue

        end_time = schedule.start_date_time + timedelta(
            minutes=schedule.duration + (sub["additional_time_given"] or 0)
        )
        if schedule.schedule_type == "Flexible":
            end_time += timedelta(days=schedule.schedule_expire_in_days or 0)

        flexible_note = ""
        if schedule.schedule_type == "Flexible":
            flexible_note = "Finish before " + format_datetime(
                end_time, "dd MMM, HH:mm"
            )

        card = {
            "kind": "exam",
            "badge_label": (schedule.get("badge") or "Exam"),
            "badge_class": "badge-exam",
            "role_label": None,
            "role_class": None,
            "submission_status": sub["status"],
            "action_disabled": False,
            "action_disabled_reason": None,
            "title": exam.title,
            "description": _short_desc(exam.description),
            "start_time": schedule.start_date_time,
            "start_time_display": format_datetime(
                schedule.start_date_time, "dd MMM YYYY, HH:mm"
            ),
            "schedule_type": schedule.schedule_type,
            "duration": f"{schedule.duration} min",
            "flexible_note": flexible_note,
            "certificate_template": exam.certificate_template,
            "action_link": "/exam",
            "status_label": None,
        }

        is_upcoming = sched_status == "Upcoming"
        is_live_window = sched_status == "Ongoing"

        if is_live_window:
            if sub["status"] in ("Registered", "Started"):
                card["action_text"] = (
                    "Continue Exam" if sub["status"] == "Started" else "Start Exam"
                )
                if schedule.schedule_type == "Fixed":
                    has_live_fixed = True
            elif sub["status"] == "Submitted":
                card["status_label"] = "Submitted"
                card["status_class"] = "status-passed"
            elif sub["status"] == "Terminated":
                card["status_label"] = "Terminated"
                card["status_class"] = "status-failed"
            else:
                card["status_label"] = sub["status"]
                card["status_class"] = "status-neutral"
            live.append(card)
        elif is_upcoming:
            upcoming.append(card)

    return live, upcoming, has_live_fixed


def _proctor_items():
    """Return (live, upcoming) proctor dashboard cards — one per exam schedule."""
    live, upcoming = [], []

    live_subs = frappe.get_all(
        "Exam Submission",
        filters={
            "assigned_proctor": frappe.session.user,
            "status": [
                "not in",
                ["Registration Cancelled", "Aborted", "Submitted", "Terminated"],
            ],
        },
        fields=["name", "exam_schedule", "status"],
    )
    by_schedule = {}
    for sub in live_subs:
        by_schedule.setdefault(sub["exam_schedule"], []).append(sub)

    now_dt = frappe.utils.now_datetime()
    for schedule_name, subs in by_schedule.items():
        schedule = frappe.get_doc(
            "Exam Schedule", schedule_name, ignore_permissions=True
        )
        end_time = schedule.start_date_time + timedelta(minutes=schedule.duration)
        if not (schedule.start_date_time <= now_dt <= end_time):
            continue
        exam_title = frappe.db.get_value("Exam", schedule.exam, "title")
        count = len(subs)
        live.append(
            {
                "kind": "proctor",
                "badge_label": (schedule.get("badge") or "Exam"),
                "badge_class": "badge-exam",
                "role_label": "Proctoring",
                "role_class": "badge-proctor",
                "title": exam_title,
                "description": f"{count} candidate{'' if count == 1 else 's'} to proctor.",
                "start_time": schedule.start_date_time,
                "start_time_display": format_datetime(
                    schedule.start_date_time, "dd MMM YYYY, HH:mm"
                ),
                "schedule_type": schedule.schedule_type,
                "duration": f"{schedule.duration} min",
                "flexible_note": "",
                "action_link": "/proctor",
                "action_text": "Open Proctor View",
            }
        )

    for ev in get_proctor_upcoming_events():
        sched_badge = frappe.db.get_value("Exam Schedule", ev["schedule_name"], "badge")
        upcoming.append(
            {
                "kind": "proctor",
                "badge_label": sched_badge or "Exam",
                "badge_class": "badge-exam",
                "role_label": "Proctoring",
                "role_class": "badge-proctor",
                "title": ev["exam_title"],
                "description": f"{ev['candidate_count']} candidate{'' if ev['candidate_count'] == 1 else 's'} assigned.",
                "start_time": ev["start_time"],
                "start_time_display": format_datetime(
                    ev["start_time"], "dd MMM YYYY, HH:mm"
                ),
                "schedule_type": "Fixed",
                "duration": f"{ev['duration']} min" if ev.get("duration") else "",
                "flexible_note": "",
                "action_link": "/proctor",
                "action_text": "View Schedule",
            }
        )

    return live, upcoming


def _evaluator_items():
    """Return live evaluator cards — one per exam schedule. No 'upcoming' state."""
    live = []
    pending = get_evaluator_live_exams(evaluator=frappe.session.user, completed=True)

    by_schedule = {}
    for sub in pending:
        key = sub.exam_schedule or sub.name
        entry = by_schedule.setdefault(key, {"title": sub.title, "count": 0})
        entry["count"] += 1

    for schedule_name, info in by_schedule.items():
        count = info["count"]
        sched_badge = (
            frappe.db.get_value("Exam Schedule", schedule_name, "badge")
            if schedule_name
            else None
        )
        live.append(
            {
                "kind": "evaluate",
                "badge_label": sched_badge or "Exam",
                "badge_class": "badge-exam",
                "role_label": "Evaluation",
                "role_class": "badge-evaluate",
                "title": info["title"],
                "description": f"{count} submission{'' if count == 1 else 's'} pending evaluation.",
                "start_time": None,
                "start_time_display": "Ready now",
                "schedule_type": "",
                "duration": "",
                "flexible_note": "",
                "action_link": "/evaluate",
                "action_text": "Open Evaluator",
            }
        )
    return live, []


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    submit_candidate_pending_exams()
    context.no_cache = 1

    roles = frappe.get_roles()
    is_proctor = "Exam Proctor" in roles
    is_evaluator = "Exam Evaluator" in roles

    live, upcoming, has_live_fixed = _candidate_items()
    context.auto_redirect_to_exam = has_live_fixed

    if is_proctor:
        p_live, p_upcoming = _proctor_items()
        live += p_live
        upcoming += p_upcoming

    if is_evaluator:
        e_live, _e_upcoming = _evaluator_items()
        live += e_live

    def _live_priority(c):
        """Priority for sorting live cards. Lower = higher priority.
        0 = candidate's Fixed exam that has been Started.
        1 = candidate's Fixed exam Registered but not yet started.
        2 = candidate's Flexible exam (ordered by start_time asc).
        3 = candidate exam in a terminal/status state (Submitted/Terminated).
        4 = proctor / evaluator cards.
        """
        if c.get("kind") != "exam":
            return (4, c["start_time"] or datetime.max)
        if not c.get("action_text"):
            return (3, c["start_time"] or datetime.max)
        if c.get("schedule_type") == "Fixed":
            return (
                0 if c.get("submission_status") == "Started" else 1,
                c["start_time"] or datetime.min,
            )
        return (2, c["start_time"] or datetime.max)

    live.sort(key=_live_priority)
    upcoming.sort(key=lambda c: c["start_time"] or datetime.max)

    # Only one exam can be active at a time. If any candidate Fixed exam is
    # currently live (registered or started), disable Start/Continue buttons
    # on every OTHER candidate exam card. The highest-priority Fixed card
    # (sorted to the top) keeps its action enabled.
    exam_live = [c for c in live if c.get("kind") == "exam" and c.get("action_text")]
    has_fixed_live = any(c.get("schedule_type") == "Fixed" for c in exam_live)
    if has_fixed_live and exam_live:
        active = exam_live[0]
        for c in exam_live[1:]:
            c["action_disabled"] = True
            c["action_disabled_reason"] = "Finish your active exam first"

    context.live_items = live
    context.upcoming_items = upcoming
    context.live_count = len(live)
    context.upcoming_count = len(upcoming)

    scopes = ["exams"]
    if is_proctor:
        scopes.append("proctoring")
    if is_evaluator:
        scopes.append("evaluation")
    if len(scopes) == 1:
        scope_text = scopes[0]
    elif len(scopes) == 2:
        scope_text = f"{scopes[0]} and {scopes[1]}"
    else:
        scope_text = ", ".join(scopes[:-1]) + f" and {scopes[-1]}"
    context.subheading = f"Your live and upcoming {scope_text}."

    context.open_exams = _open_exams()

    context.metatags = {
        "title": "Dashboard",
        "description": "Live and upcoming exams, proctoring and evaluation sessions",
    }


def _open_exams():
    """Return public exams with active schedules for the Open Exams section."""
    from frappe.utils import format_datetime

    schedules = frappe.get_all(
        "Exam Schedule",
        fields=[
            "name", "exam", "start_date_time", "schedule_type",
            "duration", "schedule_expire_in_days", "badge", "short_uuid",
        ],
        ignore_permissions=True,
    )

    exams_map = {}
    skipped_exams = set()
    for sched in schedules:
        exam_name = sched.exam

        if exam_name in skipped_exams:
            continue

        if exam_name not in exams_map:
            exam_doc = frappe.get_doc("Exam", exam_name)
            if not exam_doc.is_public:
                skipped_exams.add(exam_name)
                continue
            exams_map[exam_name] = {
                "name": exam_doc.name,
                "title": exam_doc.title,
                "description": _short_desc(exam_doc.description),
                "duration": exam_doc.duration,
                "question_type": exam_doc.question_type,
                "image": exam_doc.image,
                "enable_payment": exam_doc.enable_payment,
                "price": exam_doc.price,
                "schedules": [],
            }

        status = get_schedule_status(sched.name)
        if status == "Completed":
            continue
        if sched.schedule_type == "Fixed" and status != "Upcoming":
            continue

        exams_map[exam_name]["schedules"].append({
            "name": sched.name,
            "short_uuid": sched.short_uuid,
            "start_date_time": format_datetime(sched.start_date_time, "dd MMM YYYY, HH:mm"),
            "schedule_type": sched.schedule_type,
            "duration": sched.duration,
            "badge": sched.badge or "Exam",
        })

    return [e for e in exams_map.values() if e["schedules"]]
