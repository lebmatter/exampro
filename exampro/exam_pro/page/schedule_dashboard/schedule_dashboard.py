import frappe
from frappe.utils import flt
from exampro.exam_pro.doctype.exam_schedule.exam_schedule import (
    get_schedule_status,
    get_schedule_end_time,
)


CACHE_TTL = {
    "Upcoming": 300,
    "Ongoing": 30,
    "Completed": 600,
}


@frappe.whitelist()
def get_schedule_dashboard_data(schedule_name):
    user_roles = frappe.get_roles()
    if "System Manager" not in user_roles and "Exam Manager" not in user_roles:
        frappe.throw("Insufficient permissions to view this dashboard.")

    cache_key = f"schedule_dashboard:{schedule_name}"
    cached = frappe.cache().get_value(cache_key)
    if cached:
        return cached

    status = get_schedule_status(schedule_name)
    data = _build_schedule_metadata(schedule_name, status)
    data["status_counts"] = _get_status_counts(schedule_name)
    data["total_candidates"] = sum(data["status_counts"].values())

    if status == "Ongoing":
        data.update(_get_live_metrics(schedule_name))

    if status in ("Ongoing", "Completed"):
        data.update(_get_result_metrics(schedule_name))

    if status == "Completed":
        data.update(_get_evaluation_progress(schedule_name))

    ttl = CACHE_TTL.get(status, 60)
    frappe.cache().set_value(cache_key, data, expires_in_sec=ttl)
    return data


def _build_schedule_metadata(schedule_name, status):
    schedule = frappe.db.get_value(
        "Exam Schedule",
        schedule_name,
        ["exam", "start_date_time", "duration", "schedule_type", "schedule_expire_in_days"],
        as_dict=True,
    )
    if not schedule:
        frappe.throw("Exam Schedule not found.")

    exam = frappe.db.get_value(
        "Exam",
        schedule.exam,
        ["title", "total_marks", "pass_percentage", "question_type"],
        as_dict=True,
    )

    end_time = get_schedule_end_time(schedule_name)

    return {
        "schedule_name": schedule_name,
        "exam": schedule.exam,
        "exam_title": exam.title if exam else "",
        "start_date_time": str(schedule.start_date_time),
        "duration": schedule.duration,
        "schedule_type": schedule.schedule_type,
        "schedule_status": status,
        "end_time": str(end_time),
        "total_marks": flt(exam.total_marks) if exam else 0,
        "pass_percentage": flt(exam.pass_percentage) if exam else 0,
        "question_type": exam.question_type if exam else "Choices",
    }


def _get_status_counts(schedule_name):
    rows = frappe.db.sql(
        """
        SELECT status, COUNT(*) as count
        FROM `tabExam Submission`
        WHERE exam_schedule = %s
        GROUP BY status
        """,
        (schedule_name,),
        as_dict=True,
    )
    counts = {}
    for r in rows:
        counts[r.status] = r.count
    return counts


def _get_live_metrics(schedule_name):
    all_candidates = frappe.db.sql(
        """
        SELECT name, candidate, candidate_name, status, attention_score,
               warning_count, total_away_time, total_distracted_time
        FROM `tabExam Submission`
        WHERE exam_schedule = %s
        ORDER BY status, candidate_name
        """,
        (schedule_name,),
        as_dict=True,
    )

    live_candidates = [c for c in all_candidates if c.status == "Started"]
    candidates_live = len(live_candidates)
    avg_attention = 0
    total_warnings = 0
    avg_away = 0
    avg_distracted = 0

    if candidates_live:
        avg_attention = sum(flt(c.attention_score) for c in live_candidates) / candidates_live
        total_warnings = sum(c.warning_count or 0 for c in live_candidates)
        avg_away = sum(flt(c.total_away_time) for c in live_candidates) / candidates_live
        avg_distracted = sum(flt(c.total_distracted_time) for c in live_candidates) / candidates_live

    return {
        "candidates_live": candidates_live,
        "avg_attention_score_live": round(avg_attention, 1),
        "total_warnings_live": total_warnings,
        "avg_away_time_live": round(avg_away, 1),
        "avg_distracted_time_live": round(avg_distracted, 1),
        "live_candidates": live_candidates,
        "all_candidates": all_candidates,
    }


def _get_result_metrics(schedule_name):
    scores = frappe.db.sql(
        """
        SELECT total_marks
        FROM `tabExam Submission`
        WHERE exam_schedule = %s AND status = 'Submitted'
        """,
        (schedule_name,),
        as_dict=True,
    )

    result_counts = frappe.db.sql(
        """
        SELECT result_status, COUNT(*) as count
        FROM `tabExam Submission`
        WHERE exam_schedule = %s AND status = 'Submitted'
        GROUP BY result_status
        """,
        (schedule_name,),
        as_dict=True,
    )

    result_dist = {}
    for r in result_counts:
        result_dist[r.result_status] = r.count

    total_submitted = sum(result_dist.values())
    passed = result_dist.get("Passed", 0)

    marks_list = [flt(s.total_marks) for s in scores if s.total_marks is not None]

    bins = [0, 20, 40, 60, 80, 100]
    distribution = [0, 0, 0, 0, 0]
    for m in marks_list:
        for i in range(len(bins) - 1):
            if bins[i] <= m <= bins[i + 1]:
                distribution[i] += 1
                break

    recent = frappe.get_all(
        "Exam Submission",
        filters={"exam_schedule": schedule_name, "status": "Submitted"},
        fields=[
            "name", "candidate", "candidate_name",
            "exam_submitted_time", "total_marks", "result_status",
        ],
        order_by="exam_submitted_time desc",
        limit=10,
    )

    return {
        "pass_rate": round(passed / total_submitted * 100, 1) if total_submitted else 0,
        "avg_score": round(sum(marks_list) / len(marks_list), 2) if marks_list else 0,
        "max_score": max(marks_list) if marks_list else 0,
        "min_score": min(marks_list) if marks_list else 0,
        "score_distribution": distribution,
        "result_status_distribution": result_dist,
        "recent_submissions": recent,
    }


def _get_evaluation_progress(schedule_name):
    question_type = frappe.db.get_value(
        "Exam Schedule", schedule_name, "exam"
    )
    if question_type:
        question_type = frappe.db.get_value("Exam", question_type, "question_type")

    if question_type == "Choices":
        return {"evaluation_progress": None}

    total = frappe.db.count(
        "Exam Submission",
        {"exam_schedule": schedule_name, "status": "Submitted"},
    )
    evaluated = frappe.db.count(
        "Exam Submission",
        {
            "exam_schedule": schedule_name,
            "status": "Submitted",
            "evaluation_status": ["in", ["Done", "Auto"]],
        },
    )

    return {
        "evaluation_progress": {
            "total": total,
            "evaluated": evaluated,
            "pending": total - evaluated,
        }
    }
