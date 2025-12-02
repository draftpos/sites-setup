frappe.ui.form.on('Site Provisioning', {
    onload: function(frm) {
        // Load site options for admin site selection
        if (frm.is_new() && frappe.user_roles.includes('System Manager')) {
            frm.trigger('load_site_options');
        }
    },

    load_site_options: function(frm) {
        // Fetch unassigned sites for the dropdown
        frappe.call({
            method: 'sites_setup.api.get_unassigned_sites',
            callback: function(r) {
                if (r.message && r.message.length > 0) {
                    let options = [''].concat(r.message);
                    frm.set_df_property('assigned_site', 'options', options.join('\n'));
                    frm.set_df_property('assigned_site', 'description',
                        `<span class="text-info">${r.message.length} sites available. Leave empty for auto-assignment.</span>`);
                } else {
                    frm.set_df_property('assigned_site', 'options', '');
                    frm.set_df_property('assigned_site', 'description',
                        '<span class="text-danger">No sites available!</span>');
                }
            }
        });
    },

    refresh: function(frm) {
        // Show status indicators
        if (frm.doc.status === 'Success') {
            frm.dashboard.set_headline_alert(
                `<div class="alert alert-success">
                    <strong>Site Ready!</strong> Visit:
                    <a href="https://${frm.doc.requested_subdomain}" target="_blank">
                        https://${frm.doc.requested_subdomain}
                    </a>
                    <br><small>Server: ${frm.doc.server_ip || 'N/A'}</small>
                </div>`
            );

            // Add unassign button for System Managers
            if (frappe.user_roles.includes('System Manager') && !frm.doc.is_unassigned) {
                frm.add_custom_button(__('Unassign Site'), function() {
                    frappe.confirm(
                        __('Are you sure you want to unassign this site? This will backup the site and remove the domain.'),
                        function() {
                            frappe.call({
                                method: 'unassign_site',
                                doc: frm.doc,
                                args: { backup: true },
                                freeze: true,
                                freeze_message: __('Starting unassignment process...'),
                                callback: function(r) {
                                    if (r.message) {
                                        frappe.show_alert({
                                            message: r.message.message,
                                            indicator: 'blue'
                                        });
                                        frm.reload_doc();
                                    }
                                }
                            });
                        }
                    );
                }, __('Actions'));
            }
        } else if (frm.doc.status === 'Unassigned') {
            frm.dashboard.set_headline_alert(
                `<div class="alert alert-warning">
                    <strong>Site Unassigned</strong> - This domain has been removed and the site is available for reuse.
                    <br><small>Previous Server: ${frm.doc.server_ip || 'N/A'}</small>
                </div>`
            );
        } else if (frm.doc.status === 'Failed') {
            frm.dashboard.set_headline_alert(
                `<div class="alert alert-danger">
                    <strong>Provisioning Failed:</strong> ${frm.doc.error_message || 'Unknown error'}
                    <br><small>Server: ${frm.doc.server_ip || 'N/A'}</small>
                </div>`
            );

            // Add retry button for failed provisioning
            frm.add_custom_button(__('Retry Provisioning'), function() {
                frappe.confirm(
                    __('Are you sure you want to retry provisioning?'),
                    function() {
                        frappe.call({
                            method: 'start_provisioning',
                            doc: frm.doc,
                            freeze: true,
                            freeze_message: __('Retrying provisioning...'),
                            callback: function(r) {
                                if (r.message) {
                                    frappe.show_alert({
                                        message: __('Provisioning restarted!'),
                                        indicator: 'green'
                                    });
                                    frm.reload_doc();
                                }
                            }
                        });
                    }
                );
            }, __('Actions'));

        } else if (frm.doc.status === 'Running') {
            frm.dashboard.set_headline_alert(
                `<div class="alert alert-info">
                    <strong>Provisioning in progress...</strong> Please wait while your site is being set up.
                    <br><small>Server: ${frm.doc.server_ip || 'N/A'}</small>
                </div>`
            );
            // Auto-refresh while running
            setTimeout(function() {
                frm.reload_doc();
            }, 5000);
        }

        // Show provisioning status details
        if (!frm.is_new() && (frm.doc.domain_created || frm.doc.admin_password_set)) {
            let status_html = '<div class="row">';
            status_html += `<div class="col-sm-6">
                <span class="indicator ${frm.doc.domain_created ? 'green' : 'orange'}"></span>
                Domain Created: ${frm.doc.domain_created ? 'Yes' : 'No'}
            </div>`;
            status_html += `<div class="col-sm-6">
                <span class="indicator ${frm.doc.admin_password_set ? 'green' : 'orange'}"></span>
                Admin Password Set: ${frm.doc.admin_password_set ? 'Yes' : 'No'}
            </div>`;
            status_html += '</div>';
            frm.set_df_property('section_break_details', 'description', status_html);
        }

        // Add Test SSH Connection button for System Managers
        if (frappe.user_roles.includes('System Manager') && !frm.is_new()) {
            frm.add_custom_button(__('Test SSH Connection'), function() {
                frappe.call({
                    method: 'sites_setup.api.test_ssh_connection',
                    freeze: true,
                    freeze_message: __('Testing SSH connection...'),
                    callback: function(r) {
                        if (r.message) {
                            if (r.message.success) {
                                frappe.msgprint({
                                    title: __('SSH Connection Successful'),
                                    message: __('Connection to server established.<br>Bench Version: {0}',
                                               [r.message.bench_version]),
                                    indicator: 'green'
                                });
                            } else {
                                frappe.msgprint({
                                    title: __('SSH Connection Failed'),
                                    message: r.message.message,
                                    indicator: 'red'
                                });
                            }
                        }
                    }
                });
            }, __('Actions'));

            // Add view domains by server button
            frm.add_custom_button(__('View Server Summary'), function() {
                frappe.call({
                    method: 'sites_setup.api.get_server_summary',
                    callback: function(r) {
                        if (r.message && r.message.length > 0) {
                            let html = '<table class="table table-bordered">';
                            html += '<thead><tr><th>Server IP</th><th>Port</th><th>Total</th><th>Success</th><th>Failed</th><th>Running</th></tr></thead>';
                            html += '<tbody>';
                            r.message.forEach(function(server) {
                                html += `<tr>
                                    <td>${server.server_ip}</td>
                                    <td>${server.server_port}</td>
                                    <td>${server.total_domains}</td>
                                    <td class="text-success">${server.successful}</td>
                                    <td class="text-danger">${server.failed}</td>
                                    <td class="text-info">${server.running}</td>
                                </tr>`;
                            });
                            html += '</tbody></table>';

                            frappe.msgprint({
                                title: __('Server Summary'),
                                message: html,
                                indicator: 'blue'
                            });
                        } else {
                            frappe.msgprint(__('No server data available'));
                        }
                    }
                });
            }, __('Actions'));
        }
    },

    requested_subdomain: function(frm) {
        // Normalize and validate subdomain on change
        if (frm.doc.requested_subdomain && frm.is_new()) {
            let subdomain = frm.doc.requested_subdomain.toLowerCase().trim();

            // Remove .havano.cloud if user typed it
            subdomain = subdomain.replace(/\.havano\.cloud$/, '');

            // Validate format
            if (!/^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$/.test(subdomain)) {
                frappe.show_alert({
                    message: __('Invalid subdomain. Use only lowercase letters, numbers, and hyphens.'),
                    indicator: 'red'
                });
                return;
            }

            // Check availability
            frappe.call({
                method: 'sites_setup.api.check_subdomain_availability',
                args: {
                    subdomain: subdomain
                },
                callback: function(r) {
                    if (r.message) {
                        if (r.message.available) {
                            frappe.show_alert({
                                message: __('Subdomain {0} is available!', [r.message.subdomain]),
                                indicator: 'green'
                            });
                        } else {
                            frappe.show_alert({
                                message: __('Subdomain {0} is already taken', [r.message.subdomain]),
                                indicator: 'red'
                            });
                        }
                    }
                }
            });
        }
    },

    admin_password: function(frm) {
        // Validate password on change
        let password = frm.doc.admin_password;
        if (password && password.length > 0) {
            let errors = [];

            if (password.length < 8) {
                errors.push('At least 8 characters');
            }
            if (!/[A-Z]/.test(password)) {
                errors.push('One uppercase letter');
            }
            if (!/[a-z]/.test(password)) {
                errors.push('One lowercase letter');
            }
            if (!/\d/.test(password)) {
                errors.push('One number');
            }
            if (!/[@$!%*?&]/.test(password)) {
                errors.push('One special character (@$!%*?&)');
            }

            if (errors.length > 0) {
                frm.set_df_property('admin_password', 'description',
                    '<span class="text-danger">Missing: ' + errors.join(', ') + '</span>');
            } else {
                frm.set_df_property('admin_password', 'description',
                    '<span class="text-success">Password meets all requirements</span>');
            }
        }
    },

    after_save: function(frm) {
        // Show message that provisioning has started
        if (frm.doc.status === 'Running') {
            frappe.show_alert({
                message: __('Provisioning started automatically! Page will refresh to show progress.'),
                indicator: 'blue'
            });
            // Reload to show progress
            setTimeout(function() {
                frm.reload_doc();
            }, 2000);
        }
    },

    company_name: function(frm) {
        // Auto-suggest subdomain when company name changes (if subdomain is empty)
        if (frm.doc.company_name && !frm.doc.requested_subdomain && frm.is_new()) {
            let suggested = frm.doc.company_name.toLowerCase()
                .replace(/[^a-z0-9]/g, '')
                .substring(0, 10);
            if (suggested) {
                frm.set_value('requested_subdomain', suggested);
                frappe.show_alert({
                    message: __('Subdomain auto-generated from company name'),
                    indicator: 'blue'
                });
            }
        }
    }
});
