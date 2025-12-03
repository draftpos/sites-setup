# Copyright (c) 2024, Havano and contributors
# For license information, please see license.txt

import json
import frappe
from frappe.model.document import Document


class AvailableSite(Document):
    @staticmethod
    def get_list(filters=None, fields=None, order_by=None, start=0, page_length=20, **kwargs):
        """Get list of all sites (available and assigned) for the virtual doctype"""

        settings = frappe.get_single("Sites Setup Settings")

        site_min = settings.site_min
        site_max = settings.site_max
        prefix = settings.site_prefix
        domain = settings.site_domain

        if not all([site_min, site_max, prefix, domain]):
            return []

        # Get all assigned sites (excluding unassigned ones)
        assigned_sites = frappe.get_all(
            "Site Provisioning",
            filters={"assigned_site": ("is", "set"), "is_unassigned": 0},
            pluck="assigned_site",
        )

        # Parse filters
        parsed_filters = AvailableSite._parse_filters(filters)

        # Generate list of all sites with status
        sites = []
        for i in range(site_min, site_max + 1):
            site_name = f"{prefix}{i}.{domain}"
            status = "Assigned" if site_name in assigned_sites else "Available"

            # Apply status filter
            if not AvailableSite._matches_filter(parsed_filters.get("status"), status):
                continue

            # Apply site_name filter
            if not AvailableSite._matches_filter(parsed_filters.get("site_name"), site_name, is_like=True):
                continue

            # Apply name filter (same as site_name for virtual doctype)
            if not AvailableSite._matches_filter(parsed_filters.get("name"), site_name, is_like=True):
                continue

            sites.append({
                "name": site_name,
                "site_name": site_name,
                "status": status,
            })

        # Handle sorting
        if order_by and isinstance(order_by, str):
            order_by = order_by.replace("`tabAvailable Site`.", "").replace("`", "")
            parts = order_by.split()
            field = parts[0] if parts else "site_name"
            direction = parts[1] if len(parts) > 1 else "asc"
            reverse = direction.lower() == "desc"
            sites.sort(key=lambda x: x.get(field, ""), reverse=reverse)

        # Handle pagination
        start = int(start or 0)
        page_length = int(page_length or 20)

        return sites[start:start + page_length]

    @staticmethod
    def _parse_filters(filters):
        """Parse filters from various formats into a standard dict"""
        if not filters:
            return {}

        # Handle string filters (JSON)
        if isinstance(filters, str):
            try:
                filters = json.loads(filters)
            except (json.JSONDecodeError, TypeError):
                return {}

        # Handle list of lists format [["doctype", "field", "operator", "value"], ...]
        # or [[field, operator, value], ...]
        if isinstance(filters, list):
            filters_dict = {}
            for f in filters:
                if isinstance(f, (list, tuple)):
                    if len(f) >= 4:
                        # [doctype, field, operator, value]
                        filters_dict[f[1]] = [f[2], f[3]]
                    elif len(f) >= 3:
                        # [field, operator, value]
                        filters_dict[f[0]] = [f[1], f[2]]
                    elif len(f) == 2:
                        # [field, value] - assume equals
                        filters_dict[f[0]] = ["=", f[1]]
            return filters_dict

        # Handle dict format
        if isinstance(filters, dict):
            result = {}
            for key, value in filters.items():
                if isinstance(value, (list, tuple)) and len(value) >= 2:
                    # Check if first element looks like an operator
                    if value[0] in ["=", "!=", "like", "not like", ">", "<", ">=", "<=", "in", "not in"]:
                        result[key] = value
                    else:
                        # Assume equals
                        result[key] = ["=", value]
                else:
                    # Simple value - assume equals
                    result[key] = ["=", value]
            return result

        return {}

    @staticmethod
    def _matches_filter(filter_value, actual_value, is_like=False):
        """Check if actual_value matches the filter"""
        if not filter_value:
            return True

        if isinstance(filter_value, (list, tuple)) and len(filter_value) >= 2:
            op, val = filter_value[0], filter_value[1]
            if op == "=":
                return actual_value == val
            elif op == "!=":
                return actual_value != val
            elif op == "like":
                search_term = str(val).replace("%", "").lower()
                return search_term in str(actual_value).lower()
            elif op == "not like":
                search_term = str(val).replace("%", "").lower()
                return search_term not in str(actual_value).lower()
        elif isinstance(filter_value, str):
            if is_like:
                return filter_value.lower() in actual_value.lower()
            return actual_value == filter_value

        return True

    @staticmethod
    def get_count(filters=None, **kwargs):
        """Get count of sites matching filters"""
        settings = frappe.get_single("Sites Setup Settings")

        site_min = settings.site_min
        site_max = settings.site_max

        if not all([site_min, site_max]):
            return 0

        parsed_filters = AvailableSite._parse_filters(filters)

        # If filtering by status
        status_filter = parsed_filters.get("status")
        if status_filter:
            target_status = None
            if isinstance(status_filter, (list, tuple)) and len(status_filter) >= 2:
                if status_filter[0] == "=":
                    target_status = status_filter[1]
            elif isinstance(status_filter, str):
                target_status = status_filter

            if target_status == "Available":
                assigned_count = frappe.db.count(
                    "Site Provisioning",
                    filters={"assigned_site": ("is", "set"), "is_unassigned": 0}
                )
                total = site_max - site_min + 1
                return total - assigned_count
            elif target_status == "Assigned":
                return frappe.db.count(
                    "Site Provisioning",
                    filters={"assigned_site": ("is", "set"), "is_unassigned": 0}
                )

        return site_max - site_min + 1

    @staticmethod
    def get_stats(args=None, **kwargs):
        """Get stats for the list view sidebar"""
        settings = frappe.get_single("Sites Setup Settings")

        site_min = settings.site_min or 0
        site_max = settings.site_max or 0
        total = max(0, site_max - site_min + 1) if site_min and site_max else 0

        assigned_count = frappe.db.count(
            "Site Provisioning",
            filters={"assigned_site": ("is", "set"), "is_unassigned": 0}
        )

        available_count = total - assigned_count

        return {
            "status": [
                ["Available", available_count, False],
                ["Assigned", assigned_count, False],
            ]
        }
