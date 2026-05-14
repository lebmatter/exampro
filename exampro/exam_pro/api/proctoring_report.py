import frappe
import json
import pdfkit
import base64
import requests
from frappe import _
from datetime import datetime
from exampro.exam_pro.doctype.exam_submission.exam_submission import get_s3_client

WARNING_TYPE_LABELS = {
    "tabchange": "Tab Switch",
    "monitorchange": "Monitor Change",
    "nowebcam": "Webcam Not Found",
    "noface": "No Face Detected",
    "multiplefaces": "Multiple Faces Detected",
    "gazeaway": "Gaze Away",
    "nofacetimeout": "No Face (Timeout)",
    "appswitch": "App Switch",
    "other": "Other Violation"
}

@frappe.whitelist()
def generate_proctoring_report(exam_submission):
    """
    Generate a proctoring report PDF for an exam submission.
    Returns base64 encoded PDF string.
    """
    # 1. Permission check
    doc = frappe.get_doc("Exam Submission", exam_submission)
    if not (frappe.has_permission("Exam Submission", "read", doc.name) or 
            frappe.session.user == "Administrator"):
        frappe.throw(_("You don't have permission to access this report."), frappe.PermissionError)

    # 2. Gather Data
    context = get_report_context(doc)
    
    # 3. Render HTML
    html_content = frappe.render_template("templates/proctoring_report.html", context)
    
    # 4. Generate PDF using pdfkit
    # Basic options for pdfkit
    options = {
        'page-size': 'A4',
        'margin-top': '0.75in',
        'margin-right': '0.75in',
        'margin-bottom': '0.75in',
        'margin-left': '0.75in',
        'encoding': "UTF-8"
    }
    
    try:
        pdf_bytes = pdfkit.from_string(html_content, False, options=options)
        return base64.b64encode(pdf_bytes).decode('utf-8')
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), _("Proctoring Report Generation Error"))
        frappe.throw(_("Error generating PDF: {0}").format(str(e)))

@frappe.whitelist()
def download_proctoring_report(exam_submission):
    """
    Direct download link for proctoring report.
    """
    pdf_base64 = generate_proctoring_report(exam_submission)
    pdf_bytes = base64.b64decode(pdf_base64)
    
    frappe.local.response.filename = f"proctoring_report_{exam_submission}.pdf"
    frappe.local.response.filecontent = pdf_bytes
    frappe.local.response.type = "download"

