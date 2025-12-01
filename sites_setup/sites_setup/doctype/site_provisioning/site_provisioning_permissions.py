import frappe


def get_permission_query_conditions(user):
    """
    Return SQL conditions for filtering Site Provisioning records.
    Users can only see their own provisionings unless they are System Manager.
    """
    if not user:
        user = frappe.session.user

    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        return ""

    return f"(`tabSite Provisioning`.requested_by = {frappe.db.escape(user)})"


def has_permission(doc, ptype, user):
    """
    Check if user has permission to access the Site Provisioning document.
    Users can only access their own provisionings unless they are System Manager.
    """
    if not user:
        user = frappe.session.user

    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        return True

    return doc.requested_by == user
