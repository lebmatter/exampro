import frappe


def get_context(context):
	context.no_cache = 1

	short_uuid = frappe.form_dict.get("short_uuid", "")
	is_host = frappe.request.path.rstrip("/").endswith("/host")
	is_preview = frappe.form_dict.get("preview") == "1"

	context.short_uuid = short_uuid
	context.is_host = is_host
	context.is_preview = is_preview

	if is_host:
		if "Exam Manager" not in frappe.get_roles():
			frappe.throw("Not authorized", frappe.PermissionError)
