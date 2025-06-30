import frappe
from frappe.utils import getdate, add_days, nowdate, flt
import json

@frappe.whitelist()
def get_dashboard_data(filters=None):
    """
    Get all data for the dashboard
    """
    if isinstance(filters, str):
        filters = json.loads(filters)
    
    if not filters:
        filters = {
            'start_date': add_days(nowdate(), -30),
            'end_date': nowdate()
        }
    
    # Initialize data object
    data = {
        'total_exams': get_total_exams(),
        'total_schedules': get_total_schedules(),
        'total_candidates': get_total_candidates(),
        'completed_exams': get_completed_exams(filters),
        'pass_rate': get_pass_rate(filters),
        'avg_score': get_avg_score(filters),
        'status_distribution': get_status_distribution(filters),
        'submission_trend': get_submission_trend(filters),
        'score_distribution': get_score_distribution(filters),
        'schedule_types': get_schedule_types(filters),
        'recent_submissions': get_recent_submissions(filters),
        'top_exams': get_top_exams(filters)
    }
    
    return data

def get_total_exams():
    """Return total number of exams"""
    return frappe.db.count('Exam')

def get_total_schedules():
    """Return total number of exam schedules"""
    return frappe.db.count('Exam Schedule')

def get_total_candidates():
    """Return total number of candidates"""
    # Count unique candidates in Exam Batch User
    batch_users = frappe.db.sql("""
        SELECT COUNT(DISTINCT candidate) as count 
        FROM `tabExam Batch User`
    """, as_dict=1)
    
    # Count unique candidates in Exam Submission
    submission_users = frappe.db.sql("""
        SELECT COUNT(DISTINCT candidate) as count 
        FROM `tabExam Submission`
    """, as_dict=1)
    
    # Return the higher count as some candidates might be in batches but not have submissions yet
    return max(batch_users[0].count if batch_users else 0, submission_users[0].count if submission_users else 0)

def get_completed_exams(filters):
    """Return number of completed exams within the filter period"""
    return frappe.db.count('Exam Submission', {
        'status': 'Submitted',
        'exam_submitted_time': ['between', [filters.get('start_date'), filters.get('end_date')]]
    })

def get_pass_rate(filters):
    """Calculate pass rate percentage"""
    total_submitted = frappe.db.count('Exam Submission', {
        'status': 'Submitted',
        'exam_submitted_time': ['between', [filters.get('start_date'), filters.get('end_date')]]
    })
    
    if not total_submitted:
        return 0
    
    passed = frappe.db.count('Exam Submission', {
        'status': 'Submitted',
        'result_status': 'Pass',
        'exam_submitted_time': ['between', [filters.get('start_date'), filters.get('end_date')]]
    })
    
    return int(passed / total_submitted * 100) if total_submitted > 0 else 0

def get_avg_score(filters):
    """Calculate average score of submitted exams"""
    avg_score = frappe.db.sql("""
        SELECT AVG(total_marks) as avg_score
        FROM `tabExam Submission`
        WHERE status = 'Submitted'
        AND exam_submitted_time BETWEEN %s AND %s
    """, (filters.get('start_date'), filters.get('end_date')), as_dict=1)
    
    return flt(avg_score[0].avg_score) if avg_score and avg_score[0].avg_score else 0

def get_status_distribution(filters):
    """Get distribution of exam submission statuses"""
    data = frappe.db.sql("""
        SELECT status, COUNT(*) as count
        FROM `tabExam Submission`
        WHERE creation BETWEEN %s AND %s
        GROUP BY status
    """, (filters.get('start_date'), filters.get('end_date')), as_dict=1)
    
    status_dict = {}
    for d in data:
        status_dict[d.status] = d.count
    
    return status_dict

