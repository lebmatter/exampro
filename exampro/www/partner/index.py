import frappe

from exampro.exam_pro.api.utils import get_current_user_partner


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login"
		raise frappe.Redirect

	frappe.local.flags.redirect_location = "/exam-studio"
	raise frappe.Redirect
