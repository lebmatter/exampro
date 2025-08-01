app_name = "exampro"
app_title = "Exam Pro"
app_publisher = "Labeeb Mattra"
app_description = "Proctored Exams for Frappe Framework"
app_email = "labeeb@zerodha.com"
app_license = "mit"
# required_apps = []

# App startup hooks
# on_app_init = ["exampro.exam_pro.doctype.exam_submission.exam_submission.rebuild_exam_trackers"]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/exampro/css/exampro.css"
# app_include_js = "/assets/exampro/js/exampro.js"

# include js, css files in header of web template
# web_include_css = "/assets/exampro/css/exampro.css"
# web_include_js = "/assets/exampro/js/exampro.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "exampro/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "exampro/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }
website_user_home_page = "/my-exams"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
#	"methods": "exampro.utils.jinja_methods",
#	"filters": "exampro.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "exampro.install.before_install"
after_install = "exampro.exam_pro.api.utils.create_sample_exams"


# Uninstallation
# ------------

# before_uninstall = "exampro.uninstall.before_uninstall"
# after_uninstall = "exampro.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "exampro.utils.before_app_install"
# after_app_install = "exampro.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "exampro.utils.before_app_uninstall"
# after_app_uninstall = "exampro.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "exampro.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
#	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
#	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
#	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
#	"*": {
#		"on_update": "method",
#		"on_cancel": "method",
#		"on_trash": "method"
#	}
# }

doc_events = {
    "User": {
        "before_insert": "exampro.exam_pro.api.utils.validate_user_email"
    }
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
#	"all": [
#		"exampro.tasks.all"
#	],
#	"daily": [
#		"exampro.tasks.daily"
#	],
#	"hourly": [
#		"exampro.tasks.hourly"
#	],
#	"weekly": [
#		"exampro.tasks.weekly"
#	],
#	"monthly": [
#		"exampro.tasks.monthly"
#	],
# }

# Testing
# -------

# before_tests = "exampro.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
#	"frappe.desk.doctype.event.event.get_events": "exampro.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
#	"Task": "exampro.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["exampro.utils.before_request"]
after_request = ["exampro.exam_pro.api.utils.cleanup_request"]

# Job Events
# ----------
# before_job = ["exampro.utils.before_job"]
# after_job = ["exampro.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
#	{
#		"doctype": "{doctype_1}",
#		"filter_by": "{filter_by}",
#		"redact_fields": ["{field_1}", "{field_2}"],
#		"partial": 1,
#	},
#	{
#		"doctype": "{doctype_2}",
#		"filter_by": "{filter_by}",
#		"partial": 1,
#	},
#	{
#		"doctype": "{doctype_3}",
#		"strict": False,
#	},
#	{
#		"doctype": "{doctype_4}"
#	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
#	"exampro.auth.validate"
# ]

website_route_rules = [
    {"from_route": "/exam/<exam_submission>", "to_route": "exam/result"},
    {"from_route": "/manage", "to_route": "manage/users"},
    {"from_route": "/exam/invite/<invite_code>", "to_route": "exam/invite"},
    {"from_route": "/leaderboard/<submission>", "to_route": "leaderboard"}
]

fixtures = [
    {
        "dt": "Role",
        "filters": [
            ["name", "in", ["Exam Candidate", "Exam Proctor", "Exam Evaluator", "Exam Manager"]]
        ]
    },
    {
        "dt": "Email Template"
    }
]

update_website_context = ["exampro.exam_pro.api.utils.get_website_context"]
