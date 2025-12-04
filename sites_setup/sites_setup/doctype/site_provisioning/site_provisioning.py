import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.background_jobs import enqueue
import re


class SiteProvisioning(Document):
    def before_insert(self):
        self.requested_by = frappe.session.user
        self.status = "Pending"
        self.generate_subdomain_if_empty()
        self.validate_subdomain()
        self.validate_admin_password()
        self.handle_site_assignment()
        self.record_server_info()

    def after_insert(self):
        """Auto-start provisioning after document is created"""
        # Mark the site as assigned in Available Site
        from sites_setup.sites_setup.doctype.available_site.available_site import mark_site_assigned
        mark_site_assigned(self.assigned_site, self.name)

        self.start_provisioning_auto()

    def validate(self):
        if self.is_new():
            self.generate_subdomain_if_empty()
            self.validate_subdomain()
            self.validate_admin_password()

    def generate_subdomain_if_empty(self):
        """Generate subdomain from company name if not provided"""
        if not self.requested_subdomain and self.company_name:
            subdomain = generate_subdomain_from_company(self.company_name)
            if subdomain:
                self.requested_subdomain = subdomain

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

        if not self.requested_subdomain:
            frappe.throw(_("Subdomain is required. Provide a subdomain or company name."))

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

        # Check for uniqueness (exclude unassigned sites)
        existing = frappe.db.exists(
            "Site Provisioning",
            {
                "requested_subdomain": full_subdomain,
                "name": ("!=", self.name or ""),
                "is_unassigned": 0
            },
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

    def handle_site_assignment(self):
        """Handle site assignment - allow admin to select or auto-assign"""
        # If admin manually selected a site, validate it
        if self.assigned_site:
            if "System Manager" not in frappe.get_roles():
                frappe.throw(_("Only System Managers can manually select a site"))

            # Validate the selected site is in the valid range and available
            unassigned_sites = get_unassigned_sites()
            if self.assigned_site not in unassigned_sites:
                frappe.throw(_("The selected site '{0}' is not available").format(self.assigned_site))
        else:
            # Auto-assign the next available site
            self.auto_assign_site()

    def auto_assign_site(self):
        """Assign the next available site from the pool"""
        unassigned_sites = get_unassigned_sites()

        if not unassigned_sites:
            frappe.throw(_("No available ERP sites. Please contact support."))

        self.assigned_site = unassigned_sites[0]

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

    @frappe.whitelist()
    def unassign_site(self, backup=True):
        """Unassign the site and optionally backup"""
        if "System Manager" not in frappe.get_roles():
            frappe.throw(_("Only System Managers can unassign sites"), frappe.PermissionError)

        if self.status != "Success":
            frappe.throw(_("Can only unassign successfully provisioned sites"))

        if self.is_unassigned:
            frappe.throw(_("This site is already unassigned"))

        # Enqueue background job for unassignment
        enqueue(
            "sites_setup.sites_setup.doctype.site_provisioning.site_provisioning.run_unassign",
            queue="long",
            timeout=600,
            provisioning_name=self.name,
            backup=backup,
        )

        return {"message": _("Unassignment process started. Site will be backed up and domain removed.")}


def generate_subdomain_from_company(company_name):
    """Generate a subdomain from company name (max 10 chars)"""
    if not company_name:
        return None

    # Normalize: lowercase, remove special chars, replace spaces with nothing
    subdomain = company_name.lower().strip()

    # Remove all non-alphanumeric characters except hyphens
    subdomain = re.sub(r'[^a-z0-9]', '', subdomain)

    # Take first 10 characters
    subdomain = subdomain[:10]

    # Ensure it starts and ends with alphanumeric
    subdomain = subdomain.strip('-')

    if not subdomain:
        return None

    # Check if subdomain is already taken, append number if needed
    settings = frappe.get_single("Sites Setup Settings")
    domain = settings.site_domain

    original_subdomain = subdomain
    counter = 1

    while True:
        full_subdomain = f"{subdomain}.{domain}"
        exists = frappe.db.exists(
            "Site Provisioning",
            {"requested_subdomain": full_subdomain, "is_unassigned": 0}
        )
        if not exists:
            return subdomain

        # Try with counter
        subdomain = f"{original_subdomain[:8]}{counter}"
        counter += 1

        if counter > 99:
            # Give up after 99 attempts
            return None


def get_unassigned_sites():
    """Get list of unassigned sites from the pool"""
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

    # Generate list of unassigned sites
    unassigned = []
    for i in range(site_min, site_max + 1):
        site = f"{prefix}{i}.{domain}"
        if site not in assigned_sites:
            unassigned.append(site)

    return unassigned


def get_sites_stats():
    """Get statistics about site assignments"""
    settings = frappe.get_single("Sites Setup Settings")

    site_min = settings.site_min or 0
    site_max = settings.site_max or 0
    total_sites = max(0, site_max - site_min + 1) if site_min and site_max else 0

    # Count assigned sites (excluding unassigned)
    assigned_count = frappe.db.count(
        "Site Provisioning",
        filters={"assigned_site": ("is", "set"), "is_unassigned": 0}
    )

    unassigned_count = total_sites - assigned_count

    return {
        "total_sites": total_sites,
        "assigned_count": assigned_count,
        "unassigned_count": unassigned_count,
        "site_prefix": settings.site_prefix,
        "site_domain": settings.site_domain,
        "site_min": site_min,
        "site_max": site_max,
    }


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

        # Step 3: Update admin user and company details on the remote site (if provided)
        user_details = {
            "first_name": provisioning.first_name,
            "middle_name": provisioning.middle_name,
            "last_name": provisioning.last_name,
            "phone": provisioning.phone,
            "email": provisioning.email,
            "company_name": provisioning.company_name,
        }
        has_user_details = any([provisioning.first_name, provisioning.middle_name, provisioning.last_name, provisioning.phone, provisioning.email, provisioning.company_name])

        if has_user_details:
            try:
                frappe.logger().info(f"Updating admin user details for {provisioning.assigned_site}: {user_details}")
                user_update_log = service.update_admin_user(
                    provisioning.assigned_site,
                    user_details
                )
                provisioning.bench_log = (provisioning.bench_log or "") + "\n\n=== ADMIN USER UPDATE ===\n" + user_update_log
                provisioning.save(ignore_permissions=True)
                frappe.db.commit()
                frappe.logger().info(f"Admin user details updated for {provisioning.assigned_site}")
            except Exception as e:
                # Non-fatal error, log it and add to bench_log
                error_msg = f"Failed to update admin user details: {str(e)}"
                frappe.logger().warning(error_msg)
                provisioning.bench_log = (provisioning.bench_log or "") + f"\n\n=== ADMIN USER UPDATE FAILED ===\n{error_msg}"
                provisioning.save(ignore_permissions=True)
                frappe.db.commit()
        else:
            provisioning.bench_log = (provisioning.bench_log or "") + "\n\n=== ADMIN USER UPDATE ===\nNo user details provided, skipping update."
            provisioning.save(ignore_permissions=True)
            frappe.db.commit()

        service.disconnect()

        # Mark as success
        provisioning.status = "Success"
        provisioning.error_message = None
        provisioning.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.logger().info(
            f"Successfully provisioned {provisioning.requested_subdomain} -> {provisioning.assigned_site}"
        )

        # Send success email asynchronously (after returning to caller)
        enqueue(
            "sites_setup.sites_setup.doctype.site_provisioning.site_provisioning._send_welcome_email",
            queue="short",
            provisioning_name=provisioning.name,
        )

    except Exception as e:
        frappe.logger().error(f"Failed to provision {provisioning.requested_subdomain}: {str(e)}")

        provisioning.status = "Failed"
        provisioning.error_message = str(e)
        provisioning.save(ignore_permissions=True)
        frappe.db.commit()

        _send_failure_email(provisioning)


def run_unassign(provisioning_name, backup=True):
    """
    Background job to unassign a site.
    """
    from sites_setup.sites_setup.ssh_service import ERPSshService

    provisioning = frappe.get_doc("Site Provisioning", provisioning_name)

    try:
        frappe.logger().info(f"Starting unassignment for {provisioning.requested_subdomain}")

        service = ERPSshService()

        # Step 1: Backup the site if requested
        if backup:
            try:
                # Pass the domain name to include in backup folder name
                backup_log = service.backup_site(
                    provisioning.assigned_site,
                    domain_name=provisioning.requested_subdomain
                )
                provisioning.bench_log = (provisioning.bench_log or "") + "\n\n=== UNASSIGN BACKUP ===\n" + backup_log
                provisioning.save(ignore_permissions=True)
                frappe.db.commit()
                frappe.logger().info(f"Backup completed for {provisioning.assigned_site} (domain: {provisioning.requested_subdomain})")
            except Exception as e:
                frappe.logger().error(f"Failed to backup site: {str(e)}")
                # Continue with unassignment even if backup fails
                provisioning.bench_log = (provisioning.bench_log or "") + f"\n\n=== BACKUP FAILED ===\n{str(e)}"
                provisioning.save(ignore_permissions=True)
                frappe.db.commit()

        # Step 2: Remove domain from site
        try:
            remove_log = service.remove_domain_from_site(
                provisioning.requested_subdomain,
                provisioning.assigned_site,
            )
            provisioning.bench_log = (provisioning.bench_log or "") + "\n\n=== DOMAIN REMOVED ===\n" + remove_log
            provisioning.save(ignore_permissions=True)
            frappe.db.commit()
            frappe.logger().info(f"Domain removed for {provisioning.requested_subdomain}")
        except Exception as e:
            frappe.logger().error(f"Failed to remove domain: {str(e)}")
            provisioning.error_message = f"Domain removal failed: {str(e)}"
            provisioning.save(ignore_permissions=True)
            frappe.db.commit()
            return

        service.disconnect()

        # Mark as unassigned
        provisioning.status = "Unassigned"
        provisioning.is_unassigned = 1
        provisioning.domain_created = 0
        provisioning.save(ignore_permissions=True)

        # Mark the site as available in Available Site
        from sites_setup.sites_setup.doctype.available_site.available_site import mark_site_available
        mark_site_available(provisioning.assigned_site)

        frappe.db.commit()

        frappe.logger().info(
            f"Successfully unassigned {provisioning.requested_subdomain} from {provisioning.assigned_site}"
        )

    except Exception as e:
        frappe.logger().error(f"Failed to unassign {provisioning.requested_subdomain}: {str(e)}")
        provisioning.error_message = str(e)
        provisioning.save(ignore_permissions=True)
        frappe.db.commit()


def _send_welcome_email(provisioning_name):
    """Send welcome notification email (called async after API response)"""
    try:
        provisioning = frappe.get_doc("Site Provisioning", provisioning_name)

        # Determine recipient email
        recipient_email = provisioning.email
        if not recipient_email and provisioning.requested_by:
            user = frappe.get_doc("User", provisioning.requested_by)
            recipient_email = user.email

        if not recipient_email:
            return

        # Get user name
        user_name = provisioning.first_name or "User"
        if provisioning.last_name:
            user_name = f"{provisioning.first_name} {provisioning.last_name}"

        frappe.sendmail(
            recipients=[recipient_email],
            subject=f"Welcome! Your ERPNext Site is Ready - {provisioning.requested_subdomain}",
            message=f"""
            <h2>Welcome to ERPNext!</h2>
            <p>Hello {user_name},</p>
            <p>Great news! Your ERPNext site has been successfully provisioned and is ready to use.</p>

            <h3>Your Site Details:</h3>
            <table style="border-collapse: collapse; margin: 20px 0;">
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>Site URL</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">
                        <a href="https://{provisioning.requested_subdomain}">https://{provisioning.requested_subdomain}</a>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>Username</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">Administrator</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>Password</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">The password you set during registration</td>
                </tr>
            </table>

            <h3>Getting Started:</h3>
            <ol>
                <li>Click the link above to access your site</li>
                <li>Login with Administrator and your password</li>
                <li>Complete the setup wizard to configure your company</li>
            </ol>

            <p>If you have any questions, please don't hesitate to reach out to our support team.</p>

            <p>Best regards,<br>The ERPNext Team</p>
            """,
        )
    except Exception as e:
        frappe.logger().error(f"Failed to send welcome email: {str(e)}")


def _send_failure_email(provisioning):
    """Send failure notification email"""
    try:
        recipient_email = provisioning.email
        if not recipient_email and provisioning.requested_by:
            user = frappe.get_doc("User", provisioning.requested_by)
            recipient_email = user.email

        if not recipient_email:
            return

        user_name = provisioning.first_name or "User"

        frappe.sendmail(
            recipients=[recipient_email],
            subject=f"Site Provisioning Failed - {provisioning.requested_subdomain}",
            message=f"""
            <h2>Site Provisioning Failed</h2>
            <p>Hello {user_name},</p>
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
