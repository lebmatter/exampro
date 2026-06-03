from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.utils import format_datetime, strip_html

from exampro.exam_pro.api.utils import submit_candidate_pending_exams
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

		schedule = frappe.get_doc("Exam Schedule", sub["exam_schedule"], ignore_permissions=True)
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
			flexible_note = "Finish before " + format_datetime(end_time, "dd MMM, HH:mm")

		card = {
			"kind": "exam",
			"badge_label": "Exam",
			"badge_class": "badge-exam",
			"title": exam.title,
			"description": _short_desc(exam.description),
			"start_time": schedule.start_date_time,
			"start_time_display": format_datetime(schedule.start_date_time, "dd MMM YYYY, HH:mm"),
			"schedule_type": schedule.schedule_type,
			"duration": f"{schedule.duration} min",
			"flexible_note": flexible_note,
			"action_link": "/exam",
			"status_label": None,
		}

		is_upcoming = sched_status == "Upcoming"
		is_live_window = sched_status == "Ongoing"

		if is_live_window:
			if sub["status"] in ("Registered", "Started"):
				card["action_text"] = "Continue Exam" if sub["status"] == "Started" else "Start Exam"
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
			"status": ["not in", ["Registration Cancelled", "Aborted", "Submitted", "Terminated"]],
		},
		fields=["name", "exam_schedule", "status"],
	)
	by_schedule = {}
	for sub in live_subs:
		by_schedule.setdefault(sub["exam_schedule"], []).append(sub)

	now_dt = frappe.utils.now_datetime()
	for schedule_name, subs in by_schedule.items():
		schedule = frappe.get_doc("Exam Schedule", schedule_name, ignore_permissions=True)
		end_time = schedule.start_date_time + timedelta(minutes=schedule.duration)
		if not (schedule.start_date_time <= now_dt <= end_time):
			continue
		exam_title = frappe.db.get_value("Exam", schedule.exam, "title")
		count = len(subs)
		live.append({
			"kind": "proctor",
			"badge_label": "Proctoring",
			"badge_class": "badge-proctor",
			"title": exam_title,
			"description": f"{count} candidate{'' if count == 1 else 's'} to proctor.",
			"start_time": schedule.start_date_time,
			"start_time_display": format_datetime(schedule.start_date_time, "dd MMM YYYY, HH:mm"),
			"schedule_type": schedule.schedule_type,
			"duration": f"{schedule.duration} min",
			"flexible_note": "",
			"action_link": "/proctor",
			"action_text": "Open Proctor View",
		})

	for ev in get_proctor_upcoming_events():
		upcoming.append({
			"kind": "proctor",
			"badge_label": "Proctoring",
			"badge_class": "badge-proctor",
			"title": ev["exam_title"],
			"description": f"{ev['candidate_count']} candidate{'' if ev['candidate_count'] == 1 else 's'} assigned.",
			"start_time": ev["start_time"],
			"start_time_display": format_datetime(ev["start_time"], "dd MMM YYYY, HH:mm"),
			"schedule_type": "Fixed",
			"duration": f"{ev['duration']} min" if ev.get("duration") else "",
			"flexible_note": "",
			"action_link": "/proctor",
			"action_text": "View Schedule",
		})

	return live, upcoming


def _evaluator_items():
	"""Return live evaluator cards — one per exam. No 'upcoming' state."""
	live = []
	pending = get_evaluator_live_exams(evaluator=frappe.session.user, completed=True)

	by_exam = {}
	for sub in pending:
		# evaluate.get_evaluator_live_exams sets sub.name = exam.name
		exam_key = sub.name
		entry = by_exam.setdefault(exam_key, {"title": sub.title, "count": 0, "last_submitted": None})
		entry["count"] += 1
		ts = sub.exam_submitted_time
		if ts and (entry["last_submitted"] is None or str(ts) > str(entry["last_submitted"])):
			entry["last_submitted"] = ts

	for exam_name, info in by_exam.items():
		count = info["count"]
		live.append({
			"kind": "evaluate",
			"badge_label": "Evaluation",
			"badge_class": "badge-evaluate",
			"title": info["title"],
			"description": f"{count} submission{'' if count == 1 else 's'} pending evaluation.",
			"start_time": None,
			"start_time_display": "Ready now",
			"schedule_type": "",
			"duration": "",
			"flexible_note": "",
			"action_link": "/evaluate",
			"action_text": "Open Evaluator",
		})
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

	live.sort(key=lambda c: c["start_time"] or datetime.min)
	upcoming.sort(key=lambda c: c["start_time"] or datetime.max)

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

	context.metatags = {
		"title": "Dashboard",
		"description": "Live and upcoming exams, proctoring and evaluation sessions",
	}
