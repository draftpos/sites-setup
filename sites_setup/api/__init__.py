import frappe
from frappe import _


@frappe.whitelist()
def provision_site(
    subdomain=None,
    admin_password=None,
    first_name=None,
    middle_name=None,
    last_name=None,
    email=None,
    phone=None,
    company_name=None,
    industry=None,
    address=None,
    city=None,
    country=None,
    assigned_site=None,
):
    """
    API endpoint to provision a new site with a custom domain.
    Provisioning starts automatically after creation.

    Args:
        subdomain: The subdomain to provision (optional if company_name provided)
        admin_password: The admin password to set for the site (required)
        first_name: User's first name
        middle_name: User's middle name
        last_name: User's last name
        email: User's email address
        phone: User's phone number
        company_name: Company name (can be used to auto-generate subdomain)
        industry: Company industry
        address: Company address
        city: Company city
        country: Company country
        assigned_site: Specific site to assign (System Manager only)

    Returns:
        dict: Contains provisioning_id, status, site_url, and message
    """
    if not admin_password:
        frappe.throw(_("Admin password is required"))

    # Create provisioning record (validation happens in the DocType)
    # Provisioning starts automatically in after_insert hook
    doc_data = {
        "doctype": "Site Provisioning",
        "admin_password": admin_password,
    }

    # Add optional fields if provided
    if subdomain:
        doc_data["requested_subdomain"] = subdomain
    if first_name:
        doc_data["first_name"] = first_name
    if middle_name:
        doc_data["middle_name"] = middle_name
    if last_name:
        doc_data["last_name"] = last_name
    if email:
        doc_data["email"] = email
    if phone:
        doc_data["phone"] = phone
    if company_name:
        doc_data["company_name"] = company_name
    if industry:
        doc_data["industry"] = industry
    if address:
        doc_data["address"] = address
    if city:
        doc_data["city"] = city
    if country:
        doc_data["country"] = country
    if assigned_site:
        doc_data["assigned_site"] = assigned_site

    provisioning = frappe.get_doc(doc_data)
    provisioning.insert()
    frappe.db.commit()

    # Reload to get the updated status (Running after auto-start)
    provisioning.reload()

    # Build the site URL
    site_url = f"https://{provisioning.requested_subdomain}"

    return {
        "success": True,
        "provisioning_id": provisioning.name,
        "status": provisioning.status,
        "site_url": site_url,
        "requested_subdomain": provisioning.requested_subdomain,
        "assigned_site": provisioning.assigned_site,
        "server_ip": provisioning.server_ip,
        "message": _("Provisioning started automatically. Your site URL: {0}").format(site_url),
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
def get_sites_stats():
    """
    Get statistics about site assignments.
    Returns total sites, assigned count, and unassigned count.

    Returns:
        dict: Contains total_sites, assigned_count, unassigned_count
    """
    from sites_setup.sites_setup.doctype.site_provisioning.site_provisioning import get_sites_stats as _get_sites_stats

    return _get_sites_stats()


@frappe.whitelist()
def get_unassigned_sites():
    """
    Get list of unassigned sites from the pool.
    Only available to System Managers.

    Returns:
        list: List of unassigned site names
    """
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Only System Managers can view unassigned sites"), frappe.PermissionError)

    from sites_setup.sites_setup.doctype.site_provisioning.site_provisioning import get_unassigned_sites as _get_unassigned_sites

    return _get_unassigned_sites()


@frappe.whitelist()
def unassign_site(provisioning_id, backup=True):
    """
    Unassign a site and optionally create a backup.
    Only available to System Managers.

    Args:
        provisioning_id: The ID of the provisioning request
        backup: Whether to backup the site before unassigning (default True)

    Returns:
        dict: Contains message about the unassignment process
    """
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Only System Managers can unassign sites"), frappe.PermissionError)

    provisioning = frappe.get_doc("Site Provisioning", provisioning_id)
    return provisioning.unassign_site(backup=backup)


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


@frappe.whitelist()
def run_site_migrate(provisioning_id):
    """
    Run bench migrate on a provisioned site.
    Available to site owner and System Managers.
    Runs asynchronously as a background job.

    Args:
        provisioning_id: The ID of the provisioning request

    Returns:
        dict: Contains message about the operation
    """
    provisioning = frappe.get_doc("Site Provisioning", provisioning_id)

    # Check permissions
    if (
        provisioning.requested_by != frappe.session.user
        and "System Manager" not in frappe.get_roles()
    ):
        frappe.throw(_("You don't have permission to run migrate on this site"), frappe.PermissionError)

    # Only allow for successful provisionings
    if provisioning.status != "Success":
        frappe.throw(_("Migrate can only be run on successfully provisioned sites"), frappe.ValidationError)

    # Check if app operation is running
    if provisioning.app_operation_status == "Running":
        frappe.throw(_("Cannot run migrate while an app operation is in progress"), frappe.ValidationError)

    # Enqueue background job
    frappe.enqueue(
        "sites_setup.sites_setup.doctype.site_provisioning.site_provisioning.run_migrate_job",
        queue="long",
        timeout=600,
        provisioning_name=provisioning_id,
    )

    # Update status to show migration is running
    provisioning.db_set("app_operation_status", "Running")
    provisioning.db_set("app_operation_log", "Starting bench migrate...")
    frappe.db.commit()

    return {
        "success": True,
        "message": _("Migration started. This may take several minutes."),
    }


# Public Registration API (no login required)
@frappe.whitelist(allow_guest=True)
def register(
    email=None,
    password=None,
    subdomain=None,
    first_name=None,
    middle_name=None,
    last_name=None,
    phone=None,
    company_name=None,
    industry=None,
    address=None,
    city=None,
    country=None,
):
    """
    Public registration API endpoint to provision a new ERPNext site.
    No authentication required - this is for new user registration.
    The password provided will be set as the admin password for the new site.

    Args:
        email: User's email address (required)
        password: Password for the site admin account (required)
        subdomain: The subdomain to provision (optional if company_name provided)
        first_name: User's first name
        middle_name: User's middle name
        last_name: User's last name
        phone: User's phone number
        company_name: Company name (can be used to auto-generate subdomain)
        industry: Company industry
        address: Company address
        city: Company city
        country: Company country

    Returns:
        dict: Contains provisioning_id, status, site_url, and message
    """
    # Validate required fields
    if not email:
        frappe.throw(_("Email is required"), frappe.ValidationError)

    if not password:
        frappe.throw(_("Password is required"), frappe.ValidationError)

    # Validate email format
    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        frappe.throw(_("Invalid email format"), frappe.ValidationError)

    # Set user context to Administrator for creating the provisioning record
    frappe.set_user("Administrator")

    # Create provisioning record
    doc_data = {
        "doctype": "Site Provisioning",
        "admin_password": password,
        "email": email,
    }

    # Add optional fields if provided
    if subdomain:
        doc_data["requested_subdomain"] = subdomain
    if first_name:
        doc_data["first_name"] = first_name
    if middle_name:
        doc_data["middle_name"] = middle_name
    if last_name:
        doc_data["last_name"] = last_name
    if phone:
        doc_data["phone"] = phone
    if company_name:
        doc_data["company_name"] = company_name
    if industry:
        doc_data["industry"] = industry
    if address:
        doc_data["address"] = address
    if city:
        doc_data["city"] = city
    if country:
        doc_data["country"] = country

    provisioning = frappe.get_doc(doc_data)
    provisioning.insert(ignore_permissions=True)
    frappe.db.commit()

    # Reload to get the updated status (Running after auto-start)
    provisioning.reload()

    # Build the site URL
    site_url = f"https://{provisioning.requested_subdomain}"

    return {
        "success": True,
        "provisioning_id": provisioning.name,
        "status": provisioning.status,
        "site_url": site_url,
        "requested_subdomain": provisioning.requested_subdomain,
        "assigned_site": provisioning.assigned_site,
        "message": _("Registration successful! Your site is being provisioned. Site URL: {0}").format(site_url),
    }


@frappe.whitelist()
def get_bench_apps():
    """
    Get all apps available in the bench.
    Only available to System Managers.

    Returns:
        dict: Contains list of app names available in the bench
    """
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Only System Managers can view bench apps"), frappe.PermissionError)

    from sites_setup.sites_setup.ssh_service import ERPSshService

    service = ERPSshService()
    try:
        result = service.get_bench_apps()
        return result
    finally:
        service.disconnect()


@frappe.whitelist()
def get_site_apps(provisioning_id):
    """
    Get apps installed on a provisioned site.
    Available to site owner and System Managers.

    Args:
        provisioning_id: The ID of the provisioning request

    Returns:
        dict: Contains list of installed apps and list of available apps
    """
    provisioning = frappe.get_doc("Site Provisioning", provisioning_id)

    # Check permissions - user can only see their own provisionings unless System Manager
    if (
        provisioning.requested_by != frappe.session.user
        and "System Manager" not in frappe.get_roles()
    ):
        frappe.throw(_("You don't have permission to view this site's apps"), frappe.PermissionError)

    # Only allow for successful provisionings
    if provisioning.status != "Success":
        frappe.throw(_("Apps can only be managed for successfully provisioned sites"), frappe.ValidationError)

    # Check if app operation is running
    if provisioning.app_operation_status == "Running":
        frappe.throw(_("An app operation is currently in progress"), frappe.ValidationError)

    from sites_setup.sites_setup.ssh_service import ERPSshService

    service = ERPSshService()
    try:
        # Get installed apps on the site
        site_result = service.get_site_apps(provisioning.assigned_site)
        installed_apps = site_result.get("apps", [])

        # Get all available apps in the bench
        bench_result = service.get_bench_apps()
        available_apps = bench_result.get("apps", [])

        return {
            "success": True,
            "installed_apps": installed_apps,
            "available_apps": available_apps,
            "app_operation_status": provisioning.app_operation_status or "Idle"
        }
    finally:
        service.disconnect()


@frappe.whitelist()
def manage_site_apps(provisioning_id, apps_to_install=None, apps_to_uninstall=None):
    """
    Install or uninstall apps on a provisioned site.
    Available to site owner and System Managers.
    Runs asynchronously as a background job.

    Args:
        provisioning_id: The ID of the provisioning request
        apps_to_install: JSON list of app names to install
        apps_to_uninstall: JSON list of app names to uninstall

    Returns:
        dict: Contains message about the operation
    """
    import json

    provisioning = frappe.get_doc("Site Provisioning", provisioning_id)

    # Check permissions
    if (
        provisioning.requested_by != frappe.session.user
        and "System Manager" not in frappe.get_roles()
    ):
        frappe.throw(_("You don't have permission to manage this site's apps"), frappe.PermissionError)

    # Only allow for successful provisionings
    if provisioning.status != "Success":
        frappe.throw(_("Apps can only be managed for successfully provisioned sites"), frappe.ValidationError)

    # Check if app operation is already running
    if provisioning.app_operation_status == "Running":
        frappe.throw(_("An app operation is already in progress. Please wait for it to complete."), frappe.ValidationError)

    # Parse JSON if strings provided
    if isinstance(apps_to_install, str):
        apps_to_install = json.loads(apps_to_install) if apps_to_install else []
    if isinstance(apps_to_uninstall, str):
        apps_to_uninstall = json.loads(apps_to_uninstall) if apps_to_uninstall else []

    apps_to_install = apps_to_install or []
    apps_to_uninstall = apps_to_uninstall or []

    # Validate - cannot uninstall core apps
    core_apps = ["frappe", "erpnext"]
    for app in apps_to_uninstall:
        if app in core_apps:
            frappe.throw(_("Cannot uninstall core app: {0}").format(app), frappe.ValidationError)

    if not apps_to_install and not apps_to_uninstall:
        frappe.throw(_("No apps specified to install or uninstall"), frappe.ValidationError)

    # Update status to Running
    provisioning.db_set("app_operation_status", "Running")
    provisioning.db_set("app_operation_log", "")
    frappe.db.commit()

    # Enqueue background job
    frappe.enqueue(
        "sites_setup.sites_setup.doctype.site_provisioning.site_provisioning.run_app_management",
        queue="long",
        timeout=600 * max(len(apps_to_install) + len(apps_to_uninstall), 1),  # 10 min per app
        provisioning_name=provisioning_id,
        apps_to_install=apps_to_install,
        apps_to_uninstall=apps_to_uninstall,
    )

    return {
        "success": True,
        "message": _("App management started. Installing {0} app(s), uninstalling {1} app(s).").format(
            len(apps_to_install), len(apps_to_uninstall)
        ),
        "apps_to_install": apps_to_install,
        "apps_to_uninstall": apps_to_uninstall,
    }


@frappe.whitelist()
def get_app_operation_status(provisioning_id):
    """
    Get the current app operation status for a provisioned site.

    Args:
        provisioning_id: The ID of the provisioning request

    Returns:
        dict: Contains app_operation_status and app_operation_log
    """
    provisioning = frappe.get_doc("Site Provisioning", provisioning_id)

    # Check permissions
    if (
        provisioning.requested_by != frappe.session.user
        and "System Manager" not in frappe.get_roles()
    ):
        frappe.throw(_("You don't have permission to view this site"), frappe.PermissionError)

    return {
        "app_operation_status": provisioning.app_operation_status or "Idle",
        "app_operation_log": provisioning.app_operation_log or "",
    }


@frappe.whitelist(allow_guest=True)
def get_status(provisioning_id=None, email=None):
    """
    Public API endpoint to get provisioning status.
    Can lookup by provisioning_id or email.

    Args:
        provisioning_id: The ID of the provisioning request
        email: Email used during registration (returns latest provisioning for this email)

    Returns:
        dict: Contains status and details
    """
    if not provisioning_id and not email:
        frappe.throw(_("Either provisioning_id or email is required"), frappe.ValidationError)

    if provisioning_id:
        # Direct lookup by ID
        if not frappe.db.exists("Site Provisioning", provisioning_id):
            frappe.throw(_("Provisioning record not found"), frappe.DoesNotExistError)

        provisioning = frappe.get_doc("Site Provisioning", provisioning_id)
    else:
        # Lookup by email - get the latest one
        provisioning_name = frappe.db.get_value(
            "Site Provisioning",
            {"email": email},
            "name",
            order_by="creation desc"
        )
        if not provisioning_name:
            frappe.throw(_("No provisioning record found for this email"), frappe.DoesNotExistError)

        provisioning = frappe.get_doc("Site Provisioning", provisioning_name)

    site_url = f"https://{provisioning.requested_subdomain}"

    return {
        "provisioning_id": provisioning.name,
        "status": provisioning.status,
        "site_url": site_url,
        "requested_subdomain": provisioning.requested_subdomain,
        "assigned_site": provisioning.assigned_site,
        "domain_created": provisioning.domain_created,
        "admin_password_set": provisioning.admin_password_set,
        "error_message": provisioning.error_message,
        "created_at": str(provisioning.creation),
        "updated_at": str(provisioning.modified),
    }
