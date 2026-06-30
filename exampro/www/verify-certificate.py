import frappe
from frappe.utils import format_date, now_datetime


def get_context(context):
    context.no_cache = 1
    context.is_guest = frappe.session.user == "Guest"
    context.title = "Verify Certificate"


@frappe.whitelist(allow_guest=False)
def verify_certificate(cert_id):
    cert_id = (cert_id or "").strip()
    if not cert_id:
        frappe.throw("Certificate ID is required.", frappe.ValidationError)

    try:
        cert = frappe.get_doc("Exam Certificate", cert_id, ignore_permissions=True)
    except frappe.DoesNotExistError:
        _log_request(cert_id, "Not Found")
        return {"found": False, "error": f"No certificate found with ID \"{cert_id}\"."}

    exam = frappe.get_doc("Exam", cert.exam, ignore_permissions=True)

    is_expired = bool(cert.expiry_date and cert.expiry_date < frappe.utils.nowdate())
    result = "Expired" if is_expired else "Valid"

    _log_request(
        cert_id, result,
        candidate_name=cert.candidate_name,
        exam_title=exam.title,
        issue_date=cert.issue_date,
        expiry_date=cert.expiry_date,
    )

    partner_logo = None
    partner_name = None
    if exam.partner:
        partner_logo = frappe.db.get_value("Exam Partner", exam.partner, "logo")
        partner_name = exam.partner

    return {
        "found": True,
        "id": cert.name,
        "candidate_name": cert.candidate_name,
        "exam_title": exam.title,
        "issue_date": format_date(cert.issue_date, "dd MMM yyyy") if cert.issue_date else None,
        "expiry_date": format_date(cert.expiry_date, "dd MMM yyyy") if cert.expiry_date else None,
        "is_expired": is_expired,
        "partner_name": partner_name,
        "partner_logo": partner_logo,
    }


def _log_request(cert_id, result, candidate_name=None, exam_title=None, issue_date=None, expiry_date=None):
    try:
        doc = frappe.get_doc({
            "doctype": "Certificate Verification Request",
            "certificate_id": cert_id,
            "verified_by": frappe.session.user,
            "verification_time": now_datetime(),
            "result": result,
            "ip_address": frappe.local.request.environ.get("REMOTE_ADDR") if frappe.local.request else None,
            "candidate_name": candidate_name,
            "exam_title": exam_title,
            "issue_date": issue_date,
            "expiry_date": expiry_date,
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        pass
