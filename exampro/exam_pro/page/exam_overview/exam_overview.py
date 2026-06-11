import frappe
from frappe.utils import flt
from exampro.exam_pro.doctype.exam_schedule.exam_schedule import get_schedule_status


@frappe.whitelist()
def get_exam_overview_data(exam_name):
    user_roles = frappe.get_roles()
    if "System Manager" not in user_roles and "Exam Manager" not in user_roles:
        frappe.throw("Insufficient permissions to view this dashboard.")

    cache_key = f"exam_overview:{exam_name}"
    cached = frappe.cache().get_value(cache_key)
    if cached:
        return cached

    data = _build_exam_metadata(exam_name)
    data["question_breakdown"] = _get_question_breakdown(exam_name)
    data["candidate_stats"] = _get_candidate_stats(exam_name)
    data["schedules"] = _get_schedules(exam_name)
    data["score_distribution"] = _get_score_distribution(exam_name)
    data["result_distribution"] = _get_result_distribution(exam_name)

    if data.get("enable_certification"):
        data["certification_stats"] = _get_certification_stats(exam_name)

    if data.get("question_type") != "Choices":
        data["evaluation_stats"] = _get_evaluation_stats(exam_name)

    frappe.cache().set_value(cache_key, data, expires_in_sec=300)
    return data


def _build_exam_metadata(exam_name):
    exam = frappe.db.get_value(
        "Exam",
        exam_name,
        [
            "title", "duration", "pass_percentage", "total_marks", "total_questions",
            "question_type", "enable_certification", "certificate_template",
            "evaluation_required", "enable_video_proctoring", "max_warning_count",
            "leaderboard", "randomize_questions",
        ],
        as_dict=True,
    )
    if not exam:
        frappe.throw("Exam not found.")

    return {
        "exam_name": exam_name,
        "title": exam.title,
        "duration": exam.duration,
        "pass_percentage": flt(exam.pass_percentage),
        "total_marks": flt(exam.total_marks),
        "total_questions": exam.total_questions or 0,
        "question_type": exam.question_type,
        "enable_certification": exam.enable_certification,
        "certificate_template": exam.certificate_template,
        "evaluation_required": exam.evaluation_required,
        "enable_video_proctoring": exam.enable_video_proctoring,
        "max_warning_count": exam.max_warning_count,
        "leaderboard": exam.leaderboard,
        "randomize_questions": exam.randomize_questions,
    }


def _get_question_breakdown(exam_name):
    from exampro.exam_pro.doctype.exam.exam import get_question_categories
    result = get_question_categories(exam_name)
    if result and result.get("success"):
        return {
            "categories": result.get("categories", []),
            "exam_config": result.get("exam_config", {}),
        }
    return {"categories": [], "exam_config": {}}


def _get_candidate_stats(exam_name):
    status_rows = frappe.db.sql(
        """
        SELECT status, COUNT(*) as count
        FROM `tabExam Submission`
        WHERE exam = %s
        GROUP BY status
        """,
        (exam_name,),
        as_dict=True,
    )
    status_counts = {}
    for r in status_rows:
        status_counts[r.status] = r.count

    total = sum(status_counts.values())
    submitted = status_counts.get("Submitted", 0)

    score_agg = frappe.db.sql(
        """
        SELECT AVG(total_marks) as avg_score, MAX(total_marks) as max_score,
               MIN(total_marks) as min_score
        FROM `tabExam Submission`
        WHERE exam = %s AND status = 'Submitted'
        """,
        (exam_name,),
        as_dict=True,
    )
    agg = score_agg[0] if score_agg else {}

    result_rows = frappe.db.sql(
        """
        SELECT result_status, COUNT(*) as count
        FROM `tabExam Submission`
        WHERE exam = %s AND status = 'Submitted'
        GROUP BY result_status
        """,
        (exam_name,),
        as_dict=True,
    )
    result_counts = {}
    for r in result_rows:
        result_counts[r.result_status] = r.count

    passed = result_counts.get("Passed", 0)
    pass_rate = round(passed / submitted * 100, 1) if submitted else 0

    return {
        "total": total,
        "status_counts": status_counts,
        "submitted": submitted,
        "passed": passed,
        "failed": result_counts.get("Failed", 0),
        "pass_rate": pass_rate,
        "avg_score": round(flt(agg.get("avg_score")), 2),
        "max_score": flt(agg.get("max_score")),
        "min_score": flt(agg.get("min_score")),
    }


def _get_schedules(exam_name):
    schedules = frappe.db.sql(
        """
        SELECT name, start_date_time, schedule_type
        FROM `tabExam Schedule`
        WHERE exam = %s
        ORDER BY start_date_time DESC
        """,
        (exam_name,),
        as_dict=True,
    )

    candidate_counts = frappe.db.sql(
        """
        SELECT exam_schedule, COUNT(*) as count
        FROM `tabExam Submission`
        WHERE exam = %s
        GROUP BY exam_schedule
        """,
        (exam_name,),
        as_dict=True,
    )
    count_map = {r.exam_schedule: r.count for r in candidate_counts}

    status_summary = {"Upcoming": 0, "Ongoing": 0, "Completed": 0}
    for s in schedules:
        s["candidates"] = count_map.get(s.name, 0)
        s["status"] = get_schedule_status(s.name)
        s["start_date_time"] = str(s.start_date_time)
        status_summary[s["status"]] = status_summary.get(s["status"], 0) + 1

    return {
        "total": len(schedules),
        "status_summary": status_summary,
        "list": schedules,
    }


def _get_score_distribution(exam_name):
    scores = frappe.db.sql(
        """
        SELECT total_marks
        FROM `tabExam Submission`
        WHERE exam = %s AND status = 'Submitted'
        """,
        (exam_name,),
        as_dict=True,
    )

    bins = [0, 20, 40, 60, 80, 100]
    distribution = [0, 0, 0, 0, 0]
    for s in scores:
        m = flt(s.total_marks)
        for i in range(len(bins) - 1):
            if bins[i] <= m <= bins[i + 1]:
                distribution[i] += 1
                break

    return distribution


def _get_result_distribution(exam_name):
    rows = frappe.db.sql(
        """
        SELECT result_status, COUNT(*) as count
        FROM `tabExam Submission`
        WHERE exam = %s AND status = 'Submitted'
        GROUP BY result_status
        """,
        (exam_name,),
        as_dict=True,
    )
    return {r.result_status: r.count for r in rows}


def _get_certification_stats(exam_name):
    issued = frappe.db.count("Exam Certificate", {"exam": exam_name})
    passed = frappe.db.count(
        "Exam Submission",
        {"exam": exam_name, "status": "Submitted", "result_status": "Passed"},
    )
    return {
        "issued": issued,
        "eligible": passed,
        "pending": max(0, passed - issued),
    }


def _get_evaluation_stats(exam_name):
    total = frappe.db.count(
        "Exam Submission",
        {"exam": exam_name, "status": "Submitted"},
    )
    evaluated = frappe.db.count(
        "Exam Submission",
        {
            "exam": exam_name,
            "status": "Submitted",
            "evaluation_status": ["in", ["Done", "Auto"]],
        },
    )
    return {
        "total": total,
        "evaluated": evaluated,
        "pending": total - evaluated,
    }
