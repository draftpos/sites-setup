# Copyright (c) 2024, Havano and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class AvailableSite(Document):
    pass


def sync_available_sites():
    """
    Sync Available Site records based on Sites Setup Settings.
    Creates new sites, removes sites outside range, and updates status based on provisioning.
    """
    settings = frappe.get_single("Sites Setup Settings")

    site_min = settings.site_min
    site_max = settings.site_max
    prefix = settings.site_prefix
    domain = settings.site_domain

    if not all([site_min, site_max, prefix, domain]):
        frappe.msgprint(_("Please configure site range in Sites Setup Settings first"))
        return

    # Get expected site names
    expected_sites = set()
    for i in range(site_min, site_max + 1):
        expected_sites.add(f"{prefix}{i}.{domain}")

    # Get existing Available Site records
    existing_sites = set(frappe.get_all("Available Site", pluck="name"))

    # Get assigned sites from Site Provisioning (active, not unassigned)
    assigned_sites = {}
    provisioning_records = frappe.get_all(
        "Site Provisioning",
        filters={"assigned_site": ("is", "set"), "is_unassigned": 0},
        fields=["name", "assigned_site"]
    )
    for p in provisioning_records:
        assigned_sites[p.assigned_site] = p.name

    # Sites to add
    sites_to_add = expected_sites - existing_sites
    for site_name in sites_to_add:
        status = "Assigned" if site_name in assigned_sites else "Available"
        provisioning = assigned_sites.get(site_name)

        doc = frappe.get_doc({
            "doctype": "Available Site",
            "site_name": site_name,
            "status": status,
            "provisioning": provisioning
        })
        doc.insert(ignore_permissions=True)

    # Sites to remove (outside current range)
    sites_to_remove = existing_sites - expected_sites
    for site_name in sites_to_remove:
        frappe.delete_doc("Available Site", site_name, ignore_permissions=True)

    # Update status of existing sites
    for site_name in existing_sites & expected_sites:
        site = frappe.get_doc("Available Site", site_name)
        new_status = "Assigned" if site_name in assigned_sites else "Available"
        new_provisioning = assigned_sites.get(site_name)

        if site.status != new_status or site.provisioning != new_provisioning:
            site.status = new_status
            site.provisioning = new_provisioning
            site.save(ignore_permissions=True)

    frappe.db.commit()

    return {
        "added": len(sites_to_add),
        "removed": len(sites_to_remove),
        "total": len(expected_sites)
    }


def mark_site_assigned(site_name, provisioning_name):
    """Mark a site as assigned when provisioning is created"""
    if frappe.db.exists("Available Site", site_name):
        frappe.db.set_value("Available Site", site_name, {
            "status": "Assigned",
            "provisioning": provisioning_name
        })
    else:
        # Create the record if it doesn't exist
        doc = frappe.get_doc({
            "doctype": "Available Site",
            "site_name": site_name,
            "status": "Assigned",
            "provisioning": provisioning_name
        })
        doc.insert(ignore_permissions=True)


def mark_site_available(site_name):
    """Mark a site as available when provisioning is unassigned"""
    if frappe.db.exists("Available Site", site_name):
        frappe.db.set_value("Available Site", site_name, {
            "status": "Available",
            "provisioning": None
        })


@frappe.whitelist()
def sync_sites():
    """API endpoint to sync available sites"""
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Only System Managers can sync sites"), frappe.PermissionError)

    result = sync_available_sites()
    frappe.msgprint(
        _("Sites synced: {0} added, {1} removed, {2} total").format(
            result["added"], result["removed"], result["total"]
        )
    )
    return result