def get_report_context(doc):
    """
    Gathers all data needed for the proctoring report template.
    """
    exam = frappe.get_doc("Exam", doc.exam)
    schedule = frappe.get_doc("Exam Schedule", doc.exam_schedule)
    
    # Candidate details
    candidate_user = frappe.get_doc("User", doc.candidate)
    
    # Timing logic
    start_time = doc.exam_started_time
    submit_time = doc.exam_submitted_time
    duration_mins = 0
    if start_time and submit_time:
        diff = submit_time - start_time
        duration_mins = int(diff.total_seconds() / 60)
    
    # Violations from Exam Messages
    messages = frappe.get_all("Exam Messages", 
        filters={"exam_submission": doc.name, "type_of_message": "Warning"},
        fields=["name", "warning_type", "message", "timestamp", "from"],
        order_by="timestamp asc"
    )
    
    # Violation Snapshots from S3
    snapshots = get_s3_snapshots(doc.name)
    
    # Prepare snapshots with base64 data FIRST so we can match them
    evidence_log = prepare_evidence_log(doc.name, snapshots, start_time)
    # Format violations for template
    formatted_violations = []
    violation_summary = {}
    
    # Calculate timezone offset between DB timestamps and S3 filename timestamps
    timezone_offset = 0
    if len(messages) > 0 and len(evidence_log) > 0:
        first_msg_ts = messages[0].timestamp.timestamp()
        first_snap_ts = evidence_log[0]["unix_ts"]
        timezone_offset = first_snap_ts - first_msg_ts
        frappe.log_error(f"Calculated timezone offset: {timezone_offset} seconds", "Proctoring Report Debug")
    
    for msg in messages:
        label = WARNING_TYPE_LABELS.get(msg.warning_type, msg.warning_type or "Violation")
        violation_summary[label] = violation_summary.get(label, 0) + 1
        
        # Calculate relative timestamp
        rel_ts = ""
        if start_time:
            diff = msg.timestamp - start_time
            total_seconds = int(diff.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            rel_ts = f"{hours:02}:{minutes:02}:{seconds:02}"
            
        # Find matching snapshots
        # Apply the calculated timezone offset to align DB time with S3 filename time
        msg_unix_ts = msg.timestamp.timestamp() + timezone_offset
        matched_snapshots = None
        
        # We look for snapshots within a 10-second window
        for group in evidence_log:
            if abs(group["unix_ts"] - msg_unix_ts) < 10:
                matched_snapshots = group
                break

        formatted_violations.append({
            "type": label,
            "raw_type": msg.warning_type,
            "timestamp": rel_ts,
            "absolute_time": frappe.utils.format_datetime(msg.timestamp, "dd MMM hh:mm a"),
            "message": msg.message,
            "from": msg.get("from"),
            "webcam": matched_snapshots["webcam"] if matched_snapshots else None,
            "screen": matched_snapshots["screen"] if matched_snapshots else None
        })


    return {
        "doc": doc,
        "candidate_name": doc.candidate_name,
        "candidate_email": doc.candidate,
        "candidate_image": get_base64_image(candidate_user.user_image),
        "exam_title": exam.title,
        "exam_schedule": schedule.name,
        "submission_name": doc.name,
        "status": doc.status,
        
        "exam_started_time": frappe.utils.format_datetime(start_time, "dd MMM hh:mm a") if start_time else "N/A",
        "exam_submitted_time": frappe.utils.format_datetime(submit_time, "dd MMM hh:mm a") if submit_time else "N/A",
        "exam_duration_minutes": duration_mins,
        "scheduled_duration": schedule.duration,
        
        "total_marks": doc.total_marks,
        "exam_total_marks": exam.total_marks,
        "result_status": doc.result_status,
        "pass_percentage": exam.pass_percentage,
        
        "attention_score": doc.attention_score or 0,
        "warning_count": doc.warning_count or 0,
        "face_count_changes": doc.face_count_changes or 0,
        "total_away_time_seconds": round(doc.total_away_time or 0, 1),
        "total_distracted_time_seconds": round(doc.total_distracted_time or 0, 1),
        "max_warning_count": exam.max_warning_count,
        
        "video_proctoring_enabled": getattr(exam, 'enable_video_proctoring', None),
        "tracking_features": get_tracking_features(exam),
        
        "violations": formatted_violations,
        "violation_summary": violation_summary,
        "evidence_log": evidence_log,
        
        "has_violations": len(formatted_violations) > 0,
        "has_evidence": len(evidence_log) > 0,
        
        "generated_at": frappe.utils.format_datetime(frappe.utils.now_datetime(), "dd MMM yyyy hh:mm a"),
        "generated_by": frappe.session.user,
    }

def get_tracking_features(exam):
    features = []
    if getattr(exam, 'enable_video_proctoring', None):
        features.append("Webcam")
    # enable_screen_capture does not exist on the Exam doctype —
    # screen capture is always attempted by the JS client when the exam starts.
    # We infer it from whether the exam has video proctoring on.
    if getattr(exam, 'enable_video_proctoring', None):
        features.append("Screen Share")
    features.append("Tab Switch Detection")
    features.append("Gaze Tracking")
    return features

def get_s3_snapshots(exam_submission):
    """
    Lists all .jpg files in the violations folder for this submission.
    """
    try:
        settings = frappe.get_single("Exam Settings")
        s3_client = get_s3_client()
        prefix = f"{exam_submission}/violations/"
        
        snapshots = []
        paginator = s3_client.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=settings.s3_bucket, Prefix=prefix):
            if 'Contents' in page:
                for obj in page['Contents']:
                    if obj['Key'].lower().endswith('.jpg'):
                        snapshots.append(obj['Key'])
        
        if not snapshots:
            frappe.log_error(f"No snapshots found for prefix: {prefix}", "Proctoring Report Debug")
        else:
            frappe.log_error(f"Found {len(snapshots)} snapshots for {exam_submission}", "Proctoring Report Debug")
            
        return snapshots
    except Exception as e:
        frappe.log_error(f"S3 Error in get_s3_snapshots: {str(e)}")
        return []

