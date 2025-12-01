app_name = "sites_setup"
app_title = "Sites Setup"
app_publisher = "Elphas Masuka"
app_description = "This is an app to setup erpnext sites in a server"
app_email = "masukaeliphas34@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
add_to_apps_screen = [
	{
		"name": "sites_setup",
		"logo": "/assets/sites_setup/logo.png",
		"title": "Sites Setup",
		"route": "/app/site-provisioning",
	}
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/sites_setup/css/sites_setup.css"
# app_include_js = "/assets/sites_setup/js/sites_setup.js"

# include js, css files in header of web template
# web_include_css = "/assets/sites_setup/css/sites_setup.css"
# web_include_js = "/assets/sites_setup/js/sites_setup.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "sites_setup/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {"Site Provisioning" : "public/js/site_provisioning.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "sites_setup/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Website Route Rules
website_route_rules = [
	{"from_route": "/my-sites", "to_route": "my_sites"},
]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "sites_setup.utils.jinja_methods",
# 	"filters": "sites_setup.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "sites_setup.install.before_install"
# after_install = "sites_setup.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "sites_setup.uninstall.before_uninstall"
# after_uninstall = "sites_setup.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "sites_setup.utils.before_app_install"
# after_app_install = "sites_setup.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "sites_setup.utils.before_app_uninstall"
# after_app_uninstall = "sites_setup.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "sites_setup.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
	"Site Provisioning": "sites_setup.sites_setup.doctype.site_provisioning.site_provisioning_permissions.get_permission_query_conditions",
}

has_permission = {
	"Site Provisioning": "sites_setup.sites_setup.doctype.site_provisioning.site_provisioning_permissions.has_permission",
}

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"sites_setup.tasks.all"
# 	],
# 	"daily": [
# 		"sites_setup.tasks.daily"
# 	],
# 	"hourly": [
# 		"sites_setup.tasks.hourly"
# 	],
# 	"weekly": [
# 		"sites_setup.tasks.weekly"
# 	],
# 	"monthly": [
# 		"sites_setup.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "sites_setup.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "sites_setup.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "sites_setup.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["sites_setup.utils.before_request"]
# after_request = ["sites_setup.utils.after_request"]

# Job Events
# ----------
# before_job = ["sites_setup.utils.before_job"]
# after_job = ["sites_setup.utils.after_job"]

# User Data Protection
# --------------------

user_data_fields = [
	{
		"doctype": "Site Provisioning",
		"filter_by": "requested_by",
		"partial": 1,
	},
]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"sites_setup.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }
