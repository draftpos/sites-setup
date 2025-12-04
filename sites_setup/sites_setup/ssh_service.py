import frappe
from frappe import _
import paramiko
import socket


class ERPSshService:
    """SSH Service for provisioning ERPNext sites with domains"""

    def __init__(self):
        self.ssh = None
        self.config = self._get_ssh_config()

    def _get_ssh_config(self):
        """Get SSH configuration from Sites Setup Settings"""
        settings = frappe.get_single("Sites Setup Settings")
        return {
            "host": settings.ssh_host,
            "port": settings.ssh_port or 22,
            "user": settings.ssh_user,
            "password": settings.get_password("ssh_password") if settings.ssh_password else None,
            "key_path": settings.ssh_key_path,
            "bench_dir": settings.bench_directory,
            "ssl_fullchain": settings.ssl_fullchain_path,
            "ssl_privkey": settings.ssl_privkey_path,
        }

    def connect(self):
        """Establish SSH connection to the ERP server"""
        if self.ssh and self.ssh.get_transport() and self.ssh.get_transport().is_active():
            return self.ssh

        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            # Try key authentication first
            if self.config["key_path"]:
                try:
                    private_key = paramiko.RSAKey.from_private_key_file(self.config["key_path"])
                    self.ssh.connect(
                        hostname=self.config["host"],
                        port=self.config["port"],
                        username=self.config["user"],
                        pkey=private_key,
                        timeout=30,
                    )
                    return self.ssh
                except Exception:
                    pass  # Fall back to password auth

            # Try password authentication
            if self.config["password"]:
                self.ssh.connect(
                    hostname=self.config["host"],
                    port=self.config["port"],
                    username=self.config["user"],
                    password=self.config["password"],
                    timeout=30,
                )
                return self.ssh

            raise Exception("No SSH authentication method available")

        except socket.timeout:
            raise Exception(f"SSH connection timed out to {self.config['host']}")
        except paramiko.AuthenticationException:
            raise Exception("SSH authentication failed")
        except Exception as e:
            raise Exception(f"SSH connection failed: {str(e)}")

    def execute_command(self, command):
        """Execute a command on the remote server"""
        ssh = self.connect()

        frappe.logger().info(f"Executing SSH command: {command}")

        stdin, stdout, stderr = ssh.exec_command(command, timeout=300)

        output = stdout.read().decode("utf-8", errors="replace")
        error = stderr.read().decode("utf-8", errors="replace")
        exit_code = stdout.channel.recv_exit_status()

        frappe.logger().info(f"SSH command exit code: {exit_code}")

        return {
            "output": output,
            "stderr": error,
            "exit_code": exit_code,
        }

    def provision_site(self, subdomain, assigned_site, admin_password):
        """
        Provision a new ERP site with domain and SSL.

        Steps:
        1. Add domain to the site with SSL
        2. Regenerate nginx config
        3. Reload nginx
        4. Set admin password
        """
        bench_dir = self.config["bench_dir"]
        fullchain = self.config["ssl_fullchain"]
        privkey = self.config["ssl_privkey"]

        # Build the complete command
        command = (
            f"cd {self._escape_shell(bench_dir)} && "
            f"bench setup add-domain {self._escape_shell(subdomain)} "
            f"--ssl-certificate {self._escape_shell(fullchain)} "
            f"--ssl-certificate-key {self._escape_shell(privkey)} "
            f"--site {self._escape_shell(assigned_site)} && "
            f"bench setup nginx --yes && "
            f"sudo service nginx reload && "
            f"bench --site {self._escape_shell(assigned_site)} set-admin-password {self._escape_shell(admin_password)}"
        )

        result = self.execute_command(command)

        if result["exit_code"] != 0:
            raise Exception(
                f"Provisioning failed with exit code {result['exit_code']}: {result['stderr']}"
            )

        # Build full log
        full_log = f"COMMAND: {command}\n\n"
        full_log += f"STDOUT:\n{result['output']}\n\n"
        if result["stderr"]:
            full_log += f"STDERR:\n{result['stderr']}\n"
        full_log += f"EXIT CODE: {result['exit_code']}"

        return full_log

    def add_domain_to_site(self, subdomain, assigned_site):
        """Add a new domain to an existing ERPNext site (without setting password)"""
        bench_dir = self.config["bench_dir"]
        fullchain = self.config["ssl_fullchain"]
        privkey = self.config["ssl_privkey"]

        command = (
            f"cd {self._escape_shell(bench_dir)} && "
            f"bench setup add-domain {self._escape_shell(subdomain)} "
            f"--ssl-certificate {self._escape_shell(fullchain)} "
            f"--ssl-certificate-key {self._escape_shell(privkey)} "
            f"--site {self._escape_shell(assigned_site)} && "
            f"bench setup nginx --yes && "
            f"sudo service nginx reload"
        )

        result = self.execute_command(command)

        if result["exit_code"] != 0:
            raise Exception(
                f"Add domain failed with exit code {result['exit_code']}: {result['stderr']}"
            )

        full_log = f"COMMAND: {command}\n\n"
        full_log += f"STDOUT:\n{result['output']}\n\n"
        if result["stderr"]:
            full_log += f"STDERR:\n{result['stderr']}\n"
        full_log += f"EXIT CODE: {result['exit_code']}"

        return full_log

    def set_admin_password(self, assigned_site, admin_password):
        """Set the admin password for an ERPNext site"""
        bench_dir = self.config["bench_dir"]

        command = (
            f"cd {self._escape_shell(bench_dir)} && "
            f"bench --site {self._escape_shell(assigned_site)} set-admin-password {self._escape_shell(admin_password)}"
        )

        result = self.execute_command(command)

        if result["exit_code"] != 0:
            raise Exception(
                f"Set admin password failed with exit code {result['exit_code']}: {result['stderr']}"
            )

        full_log = f"COMMAND: bench --site {assigned_site} set-admin-password ********\n\n"
        full_log += f"STDOUT:\n{result['output']}\n\n"
        if result["stderr"]:
            full_log += f"STDERR:\n{result['stderr']}\n"
        full_log += f"EXIT CODE: {result['exit_code']}"

        return full_log

    def backup_site(self, assigned_site, domain_name=None):
        """
        Backup an ERPNext site.

        Args:
            assigned_site: The site to backup (e.g., erp105.havano.cloud)
            domain_name: Optional domain being removed (for logging purposes)
        """
        bench_dir = self.config["bench_dir"]

        command = (
            f"cd {self._escape_shell(bench_dir)} && "
            f"bench --site {self._escape_shell(assigned_site)} backup --with-files"
        )

        result = self.execute_command(command)

        if result["exit_code"] != 0:
            raise Exception(
                f"Backup failed with exit code {result['exit_code']}: {result['stderr']}"
            )

        full_log = f"BACKUP INFO:\n"
        full_log += f"Site: {assigned_site}\n"
        if domain_name:
            full_log += f"Domain being removed: {domain_name}\n"
        full_log += f"\nCOMMAND: {command}\n\n"
        full_log += f"STDOUT:\n{result['output']}\n\n"
        if result["stderr"]:
            full_log += f"STDERR:\n{result['stderr']}\n"
        full_log += f"EXIT CODE: {result['exit_code']}"

        return full_log

    def remove_domain_from_site(self, subdomain, assigned_site):
        """Remove a domain from an ERPNext site"""
        bench_dir = self.config["bench_dir"]

        command = (
            f"cd {self._escape_shell(bench_dir)} && "
            f"bench setup remove-domain {self._escape_shell(subdomain)} "
            f"--site {self._escape_shell(assigned_site)} && "
            f"bench setup nginx --yes && "
            f"sudo service nginx reload"
        )

        result = self.execute_command(command)

        if result["exit_code"] != 0:
            raise Exception(
                f"Remove domain failed with exit code {result['exit_code']}: {result['stderr']}"
            )

        full_log = f"COMMAND: {command}\n\n"
        full_log += f"STDOUT:\n{result['output']}\n\n"
        if result["stderr"]:
            full_log += f"STDERR:\n{result['stderr']}\n"
        full_log += f"EXIT CODE: {result['exit_code']}"

        return full_log

    def update_admin_user(self, assigned_site, user_details):
        """Update the Administrator user details and company on the remote site using bench console"""
        bench_dir = self.config["bench_dir"]

        # Check if there's anything to update
        first_name = user_details.get("first_name", "") or ""
        middle_name = user_details.get("middle_name", "") or ""
        last_name = user_details.get("last_name", "") or ""
        phone = user_details.get("phone", "") or ""
        email = user_details.get("email", "") or ""
        company_name = user_details.get("company_name", "") or ""

        if not any([first_name, middle_name, last_name, phone, email, company_name]):
            return "No user/company details to update"

        # Create a Python script file on the server
        script_content = f'''
first_name = "{first_name}"
middle_name = "{middle_name}"
last_name = "{last_name}"
phone = "{phone}"
email = "{email}"
company_name = "{company_name}"

# Update Administrator user details
user_updates = {{}}
if first_name:
    user_updates["first_name"] = first_name
if middle_name:
    user_updates["middle_name"] = middle_name
if last_name:
    user_updates["last_name"] = last_name
if phone:
    user_updates["phone"] = phone
if email:
    user_updates["email"] = email

if user_updates:
    frappe.db.set_value("User", "Administrator", user_updates)
    frappe.db.commit()
    print(f"SUCCESS: Administrator user updated")
    print(f"Updated user fields: {{list(user_updates.keys())}}")
else:
    print("No user fields to update")

# Update Company name if provided
if company_name:
    # Get the first company (default company)
    companies = frappe.get_all("Company", limit=1)
    if companies:
        company_doc = companies[0].name
        frappe.db.set_value("Company", company_doc, "company_name", company_name)
        frappe.db.commit()
        print(f"SUCCESS: Company '{{company_doc}}' renamed to '{{company_name}}'")
    else:
        print("No company found to update")
'''

        # Write script to file and execute via bench console (like your setup wizard)
        script_path = f"/tmp/update_admin_{assigned_site.replace('.', '_')}.py"

        command = (
            f"cat > {script_path} << 'SCRIPT_EOF'\n{script_content}\nSCRIPT_EOF\n"
            f"cd {self._escape_shell(bench_dir)} && "
            f"bench --site {self._escape_shell(assigned_site)} console << EOF\n"
            f"exec(open(\"{script_path}\").read())\n"
            f"EOF\n"
            f"rm -f {script_path}"
        )

        result = self.execute_command(command)

        full_log = f"COMMAND: Update Administrator user and company details\n"
        full_log += f"Site: {assigned_site}\n"
        full_log += f"User Fields: first_name={first_name}, last_name={last_name}, phone={phone}, email={email}\n"
        full_log += f"Company: {company_name}\n\n"
        full_log += f"STDOUT:\n{result['output']}\n\n"
        if result["stderr"]:
            full_log += f"STDERR:\n{result['stderr']}\n"
        full_log += f"EXIT CODE: {result['exit_code']}"

        return full_log

    def test_connection(self):
        """Test the SSH connection and Bench availability"""
        try:
            # Test basic connection
            echo_result = self.execute_command('echo "SSH connection successful"')

            if echo_result["exit_code"] != 0:
                raise Exception("Basic SSH test failed")

            # Test Bench availability
            bench_result = self.execute_command("bench --version")

            if bench_result["exit_code"] != 0:
                raise Exception("Bench command not available or accessible")

            return {
                "success": True,
                "message": "SSH connection and Bench availability confirmed",
                "bench_version": bench_result["output"].strip(),
            }

        except Exception as e:
            return {
                "success": False,
                "message": str(e),
            }

    def disconnect(self):
        """Close SSH connection"""
        if self.ssh:
            self.ssh.close()
            self.ssh = None

    def _escape_shell(self, value):
        """Escape shell arguments"""
        if value is None:
            return "''"
        return "'" + str(value).replace("'", "'\"'\"'") + "'"

    def __del__(self):
        self.disconnect()
