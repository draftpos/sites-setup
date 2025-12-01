import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.background_jobs import enqueue
import re


class SiteProvisioning(Document):
    def before_insert(self):
        self.requested_by = frappe.session.user
        self.status = "Pending"
        self.validate_subdomain()
        self.validate_admin_password()
        self.assign_site()
        self.record_server_info()

    def after_insert(self):
        """Auto-start provisioning after document is created"""
        self.start_provisioning_auto()

    def validate(self):
        if self.is_new():
            self.validate_subdomain()
            self.validate_admin_password()

    def record_server_info(self):
        """Record the server information from current settings"""
        settings = frappe.get_single("Sites Setup Settings")
        self.server_ip = settings.ssh_host
        self.server_port = str(settings.ssh_port or 22)
        self.bench_directory = settings.bench_directory

    def validate_subdomain(self):
        """Validate and normalize the subdomain format"""
        settings = frappe.get_single("Sites Setup Settings")
        domain = settings.site_domain

        if not domain:
            frappe.throw(_("Site domain not configured in Sites Setup Settings"))

        subdomain = self.requested_subdomain.lower().strip()

        # Remove the domain suffix if user entered it
        if subdomain.endswith(f".{domain}"):
            subdomain = subdomain.replace(f".{domain}", "")

        # Validate label format (DNS-safe)
        label_pattern = r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$"
        if not re.match(label_pattern, subdomain):
            frappe.throw(
                _(
                    "Invalid subdomain format. Use only lowercase letters, numbers, and hyphens. "
                    "Must start and end with a letter or number. Maximum 63 characters."
                )
            )

        # Always append the domain
        full_subdomain = f"{subdomain}.{domain}"
        self.requested_subdomain = full_subdomain

        # Check for uniqueness
        existing = frappe.db.exists(
            "Site Provisioning",
            {"requested_subdomain": full_subdomain, "name": ("!=", self.name or "")},
        )
        if existing:
            frappe.throw(_("This subdomain ({0}) is already taken").format(full_subdomain))

    def validate_admin_password(self):
        """Validate admin password complexity"""
        password = self.admin_password
        if not password:
            frappe.throw(_("Admin password is required"))

        if len(password) < 8:
            frappe.throw(_("Admin password must be at least 8 characters long"))

        # Check for complexity
        has_upper = bool(re.search(r"[A-Z]", password))
        has_lower = bool(re.search(r"[a-z]", password))
        has_digit = bool(re.search(r"\d", password))
        has_special = bool(re.search(r"[@$!%*?&]", password))

        if not (has_upper and has_lower and has_digit and has_special):
            frappe.throw(
                _(
                    "Password must contain at least one uppercase letter, "
                    "one lowercase letter, one number, and one special character (@$!%*?&)"
                )
            )

    def assign_site(self):
        """Assign the next available site from the pool"""
        settings = frappe.get_single("Sites Setup Settings")

        site_min = settings.site_min
        site_max = settings.site_max
        prefix = settings.site_prefix
        domain = settings.site_domain

        if not all([site_min, site_max, prefix, domain]):
            frappe.throw(_("Site range not properly configured in Sites Setup Settings"))

        # Get all assigned sites
        assigned_sites = frappe.get_all(
            "Site Provisioning",
            filters={"assigned_site": ("is", "set")},
            pluck="assigned_site",
        )

        # Find next available site
        for i in range(site_min, site_max + 1):
            site = f"{prefix}{i}.{domain}"
            if site not in assigned_sites:
                self.assigned_site = site
                return

        frappe.throw(_("No available ERP sites. Please contact support."))

    def start_provisioning_auto(self):
        """Auto-start provisioning (called from after_insert)"""
        if self.status != "Pending":
            return

        # Get the password before enqueueing (it's encrypted in DB)
        admin_password = self.get_password("admin_password")

        # Update status to Running
        frappe.db.set_value("Site Provisioning", self.name, "status", "Running")
        frappe.db.commit()

        # Enqueue background job
        enqueue(
            "sites_setup.sites_setup.doctype.site_provisioning.site_provisioning.run_provisioning",
            queue="long",
            timeout=600,
            provisioning_name=self.name,
            admin_password=admin_password,
        )

    @frappe.whitelist()
    def start_provisioning(self):
        """Manually start the provisioning process (for retry)"""
        if self.status not in ["Pending", "Failed"]:
            frappe.throw(_("Can only start provisioning for pending or failed requests"))

        if not self.admin_password:
            frappe.throw(_("Admin password is required to start provisioning"))

        # Get the password before enqueueing (it's encrypted in DB)
        admin_password = self.get_password("admin_password")

        # Enqueue background job
        enqueue(
            "sites_setup.sites_setup.doctype.site_provisioning.site_provisioning.run_provisioning",
            queue="long",
            timeout=600,
            provisioning_name=self.name,
            admin_password=admin_password,
        )

        self.status = "Running"
        self.error_message = None
        self.save(ignore_permissions=True)

        return {"message": _("Provisioning started")}

    @staticmethod
    def get_next_available_site():
        """Static method to get next available site without creating a document"""
        settings = frappe.get_single("Sites Setup Settings")

        site_min = settings.site_min
        site_max = settings.site_max
        prefix = settings.site_prefix
        domain = settings.site_domain

        assigned_sites = frappe.get_all(
            "Site Provisioning",
            filters={"assigned_site": ("is", "set")},
            pluck="assigned_site",
        )

        for i in range(site_min, site_max + 1):
            site = f"{prefix}{i}.{domain}"
            if site not in assigned_sites:
                return site

        return None


