import re
from collections import defaultdict
from math import ceil

import frappe
from frappe.utils import flt

from exampro.exam_pro.api.exam_studio import _check_manager_or_partner
from exampro.exam_pro.doctype.exam_schedule.exam_schedule import get_schedule_status


def _assert_exam_access(exam_name, partner):
	if partner:
		exam_partner = frappe.db.get_value("Exam", exam_name, "partner")
		if exam_partner != partner:
			frappe.throw("You do not have permission to access this exam.", frappe.PermissionError)


def _strip_html(text):
	return re.sub(r"<[^>]+>", " ", text or "").strip()


@frappe.whitelist()
def get_exam_meta(exam_name):
	partner = _check_manager_or_partner()
	_assert_exam_access(exam_name, partner)

	exam = frappe.db.get_value(
		"Exam",
		exam_name,
		["title", "total_marks", "pass_percentage", "duration", "question_type"],
		as_dict=True,
	)
	if not exam:
		frappe.throw("Exam not found.")
	exam["name"] = exam_name
	return exam


@frappe.whitelist()
def get_exam_schedules(exam_name):
	partner = _check_manager_or_partner()
	_assert_exam_access(exam_name, partner)

	rows = frappe.db.sql(
		"""
		SELECT name, start_date_time, schedule_type, badge
		FROM `tabExam Schedule`
		WHERE exam = %s
		ORDER BY start_date_time DESC
		""",
		(exam_name,),
		as_dict=True,
	)
	result = []
	for s in rows:
		result.append({
			"name": s.name,
			"start_date_time": str(s.start_date_time),
			"schedule_type": s.schedule_type,
			"badge": s.badge or "",
			"status": get_schedule_status(s.name),
		})
	return result


