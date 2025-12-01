import frappe


def get_context(context):
    """Get context for my sites page"""
    if frappe.session.user == "Guest":
        frappe.throw("Please login to view your sites", frappe.PermissionError)

    context.no_cache = 1

    provisionings = frappe.get_all(
        "Site Provisioning",
        filters={"requested_by": frappe.session.user},
        fields=[
            "name",
            "requested_subdomain",
            "assigned_site",
            "status",
            "error_message",
            "creation",
        ],
        order_by="creation desc",
    )

    context.provisionings = provisionings
    context.has_pending = any(p.status in ["Pending", "Running"] for p in provisionings)

    return context