def run_provisioning(provisioning_name, admin_password):
    """
    Background job to execute site provisioning.
    """
    from sites_setup.sites_setup.ssh_service import ERPSshService

    provisioning = frappe.get_doc("Site Provisioning", provisioning_name)

    # Update status to Running (in case it wasn't set)
    if provisioning.status != "Running":
        provisioning.status = "Running"
        provisioning.save(ignore_permissions=True)
        frappe.db.commit()

    try:
        frappe.logger().info(f"Starting provisioning for {provisioning.requested_subdomain}")

        service = ERPSshService()

        # Step 1: Add domain to site
        try:
            domain_log = service.add_domain_to_site(
                provisioning.requested_subdomain,
                provisioning.assigned_site,
            )
            provisioning.domain_created = 1
            provisioning.bench_log = domain_log
            provisioning.save(ignore_permissions=True)
            frappe.db.commit()
            frappe.logger().info(f"Domain created for {provisioning.requested_subdomain}")
        except Exception as e:
            frappe.logger().error(f"Failed to create domain: {str(e)}")
            provisioning.status = "Failed"
            provisioning.error_message = f"Domain creation failed: {str(e)}"
            provisioning.save(ignore_permissions=True)
            frappe.db.commit()
            _send_failure_email(provisioning)
            return

        # Step 2: Set admin password
        try:
            password_log = service.set_admin_password(
                provisioning.assigned_site,
                admin_password,
            )
            provisioning.admin_password_set = 1
            provisioning.bench_log = (provisioning.bench_log or "") + "\n\n" + password_log
            provisioning.save(ignore_permissions=True)
            frappe.db.commit()
            frappe.logger().info(f"Admin password set for {provisioning.assigned_site}")
        except Exception as e:
            frappe.logger().error(f"Failed to set admin password: {str(e)}")
            provisioning.status = "Failed"
            provisioning.error_message = f"Password setting failed: {str(e)}"
            provisioning.save(ignore_permissions=True)
            frappe.db.commit()
            _send_failure_email(provisioning)
            return

        service.disconnect()

        # Mark as success
        provisioning.status = "Success"
        provisioning.error_message = None
        provisioning.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.logger().info(
            f"Successfully provisioned {provisioning.requested_subdomain} -> {provisioning.assigned_site}"
        )

        # Send success email
        _send_success_email(provisioning)

    except Exception as e:
        frappe.logger().error(f"Failed to provision {provisioning.requested_subdomain}: {str(e)}")

        provisioning.status = "Failed"
        provisioning.error_message = str(e)
        provisioning.save(ignore_permissions=True)
        frappe.db.commit()

        _send_failure_email(provisioning)


def _send_success_email(provisioning):
    """Send success notification email"""
    try:
        user = frappe.get_doc("User", provisioning.requested_by)
        frappe.sendmail(
            recipients=[user.email],
            subject=f"Your ERPNext Site is Ready - {provisioning.requested_subdomain}",
            message=f"""
            <h2>Your ERPNext Site is Ready!</h2>
            <p>Hello {user.first_name or user.email},</p>
            <p>Your ERPNext site has been successfully provisioned.</p>
            <h3>Site Details:</h3>
            <ul>
                <li><strong>URL:</strong> <a href="https://{provisioning.requested_subdomain}">https://{provisioning.requested_subdomain}</a></li>
                <li><strong>Username:</strong> Administrator</li>
                <li><strong>Password:</strong> The password you set during provisioning</li>
                <li><strong>Server:</strong> {provisioning.server_ip}</li>
            </ul>
            <p>Please login and change your password if needed.</p>
            <p>Best regards,<br>Sites Setup System</p>
            """,
        )
    except Exception as e:
        frappe.logger().error(f"Failed to send success email: {str(e)}")


def _send_failure_email(provisioning):
    """Send failure notification email"""
    try:
        user = frappe.get_doc("User", provisioning.requested_by)
        frappe.sendmail(
            recipients=[user.email],
            subject=f"Site Provisioning Failed - {provisioning.requested_subdomain}",
            message=f"""
            <h2>Site Provisioning Failed</h2>
            <p>Hello {user.first_name or user.email},</p>
            <p>Unfortunately, we were unable to fully provision your ERPNext site.</p>
            <h3>Details:</h3>
            <ul>
                <li><strong>Requested Subdomain:</strong> {provisioning.requested_subdomain}</li>
                <li><strong>Server:</strong> {provisioning.server_ip}</li>
                <li><strong>Domain Created:</strong> {'Yes' if provisioning.domain_created else 'No'}</li>
                <li><strong>Admin Password Set:</strong> {'Yes' if provisioning.admin_password_set else 'No'}</li>
                <li><strong>Error:</strong> {provisioning.error_message}</li>
            </ul>
            <p>Please contact support for assistance.</p>
            <p>Best regards,<br>Sites Setup System</p>
            """,
        )
    except Exception as e:
        frappe.logger().error(f"Failed to send failure email: {str(e)}")