def get_submission_trend(filters):
    """Get exam submission trend over the filter period"""
    start_date = getdate(filters.get('start_date'))
    end_date = getdate(filters.get('end_date'))
    
    # Calculate date intervals based on period length
    date_diff = (end_date - start_date).days
    
    if date_diff <= 7:
        # Daily intervals for periods up to a week
        interval = 1
        format_str = '%d %b'
    elif date_diff <= 31:
        # Every 3 days for a month
        interval = 3
        format_str = '%d %b'
    elif date_diff <= 90:
        # Weekly intervals for periods up to 3 months
        interval = 7
        format_str = '%d %b'
    else:
        # Monthly intervals for longer periods
        interval = 30
        format_str = '%b %Y'
    
    labels = []
    values = []
    
    current_date = start_date
    while current_date <= end_date:
        next_date = add_days(current_date, interval)
        if next_date > end_date:
            next_date = end_date
            
        # Format the label
        labels.append(current_date.strftime(format_str))
        
        # Count submissions in this interval
        count = frappe.db.count('Exam Submission', {
            'exam_submitted_time': ['between', [current_date, next_date]]
        })
        values.append(count)
        
        current_date = add_days(next_date, 1)
    
    return {
        'labels': labels,
        'values': values
    }

def get_score_distribution(filters):
    """Get distribution of scores in ranges"""
    bins = [0, 20, 40, 60, 80, 100]
    distribution = [0, 0, 0, 0, 0]  # For ranges 0-20, 21-40, 41-60, 61-80, 81-100
    
    # Get all scores from submitted exams
    scores = frappe.db.sql("""
        SELECT total_marks
        FROM `tabExam Submission`
        WHERE status = 'Submitted'
        AND exam_submitted_time BETWEEN %s AND %s
    """, (filters.get('start_date'), filters.get('end_date')), as_dict=1)
    
    for score_dict in scores:
        score = score_dict.total_marks
        if score is not None:
            # Place the score in the appropriate bin
            for i in range(len(bins) - 1):
                if bins[i] <= score <= bins[i+1]:
                    distribution[i] += 1
                    break
    
    return distribution

def get_schedule_types(filters):
    """Get distribution of schedule types (Fixed vs Flexible)"""
    data = frappe.db.sql("""
        SELECT schedule_type, COUNT(*) as count
        FROM `tabExam Schedule`
        WHERE creation BETWEEN %s AND %s
        GROUP BY schedule_type
    """, (filters.get('start_date'), filters.get('end_date')), as_dict=1)
    
    type_dict = {}
    for d in data:
        type_dict[d.schedule_type] = d.count
    
    return type_dict

def get_recent_submissions(filters):
    """Get recent exam submissions"""
    submissions = frappe.get_all(
        'Exam Submission',
        filters={
            'status': 'Submitted',
            'exam_submitted_time': ['between', [filters.get('start_date'), filters.get('end_date')]]
        },
        fields=[
            'name', 'candidate', 'candidate_name', 'exam', 
            'exam_submitted_time as submission_time', 
            'total_marks as score', 'result_status'
        ],
        order_by='exam_submitted_time desc',
        limit=10
    )
    
    return submissions

def get_top_exams(filters):
    """Get top exams by participation"""
    # Get exams with submission counts
    exams = frappe.db.sql("""
        SELECT es.exam, COUNT(DISTINCT es.name) as participants,
               AVG(es.total_marks) as avg_score
        FROM `tabExam Submission` es
        WHERE es.creation BETWEEN %s AND %s
        GROUP BY es.exam
        ORDER BY participants DESC
        LIMIT 10
    """, (filters.get('start_date'), filters.get('end_date')), as_dict=1)
    
    # Calculate pass rate for each exam
    for exam in exams:
        total = frappe.db.count('Exam Submission', {
            'exam': exam.exam,
            'status': 'Submitted',
            'creation': ['between', [filters.get('start_date'), filters.get('end_date')]]
        })
        
        if total > 0:
            passed = frappe.db.count('Exam Submission', {
                'exam': exam.exam,
                'status': 'Submitted',
                'result_status': 'Pass',
                'creation': ['between', [filters.get('start_date'), filters.get('end_date')]]
            })
            
            exam['pass_rate'] = int(passed / total * 100)
        else:
            exam['pass_rate'] = 0
    
    return exams
