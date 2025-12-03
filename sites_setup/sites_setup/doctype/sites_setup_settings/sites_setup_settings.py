import frappe
from frappe.model.document import Document


class SitesSetupSettings(Document):
    def validate(self):
        if self.site_min and self.site_max:
            if self.site_min > self.site_max:
                frappe.throw("Site Range Min cannot be greater than Site Range Max")

    def on_update(self):
        """Sync available sites when settings are updated"""
        from sites_setup.sites_setup.doctype.available_site.available_site import sync_available_sites
        sync_available_sites()

    @staticmethod
    def get_settings():
        """Get the Sites Setup Settings as a dictionary"""
        settings = frappe.get_single("Sites Setup Settings")
        return {
            "ssh_host": settings.ssh_host,
            "ssh_port": settings.ssh_port or 22,
            "ssh_user": settings.ssh_user,
            "ssh_password": settings.get_password("ssh_password") if settings.ssh_password else None,
            "ssh_key_path": settings.ssh_key_path,
            "bench_directory": settings.bench_directory,
            "ssl_fullchain_path": settings.ssl_fullchain_path,
            "ssl_privkey_path": settings.ssl_privkey_path,
            "site_prefix": settings.site_prefix,
            "site_domain": settings.site_domain,
            "site_min": settings.site_min,
            "site_max": settings.site_max,
            "rate_limit_requests": settings.rate_limit_requests or 5,
            "rate_limit_window_minutes": settings.rate_limit_window_minutes or 60,
        }