def prepare_evidence_log(exam_submission, snapshot_items, start_time):
    """
    Downloads each snapshot and converts to base64.
    Returns a list of dicts with metadata and base64 data.
    """
    log = []
    settings = frappe.get_single("Exam Settings")
    s3_client = get_s3_client()
    
    # Sort snapshot keys by time (embedded in filename)
    # Pattern: {type}_{timestamp}_{source}.jpg
    # example: tabchange_1715600000_webcam.jpg
    
    # We will sort by the parsed timestamp string later
    snapshot_items.sort()
    
    # To keep the report clean, we group webcam and screen snapshots if they have the same timestamp
    grouped = {} # keyed by timestamp_type
    
    for key in snapshot_items:
        try:
            filename = key.split("/")[-1]
            parts = filename.replace(".jpg", "").split("_")
            
            v_type = parts[0]
            v_source = parts[-1] # always the last part: webcam or screen
            
            # Extract timestamp parts: {type}_{YYYYMMDD}_{HHMMSS}_{ffffff}_{source}.jpg
            if len(parts) >= 5:
                v_ts_str = f"{parts[1]}_{parts[2]}_{parts[3]}"
                try:
                    dt = datetime.strptime(v_ts_str, "%Y%m%d_%H%M%S_%f")
                    unix_ts = dt.timestamp()
                except:
                    unix_ts = 0
            elif len(parts) >= 3:
                v_ts_str = parts[1]
                try:
                    unix_ts = int(v_ts_str)
                except:
                    unix_ts = 0
            else:
                continue
            
            # Use a rounded timestamp for grouping (within 2 seconds)
            group_ts = round(unix_ts / 2) * 2
            group_id = f"{group_ts}_{v_type}"
            
            if group_id not in grouped:
                grouped[group_id] = {
                    "type": WARNING_TYPE_LABELS.get(v_type, v_type),
                    "unix_ts": unix_ts,
                    "rel_ts": format_rel_ts(unix_ts, start_time),
                    "webcam": None,
                    "screen": None
                }
            
            # Download and base64
            obj = s3_client.get_object(Bucket=settings.s3_bucket, Key=key)
            img_data = obj['Body'].read()
            b64 = base64.b64encode(img_data).decode('utf-8')
            
            if v_source == "webcam":
                grouped[group_id]["webcam"] = f"data:image/jpeg;base64,{b64}"
            else:
                grouped[group_id]["screen"] = f"data:image/jpeg;base64,{b64}"
        except Exception as e:
            frappe.log_error(f"Error processing snapshot {key}: {str(e)}")
            
    # Convert grouped dict to sorted list
    log = list(grouped.values())
    log.sort(key=lambda x: x["unix_ts"])
    
    return log

def format_rel_ts(unix_ts, start_time):
    if not start_time: return ""
    try:
        dt = datetime.fromtimestamp(unix_ts)
        diff = dt - start_time.replace(tzinfo=None)
        total_seconds = int(diff.total_seconds())
        if total_seconds < 0: total_seconds = 0
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}"
    except:
        return ""

def get_base64_image(file_url):
    if not file_url: return None
    from exampro.exam_pro.doctype.exam_submission.exam_submission import convert_image_to_base64
    b64 = convert_image_to_base64(file_url)
    if b64:
        if not b64.startswith("data:"):
            return f"data:image/jpeg;base64,{b64}"
        return b64
    return None
