import frappe
from frappe import _
import re


def validate(doc, method=None):
    """Validate the web form submission"""
    admin_password = frappe.form_dict.get("admin_password")

    if not admin_password or len(admin_password) < 8:
        frappe.throw(_("Admin password must be at least 8 characters long"))

    # Validate password complexity
    password_pattern = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]"
    if not re.match(password_pattern, admin_password):
        frappe.throw(
            _(
                "Password must contain at least one uppercase letter, "
                "one lowercase letter, one number, and one special character (@$!%*?&)"
            )
        )


def get_context(context):
    """Add context for the web form"""
    settings = frappe.get_single("Sites Setup Settings")
    context.domain = settings.site_domain
    return context
