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
        Backup an ERPNext site with optional domain name in the backup filename.

        Args:
            assigned_site: The site to backup (e.g., erp105.havano.cloud)
            domain_name: Optional domain being removed, will be included in backup filename
        """
        bench_dir = self.config["bench_dir"]

        # Generate timestamp for unique backup name
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Create a descriptive backup directory name
        if domain_name:
            # Clean the domain name for use in directory name
            clean_domain = domain_name.replace(".", "_").replace("-", "_")
            backup_dir = f"unassign_{clean_domain}_{timestamp}"
        else:
            backup_dir = f"backup_{timestamp}"

        # Create backup directory and run backup with custom path
        command = (
            f"cd {self._escape_shell(bench_dir)} && "
            f"mkdir -p sites/{self._escape_shell(assigned_site)}/private/backups/{self._escape_shell(backup_dir)} && "
            f"bench --site {self._escape_shell(assigned_site)} backup --with-files "
            f"--backup-path sites/{self._escape_shell(assigned_site)}/private/backups/{self._escape_shell(backup_dir)}"
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
        full_log += f"Backup directory: sites/{assigned_site}/private/backups/{backup_dir}\n\n"
        full_log += f"COMMAND: {command}\n\n"
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
        """Update the Administrator user details on the remote site"""
        bench_dir = self.config["bench_dir"]

        # Build the frappe command to update user
        updates = []
        if user_details.get("first_name"):
            updates.append(f"first_name='{user_details['first_name']}'")
        if user_details.get("middle_name"):
            updates.append(f"middle_name='{user_details['middle_name']}'")
        if user_details.get("last_name"):
            updates.append(f"last_name='{user_details['last_name']}'")
        if user_details.get("phone"):
            updates.append(f"phone='{user_details['phone']}'")

        if not updates:
            return "No user details to update"

        # Use bench execute to run a Python command
        update_script = f"""
import frappe
frappe.connect(site='{assigned_site}')
user = frappe.get_doc('User', 'Administrator')
"""
        for update in updates:
            field, value = update.split('=', 1)
            update_script += f"user.{field} = {value}\n"

        update_script += """
user.save(ignore_permissions=True)
frappe.db.commit()
print('Administrator user updated successfully')
"""

        # Write script to temp file and execute
        command = (
            f"cd {self._escape_shell(bench_dir)} && "
            f"bench --site {self._escape_shell(assigned_site)} execute "
            f"\"frappe.db.set_value('User', 'Administrator', {{'first_name': '{user_details.get('first_name', '')}', 'last_name': '{user_details.get('last_name', '')}', 'phone': '{user_details.get('phone', '')}'}})\""
        )

        result = self.execute_command(command)

        full_log = f"COMMAND: Update Administrator user details\n\n"
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
