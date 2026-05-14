import frappe
import json
import pdfkit
import base64
import requests
import tempfile
import os
from frappe import _
from datetime import datetime, timezone
import pytz
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
    doc = frappe.get_doc("Exam Submission", exam_submission)
    if not (frappe.has_permission("Exam Submission", "read", doc.name) or
            frappe.session.user == "Administrator"):
        frappe.throw(_("You don't have permission to access this report."), frappe.PermissionError)

    context = get_report_context(doc)
    html_content = frappe.render_template("templates/proctoring_report.html", context)

    options = {
        'page-size': 'A4',
        'margin-top': '0.75in',
        'margin-right': '0.75in',
        'margin-bottom': '0.75in',
        'margin-left': '0.75in',
        'encoding': "UTF-8",
        # ✅ FIX Bug 4 — required for base64 image rendering in wkhtmltopdf
        'enable-local-file-access': None,
        'no-stop-slow-scripts': None,
        'images': None,
        'disable-smart-shrinking': None,
        'print-media-type': None,
    }

    try:
        pdf_bytes = pdfkit.from_string(html_content, False, options=options)
        return base64.b64encode(pdf_bytes).decode('utf-8')
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), _("Proctoring Report Generation Error"))
        frappe.throw(_("Error generating PDF: {0}").format(str(e)))


@frappe.whitelist()
def download_proctoring_report(exam_submission):
    pdf_base64 = generate_proctoring_report(exam_submission)
    pdf_bytes = base64.b64decode(pdf_base64)
    frappe.local.response.filename = f"proctoring_report_{exam_submission}.pdf"
    frappe.local.response.filecontent = pdf_bytes
    frappe.local.response.type = "download"


