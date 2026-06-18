import frappe
from frappe import _


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    if "Exam Manager" not in frappe.get_roles():
        raise frappe.PermissionError(_("You are not authorized to access this page"))

    context.no_cache = 1

    settings = frappe.get_single("Exam Settings")
    context.ai_configured = bool(settings.openrouter_api_key)
