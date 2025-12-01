import frappe
from frappe import _


@frappe.whitelist()
def provision_site(subdomain, admin_password):
    """
    API endpoint to provision a new site with a custom domain.
    Provisioning starts automatically after creation.

    Args:
        subdomain: The subdomain to provision (e.g., "mycompany" - will become mycompany.havano.cloud)
        admin_password: The admin password to set for the site

    Returns:
        dict: Contains provisioning_id, status, and message
    """
    # Create provisioning record (validation happens in the DocType)
    # Provisioning starts automatically in after_insert hook
    provisioning = frappe.get_doc(
        {
            "doctype": "Site Provisioning",
            "requested_subdomain": subdomain,
            "admin_password": admin_password,
        }
    )
    provisioning.insert()
    frappe.db.commit()

    # Reload to get the updated status (Running after auto-start)
    provisioning.reload()

    return {
        "success": True,
        "provisioning_id": provisioning.name,
        "status": provisioning.status,
        "requested_subdomain": provisioning.requested_subdomain,
        "assigned_site": provisioning.assigned_site,
        "server_ip": provisioning.server_ip,
        "message": _("Provisioning started automatically. Check status for progress."),
    }


@frappe.whitelist()
def retry_provisioning(provisioning_id):
    """
    Retry provisioning for a failed request.

    Args:
        provisioning_id: The ID of the provisioning request

    Returns:
        dict: Contains status and message
    """
    provisioning = frappe.get_doc("Site Provisioning", provisioning_id)

    # Check permissions
    if (
        provisioning.requested_by != frappe.session.user
        and "System Manager" not in frappe.get_roles()
    ):
        frappe.throw(_("You don't have permission to retry this provisioning"), frappe.PermissionError)

    return provisioning.start_provisioning()


@frappe.whitelist()
def get_provisioning_status(provisioning_id):
    """
    Get the status of a provisioning request.

    Args:
        provisioning_id: The ID of the provisioning request

    Returns:
        dict: Contains status, error_message, and other details
    """
    provisioning = frappe.get_doc("Site Provisioning", provisioning_id)

    # Check permissions - user can only see their own provisionings unless System Manager
    if (
        provisioning.requested_by != frappe.session.user
        and "System Manager" not in frappe.get_roles()
    ):
        frappe.throw(_("You don't have permission to view this provisioning"), frappe.PermissionError)

    return {
        "provisioning_id": provisioning.name,
        "status": provisioning.status,
        "requested_subdomain": provisioning.requested_subdomain,
        "assigned_site": provisioning.assigned_site,
        "server_ip": provisioning.server_ip,
        "server_port": provisioning.server_port,
        "bench_directory": provisioning.bench_directory,
        "domain_created": provisioning.domain_created,
        "admin_password_set": provisioning.admin_password_set,
        "error_message": provisioning.error_message,
        "created_at": str(provisioning.creation),
        "updated_at": str(provisioning.modified),
    }


@frappe.whitelist()
def get_my_provisionings():
    """
    Get all provisioning requests for the current user.

    Returns:
        list: List of provisioning records
    """
    provisionings = frappe.get_all(
        "Site Provisioning",
        filters={"requested_by": frappe.session.user},
        fields=[
            "name",
            "requested_subdomain",
            "assigned_site",
            "status",
            "server_ip",
            "domain_created",
            "admin_password_set",
            "error_message",
            "creation",
            "modified",
        ],
        order_by="creation desc",
    )

    return provisionings


@frappe.whitelist()
def get_provisionings_by_server(server_ip=None):
    """
    Get all provisioning requests filtered by server IP.
    Only available to System Managers.

    Args:
        server_ip: Optional server IP to filter by

    Returns:
        list: List of provisioning records
    """
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Only System Managers can view provisionings by server"), frappe.PermissionError)

    filters = {}
    if server_ip:
        filters["server_ip"] = server_ip

    provisionings = frappe.get_all(
        "Site Provisioning",
        filters=filters,
        fields=[
            "name",
            "requested_subdomain",
            "assigned_site",
            "status",
            "server_ip",
            "server_port",
            "bench_directory",
            "domain_created",
            "admin_password_set",
            "requested_by",
            "creation",
        ],
        order_by="server_ip, creation desc",
    )

    return provisionings