def get_report_context(doc):
    exam = frappe.get_doc("Exam", doc.exam)
    schedule = frappe.get_doc("Exam Schedule", doc.exam_schedule)
    candidate_user = frappe.get_doc("User", doc.candidate)

    start_time = doc.exam_started_time
    submit_time = doc.exam_submitted_time
    duration_mins = 0
    if start_time and submit_time:
        diff = submit_time - start_time
        duration_mins = int(diff.total_seconds() / 60)

    messages = frappe.get_all(
        "Exam Messages",
        filters={"exam_submission": doc.name, "type_of_message": "Warning"},
        fields=["name", "warning_type", "message", "timestamp", "from",
                "webcam_snapshot_key", "screen_snapshot_key"],
        order_by="timestamp asc"
    )

    # Separate messages into those with stored S3 keys (new) and those without (old).
    msgs_with_keys    = [m for m in messages if m.get("webcam_snapshot_key") or m.get("screen_snapshot_key")]
    msgs_without_keys = [m for m in messages if not m.get("webcam_snapshot_key") and not m.get("screen_snapshot_key")]

    # For old messages: fall back to listing S3 and timestamp-matching.
    snapshots   = get_s3_snapshots(doc.name) if msgs_without_keys else []
    evidence_log = prepare_evidence_log(doc.name, snapshots, start_time) if snapshots else []

    # Pre-fetch images for messages that already have stored S3 keys.
    settings   = frappe.get_single("Exam Settings")
    s3_client  = get_s3_client()
    key_images = {}   # msg.name → {"webcam": data_uri | None, "screen": data_uri | None}
    for m in msgs_with_keys:
        key_images[m.name] = {
            "webcam": _download_s3_key(s3_client, settings.s3_bucket, m.webcam_snapshot_key),
            "screen": _download_s3_key(s3_client, settings.s3_bucket, m.screen_snapshot_key),
        }

    frappe.log_error(
        f"Messages total: {len(messages)} | with stored keys: {len(msgs_with_keys)} | legacy: {len(msgs_without_keys)}\n"
        f"S3 listing {'skipped' if not msgs_without_keys else f'found {len(snapshots)} files'}\n"
        f"Evidence log size: {len(evidence_log)}",
        "Proctoring Report Debug"
    )

    formatted_violations = []
    violation_summary = {}
    _sys_tz = pytz.timezone(frappe.utils.get_system_timezone())

    for msg in messages:
        label = WARNING_TYPE_LABELS.get(msg.warning_type, msg.warning_type or "Violation")
        violation_summary[label] = violation_summary.get(label, 0) + 1

        rel_ts = ""
        if start_time:
            diff = msg.timestamp - start_time
            total_seconds = int(diff.total_seconds())
            if total_seconds < 0:
                total_seconds = 0
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            rel_ts = f"{hours:02}:{minutes:02}:{seconds:02}"

        # Path 1 — message has stored S3 keys (new records).
        if msg.name in key_images:
            webcam_img = key_images[msg.name]["webcam"]
            screen_img = key_images[msg.name]["screen"]
            snapshot_diff = None
        else:
            # Path 2 — old record: match against the timestamp-based evidence_log.
            msg_unix_ts = _sys_tz.localize(msg.timestamp).timestamp()
            matched = None
            best_diff = float('inf')
            for group in evidence_log:
                diff = abs(group["unix_ts"] - msg_unix_ts)
                if diff < 30 and diff < best_diff:
                    best_diff = diff
                    matched = group
            webcam_img = matched["webcam"] if matched else None
            screen_img = matched["screen"] if matched else None
            snapshot_diff = round(best_diff, 1) if matched else None

        formatted_violations.append({
            "type": label,
            "raw_type": msg.warning_type,
            "timestamp": rel_ts,
            "absolute_time": frappe.utils.format_datetime(msg.timestamp, "dd MMM hh:mm:ss a"),
            "message": msg.message,
            "from": msg.get("from"),
            "webcam": webcam_img,
            "screen": screen_img,
            "snapshot_ts_diff": snapshot_diff,
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
        features.append("Screen Share")
    features.append("Tab Switch Detection")
    features.append("Gaze Tracking")
    return features


def get_s3_snapshots(exam_submission):
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

        frappe.log_error(
            f"S3 prefix scanned: {prefix}\n"
            f"Total .jpg files found: {len(snapshots)}\n"
            f"First 5 keys: {snapshots[:5]}",
            "S3 Snapshot Fetch"
        )
        return snapshots

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "S3 get_s3_snapshots Error")
        return []


def prepare_evidence_log(exam_submission, snapshot_items, start_time):
    if not snapshot_items:
        return []

    log = []
    settings = frappe.get_single("Exam Settings")
    s3_client = get_s3_client()

    snapshot_items.sort()
    grouped = {}

    for key in snapshot_items:
        try:
            filename = key.split("/")[-1]
            # ✅ FIX Bug 3 — don't blindly split by _ for source type
            # Determine source first (always ends in _webcam.jpg or _screen.jpg)
            if filename.endswith("_webcam.jpg"):
                v_source = "webcam"
                stem = filename[:-len("_webcam.jpg")]
            elif filename.endswith("_screen.jpg"):
                v_source = "screen"
                stem = filename[:-len("_screen.jpg")]
            else:
                frappe.log_error(f"Unrecognised filename format: {filename}", "Snapshot Parse")
                continue

            parts = stem.split("_")
            v_type = parts[0]
            unix_ts = 0

            # ✅ FIX Bug 2 — try multiple known timestamp formats with explicit UTC
            # Format A: {type}_{YYYYMMDD}_{HHMMSS}_{ffffff}
            if len(parts) >= 4:
                ts_str = f"{parts[1]}_{parts[2]}_{parts[3]}"
                try:
                    dt = datetime.strptime(ts_str, "%Y%m%d_%H%M%S_%f")
                    # ✅ Treat S3 filename timestamps as UTC (JS Date.now() is UTC)
                    unix_ts = dt.replace(tzinfo=timezone.utc).timestamp()
                except ValueError:
                    pass

            # Format B: {type}_{unix_epoch_ms}
            if unix_ts == 0 and len(parts) >= 2:
                try:
                    raw = int(parts[1])
                    # Detect milliseconds vs seconds
                    unix_ts = raw / 1000.0 if raw > 1e10 else float(raw)
                except ValueError:
                    pass

            # Format C: {type}_{YYYYMMDD}_{HHMMSS} (no microseconds)
            if unix_ts == 0 and len(parts) >= 3:
                ts_str = f"{parts[1]}_{parts[2]}"
                try:
                    dt = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
                    unix_ts = dt.replace(tzinfo=timezone.utc).timestamp()
                except ValueError:
                    pass

            if unix_ts == 0:
                frappe.log_error(
                    f"Could not parse timestamp from: {filename} (parts={parts})",
                    "Snapshot Timestamp Parse"
                )
                continue

            # Group webcam+screen that belong to the same event (within 3 seconds)
            group_ts = round(unix_ts / 3) * 3
            group_id = f"{group_ts}_{v_type}"

            if group_id not in grouped:
                grouped[group_id] = {
                    "type": WARNING_TYPE_LABELS.get(v_type, v_type),
                    "unix_ts": unix_ts,
                    "rel_ts": format_rel_ts(unix_ts, start_time),
                    "webcam": None,
                    "screen": None,
                }

            # Download from S3 and convert to base64
            obj = s3_client.get_object(Bucket=settings.s3_bucket, Key=key)
            img_bytes = obj['Body'].read()
            b64 = base64.b64encode(img_bytes).decode('utf-8')
            data_uri = f"data:image/jpeg;base64,{b64}"

            if v_source == "webcam":
                grouped[group_id]["webcam"] = data_uri
            else:
                grouped[group_id]["screen"] = data_uri

        except Exception as e:
            frappe.log_error(f"Error processing snapshot '{key}': {frappe.get_traceback()}", "Snapshot Processing")

    log = sorted(grouped.values(), key=lambda x: x["unix_ts"])
    return log


def format_rel_ts(unix_ts, start_time):
    if not start_time:
        return ""
    try:
        _sys_tz = pytz.timezone(frappe.utils.get_system_timezone())
        start_unix = _sys_tz.localize(start_time).timestamp()
        total_seconds = int(unix_ts - start_unix)
        if total_seconds < 0:
            total_seconds = 0
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}"
    except Exception:
        return ""


def _download_s3_key(s3_client, bucket, key):
    """Download a single S3 object by key and return a base64 data URI, or None on failure."""
    if not key:
        return None
    try:
        obj = s3_client.get_object(Bucket=bucket, Key=key)
        img_bytes = obj['Body'].read()
        b64 = base64.b64encode(img_bytes).decode('utf-8')
        return f"data:image/jpeg;base64,{b64}"
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"S3 direct key download failed: {key}")
        return None


def get_base64_image(file_url):
    if not file_url:
        return None
    from exampro.exam_pro.doctype.exam_submission.exam_submission import convert_image_to_base64
    b64 = convert_image_to_base64(file_url)
    if b64:
        if not b64.startswith("data:"):
            return f"data:image/jpeg;base64,{b64}"
        return b64
    return None