@frappe.whitelist()
def get_exam_summary(exam_name, schedule_name=None):
	partner = _check_manager_or_partner()
	_assert_exam_access(exam_name, partner)

	conds = "exam = %(exam)s AND status = 'Submitted'"
	vals = {"exam": exam_name}
	if schedule_name:
		conds += " AND exam_schedule = %(schedule)s"
		vals["schedule"] = schedule_name

	agg = frappe.db.sql(
		f"""
		SELECT
			COUNT(*) AS total_submissions,
			SUM(CASE WHEN result_status = 'Passed' THEN 1 ELSE 0 END) AS passed,
			SUM(CASE WHEN result_status = 'Failed' THEN 1 ELSE 0 END) AS failed,
			SUM(CASE WHEN evaluation_status = 'Pending' THEN 1 ELSE 0 END) AS pending_eval,
			AVG(total_marks) AS avg_score,
			MAX(total_marks) AS max_score,
			MIN(total_marks) AS min_score,
			AVG(TIMESTAMPDIFF(SECOND, exam_started_time, exam_submitted_time)) AS avg_completion_seconds
		FROM `tabExam Submission`
		WHERE {conds}
		""",
		vals,
		as_dict=True,
	)
	row = agg[0] if agg else {}
	total = int(row.get("total_submissions") or 0)
	passed = int(row.get("passed") or 0)

	exam_total_marks = flt(frappe.db.get_value("Exam", exam_name, "total_marks")) or 1
	scores = frappe.db.sql(
		f"SELECT total_marks FROM `tabExam Submission` WHERE {conds}",
		vals,
		as_dict=True,
	)
	distribution = [0, 0, 0, 0, 0]
	for s in scores:
		pct = flt(s.total_marks) / exam_total_marks * 100
		idx = min(int(pct // 20), 4)
		distribution[idx] += 1

	return {
		"total_submissions": total,
		"passed": passed,
		"failed": int(row.get("failed") or 0),
		"pending_eval": int(row.get("pending_eval") or 0),
		"pass_rate": round(passed / total * 100, 1) if total else 0,
		"avg_score": round(flt(row.get("avg_score")), 2),
		"max_score": round(flt(row.get("max_score")), 2),
		"min_score": round(flt(row.get("min_score")), 2),
		"avg_completion_time": round((flt(row.get("avg_completion_seconds")) or 0) / 60, 1),
		"score_distribution": distribution,
	}


@frappe.whitelist()
def get_question_stats(exam_name, schedule_name=None):
	partner = _check_manager_or_partner()
	_assert_exam_access(exam_name, partner)

	sub_conds = "es.exam = %(exam)s AND es.status IN ('Submitted', 'Terminated')"
	vals = {"exam": exam_name}
	if schedule_name:
		sub_conds += " AND es.exam_schedule = %(schedule)s"
		vals["schedule"] = schedule_name

	rows = frappe.db.sql(
		f"""
		SELECT
			ea.exam_question,
			ea.is_correct,
			ea.evaluation_status,
			ea.mark,
			es.name AS submission,
			es.total_marks AS submission_score
		FROM `tabExam Answer` ea
		JOIN `tabExam Submission` es ON ea.parent = es.name
		WHERE {sub_conds}
		""",
		vals,
		as_dict=True,
	)

	questions_meta = frappe.db.sql(
		"""
		SELECT
			eaq.exam_question,
			eaq.question,
			eaq.mark,
			eq.category,
			eq.difficulty,
			eq.type AS question_type
		FROM `tabExam Added Question` eaq
		LEFT JOIN `tabExam Question` eq ON eaq.exam_question = eq.name
		WHERE eaq.parent = %(exam)s
		""",
		{"exam": exam_name},
		as_dict=True,
	)
	meta_map = {q.exam_question: q for q in questions_meta}

	q_correct = defaultdict(set)
	q_total = defaultdict(set)
	sub_scores = {}

	for r in rows:
		qn = r.exam_question
		sub = r.submission
		sub_scores[sub] = flt(r.submission_score)

		if r.evaluation_status not in ("Not Attempted", None):
			q_total[qn].add(sub)
			if bool(r.is_correct) or (r.evaluation_status == "Done" and flt(r.mark) > 0):
				q_correct[qn].add(sub)

	all_subs = sorted(sub_scores.items(), key=lambda x: x[1])
	n = len(all_subs)
	k = max(1, ceil(n * 0.27))
	bottom_subs = {s for s, _ in all_subs[:k]}
	top_subs = {s for s, _ in all_subs[-k:]}

	result = []
	for qn, meta in meta_map.items():
		total_att = len(q_total.get(qn, set()))
		correct = len(q_correct.get(qn, set()))
		success_rate = round(correct / total_att * 100, 1) if total_att else None

		top_att = len(q_total.get(qn, set()) & top_subs)
		bot_att = len(q_total.get(qn, set()) & bottom_subs)
		top_correct = len(q_correct.get(qn, set()) & top_subs)
		bot_correct = len(q_correct.get(qn, set()) & bottom_subs)
		d_index = None
		if top_att and bot_att:
			d_index = round((top_correct / top_att) - (bot_correct / bot_att), 2)

		result.append({
			"exam_question": qn,
			"question": _strip_html(meta.question or "")[:120],
			"category": meta.category or "",
			"difficulty": meta.difficulty or "",
			"question_type": meta.question_type or "",
			"max_mark": flt(meta.mark),
			"total_attempts": total_att,
			"correct_count": correct,
			"success_rate": success_rate,
			"d_index": d_index,
		})

	return result


@frappe.whitelist()
def get_incident_stats(exam_name, schedule_name=None):
	partner = _check_manager_or_partner()
	_assert_exam_access(exam_name, partner)

	sub_conds = "es.exam = %(exam)s"
	vals = {"exam": exam_name}
	if schedule_name:
		sub_conds += " AND es.exam_schedule = %(schedule)s"
		vals["schedule"] = schedule_name

	rows = frappe.db.sql(
		f"""
		SELECT
			es.name AS submission,
			es.candidate,
			es.candidate_name,
			es.exam_schedule,
			esc.badge,
			es.attention_score,
			es.warning_count,
			em.warning_type,
			COUNT(*) AS cnt
		FROM `tabExam Messages` em
		JOIN `tabExam Submission` es ON em.exam_submission = es.name
		LEFT JOIN `tabExam Schedule` esc ON es.exam_schedule = esc.name
		WHERE {sub_conds}
			AND em.type_of_message IN ('Warning', 'Critical')
			AND em.warning_type IS NOT NULL
			AND em.warning_type != ''
		GROUP BY es.name, em.warning_type
		ORDER BY es.candidate_name ASC
		""",
		vals,
		as_dict=True,
	)

	incident_types = ["tabchange", "monitorchange", "nowebcam", "noface", "nofacetimeout", "nowebcamtimeout", "fullscreenexit", "other"]
	by_type = {t: 0 for t in incident_types}
	subs_seen = {}

	for r in rows:
		sub = r.submission
		wt = r.warning_type if r.warning_type in incident_types else "other"
		by_type[wt] = by_type.get(wt, 0) + int(r.cnt)

		if sub not in subs_seen:
			subs_seen[sub] = {
				"candidate": r.candidate,
				"candidate_name": r.candidate_name or r.candidate,
				"schedule": r.badge or r.exam_schedule or "",
				"attention_score": r.attention_score,
				"warning_count": r.warning_count or 0,
				**{t: 0 for t in incident_types},
				"total": 0,
			}
		subs_seen[sub][wt] = subs_seen[sub].get(wt, 0) + int(r.cnt)
		subs_seen[sub]["total"] += int(r.cnt)

	candidates = sorted(subs_seen.values(), key=lambda x: x["candidate_name"])
	total_incidents = sum(v for v in by_type.values())
	most_common = max(by_type, key=by_type.get) if total_incidents else ""

	return {
		"summary": {
			"total_incidents": total_incidents,
			"candidates_affected": len(candidates),
			"by_type": by_type,
			"most_common": most_common,
		},
		"candidates": candidates,
	}


INCIDENT_TYPE_LABELS = {
	"tabchange": "Tab Changes",
	"monitorchange": "Monitor Changes",
	"nowebcam": "No Webcam",
	"noface": "No Face",
	"nofacetimeout": "No Face Timeout",
	"nowebcamtimeout": "No Webcam Timeout",
	"fullscreenexit": "Fullscreen Exit",
	"other": "Other",
}


@frappe.whitelist()
def export_incidents_csv(exam_name, schedule_name=None):
	import csv
	import io

	partner = _check_manager_or_partner()
	_assert_exam_access(exam_name, partner)

	data = get_incident_stats(exam_name, schedule_name)
	candidates = data["candidates"]
	incident_types = ["tabchange", "monitorchange", "nowebcam", "noface", "nofacetimeout", "nowebcamtimeout", "fullscreenexit", "other"]

	output = io.StringIO()
	writer = csv.writer(output)
	writer.writerow([
		"Candidate Name", "Email", "Schedule", "Attention Score", "Warning Count",
		*[INCIDENT_TYPE_LABELS[t] for t in incident_types],
		"Total Incidents",
	])
	for c in candidates:
		writer.writerow([
			c.get("candidate_name", ""),
			c.get("candidate", ""),
			c.get("schedule", ""),
			c.get("attention_score", ""),
			c.get("warning_count", 0),
			*[c.get(t, 0) for t in incident_types],
			c.get("total", 0),
		])

	frappe.response["type"] = "csv"
	frappe.response["result"] = output.getvalue()
	frappe.response["doctype"] = "Incidents"


@frappe.whitelist()
def get_schedule_comparison(exam_name):
	partner = _check_manager_or_partner()
	_assert_exam_access(exam_name, partner)

	rows = frappe.db.sql(
		"""
		SELECT
			es.exam_schedule,
			esc.start_date_time,
			esc.badge,
			COUNT(*) AS candidate_count,
			SUM(CASE WHEN es.result_status = 'Passed' THEN 1 ELSE 0 END) AS passed,
			AVG(es.total_marks) AS avg_score,
			AVG(TIMESTAMPDIFF(SECOND, es.exam_started_time, es.exam_submitted_time)) AS avg_completion_seconds
		FROM `tabExam Submission` es
		JOIN `tabExam Schedule` esc ON es.exam_schedule = esc.name
		WHERE es.exam = %(exam)s AND es.status = 'Submitted'
		GROUP BY es.exam_schedule
		ORDER BY esc.start_date_time ASC
		""",
		{"exam": exam_name},
		as_dict=True,
	)

	result = []
	for r in rows:
		total = int(r.candidate_count or 0)
		passed = int(r.passed or 0)
		result.append({
			"schedule_name": r.exam_schedule,
			"start_date_time": str(r.start_date_time),
			"badge": r.badge or "",
			"candidate_count": total,
			"passed": passed,
			"pass_rate": round(passed / total * 100, 1) if total else 0,
			"avg_score": round(flt(r.avg_score), 2),
			"avg_completion_time": round((flt(r.avg_completion_seconds) or 0) / 60, 1),
		})

	return result