@frappe.whitelist()
def get_server_summary():
    """
    Get a summary of domains per server.
    Only available to System Managers.

    Returns:
        list: List of servers with domain counts
    """
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Only System Managers can view server summary"), frappe.PermissionError)

    # Get count of domains per server
    result = frappe.db.sql("""
        SELECT
            server_ip,
            server_port,
            bench_directory,
            COUNT(*) as total_domains,
            SUM(CASE WHEN status = 'Success' THEN 1 ELSE 0 END) as successful,
            SUM(CASE WHEN status = 'Failed' THEN 1 ELSE 0 END) as failed,
            SUM(CASE WHEN status = 'Running' THEN 1 ELSE 0 END) as running,
            SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) as pending
        FROM `tabSite Provisioning`
        WHERE server_ip IS NOT NULL
        GROUP BY server_ip, server_port, bench_directory
        ORDER BY server_ip
    """, as_dict=True)

    return result


@frappe.whitelist()
def check_subdomain_availability(subdomain):
    """
    Check if a subdomain is available.

    Args:
        subdomain: The subdomain to check (with or without .havano.cloud)

    Returns:
        dict: Contains available (bool) and message
    """
    settings = frappe.get_single("Sites Setup Settings")
    domain = settings.site_domain

    # Normalize subdomain - remove domain if present, then add it back
    subdomain = subdomain.lower().strip()
    if subdomain.endswith(f".{domain}"):
        subdomain = subdomain.replace(f".{domain}", "")

    full_subdomain = f"{subdomain}.{domain}"

    # Check if exists
    exists = frappe.db.exists("Site Provisioning", {"requested_subdomain": full_subdomain})

    return {
        "subdomain": full_subdomain,
        "available": not exists,
        "message": _("Subdomain is available") if not exists else _("Subdomain is already taken"),
    }


@frappe.whitelist()
def test_ssh_connection():
    """
    Test the SSH connection to the ERP server.
    Only available to System Managers.

    Returns:
        dict: Contains success (bool), message, and bench_version if successful
    """
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Only System Managers can test SSH connection"), frappe.PermissionError)

    from sites_setup.sites_setup.ssh_service import ERPSshService

    service = ERPSshService()
    result = service.test_connection()
    service.disconnect()

    return result


# Public API for external access (no login required)
@frappe.whitelist(allow_guest=True)
def public_provision_site(subdomain, admin_password, api_key=None, api_secret=None):
    """
    Public API endpoint to provision a new site.
    Requires API key/secret for authentication.
    Provisioning starts automatically.

    Args:
        subdomain: The subdomain to provision (e.g., "mycompany")
        admin_password: The admin password to set
        api_key: API key for authentication
        api_secret: API secret for authentication

    Returns:
        dict: Contains provisioning_id, status, and message
    """
    # Authenticate with API key if provided
    if api_key and api_secret:
        user = frappe.db.get_value("User", {"api_key": api_key}, "name")
        if user:
            user_doc = frappe.get_doc("User", user)
            if user_doc.get_password("api_secret") == api_secret:
                frappe.set_user(user)
            else:
                frappe.throw(_("Invalid API credentials"), frappe.AuthenticationError)
        else:
            frappe.throw(_("Invalid API credentials"), frappe.AuthenticationError)
    else:
        frappe.throw(_("API key and secret are required"), frappe.AuthenticationError)

    return provision_site(subdomain, admin_password)


@frappe.whitelist(allow_guest=True)
def public_get_status(provisioning_id, api_key=None, api_secret=None):
    """
    Public API endpoint to get provisioning status.
    Requires API key/secret for authentication.

    Args:
        provisioning_id: The ID of the provisioning request
        api_key: API key for authentication
        api_secret: API secret for authentication

    Returns:
        dict: Contains status and details
    """
    # Authenticate with API key if provided
    if api_key and api_secret:
        user = frappe.db.get_value("User", {"api_key": api_key}, "name")
        if user:
            user_doc = frappe.get_doc("User", user)
            if user_doc.get_password("api_secret") == api_secret:
                frappe.set_user(user)
            else:
                frappe.throw(_("Invalid API credentials"), frappe.AuthenticationError)
        else:
            frappe.throw(_("Invalid API credentials"), frappe.AuthenticationError)
    else:
        frappe.throw(_("API key and secret are required"), frappe.AuthenticationError)

    return get_provisioning_status(provisioning_id)
