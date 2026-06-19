import frappe


def get_context(context):
	context.no_cache = 1

	short_uuid = frappe.form_dict.get("short_uuid", "")
	is_host = frappe.request.path.rstrip("/").endswith("/host")

	context.short_uuid = short_uuid
	context.is_host = is_host

	if is_host:
		if "Exam Manager" not in frappe.get_roles():
			frappe.throw("Not authorized", frappe.PermissionError)
