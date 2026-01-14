frappe.ui.form.on('Site Provisioning', {
    onload: function(frm) {
        // Load site options for admin site selection
        if (frappe.user_roles.includes('System Manager')) {
            frm.trigger('load_site_options');
        }
    },

    load_site_options: function(frm) {
        // Fetch unassigned sites for the dropdown
        frappe.call({
            method: 'sites_setup.api.get_unassigned_sites',
            callback: function(r) {
                let options = [''];
                if (r.message && r.message.length > 0) {
                    options = options.concat(r.message);
                }

                // For existing records, make sure current assigned_site is in options
                if (!frm.is_new() && frm.doc.assigned_site) {
                    if (!options.includes(frm.doc.assigned_site)) {
                        options.push(frm.doc.assigned_site);
                    }
                }

                frm.set_df_property('assigned_site', 'options', options.join('\n'));

                if (frm.is_new()) {
                    if (r.message && r.message.length > 0) {
                        frm.set_df_property('assigned_site', 'description',
                            `<span class="text-info">${r.message.length} sites available. Leave empty for auto-assignment.</span>`);
                    } else {
                        frm.set_df_property('assigned_site', 'description',
                            '<span class="text-danger">No sites available!</span>');
                    }
                }

                // Refresh the field to show the value
                frm.refresh_field('assigned_site');
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

            // Check if app operation is running
            let app_operation_running = frm.doc.app_operation_status === 'Running';

            // Add unassign button for System Managers (disabled if app operation running)
            if (frappe.user_roles.includes('System Manager') && !frm.doc.is_unassigned) {
                let unassign_btn = frm.add_custom_button(__('Unassign Site'), function() {
                    if (app_operation_running) {
                        frappe.msgprint(__('Cannot unassign site while app operation is in progress.'));
                        return;
                    }
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

            // Add Manage Apps button (for site owner and System Manager)
            if (!frm.doc.is_unassigned) {
                frm.add_custom_button(__('Manage Apps'), function() {
                    if (app_operation_running) {
                        frappe.msgprint(__('An app operation is currently in progress. Please wait for it to complete.'));
                        return;
                    }
                    frm.trigger('show_manage_apps_dialog');
                }, __('Actions'));

                // Add Run Migrate button
                frm.add_custom_button(__('Run Migrate'), function() {
                    if (app_operation_running) {
                        frappe.msgprint(__('An operation is currently in progress. Please wait for it to complete.'));
                        return;
                    }
                    frappe.confirm(
                        __('Are you sure you want to run bench migrate? This will apply any pending database migrations.'),
                        function() {
                            frappe.call({
                                method: 'sites_setup.api.run_site_migrate',
                                args: {
                                    provisioning_id: frm.doc.name
                                },
                                freeze: true,
                                freeze_message: __('Starting migration...'),
                                callback: function(r) {
                                    if (r.message && r.message.success) {
                                        frappe.show_alert({
                                            message: r.message.message,
                                            indicator: 'blue'
                                        });
                                        frm.reload_doc();
                                    }
                                },
                                error: function() {
                                    frappe.msgprint({
                                        title: __('Error'),
                                        message: __('Failed to start migration. Please try again.'),
                                        indicator: 'red'
                                    });
                                }
                            });
                        }
                    );
                }, __('Actions'));
            }

            // Show app operation status if running
            if (app_operation_running) {
                frm.dashboard.add_comment(
                    __('App operation in progress... Page will auto-refresh.'),
                    'blue',
                    true
                );
                // Auto-refresh while app operation is running
                setTimeout(function() {
                    frm.reload_doc();
                }, 5000);
            }

            // Show installed apps section
            if (!frm.doc.is_unassigned && !app_operation_running) {
                frm.trigger('load_installed_apps');
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

            // Add retry button for failed provisioning (disabled if app operation running)
            let app_op_running_failed = frm.doc.app_operation_status === 'Running';
            frm.add_custom_button(__('Retry Provisioning'), function() {
                if (app_op_running_failed) {
                    frappe.msgprint(__('Cannot retry while app operation is in progress.'));
                    return;
                }
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
    },

    load_installed_apps: function(frm) {
        // Load and display installed apps for this site
        frappe.call({
            method: 'sites_setup.api.get_site_apps',
            args: {
                provisioning_id: frm.doc.name
            },
            callback: function(r) {
                if (r.message && r.message.success) {
                    let installed = r.message.installed_apps || [];
                    let status = r.message.app_operation_status || 'Idle';

                    // Build HTML for installed apps display
                    let apps_html = '<div class="installed-apps-container" style="margin-top: 10px;">';
                    apps_html += '<strong>' + __('Installed Apps') + ':</strong><br>';

                    if (installed.length > 0) {
                        apps_html += '<div style="margin-top: 5px;">';
                        installed.forEach(function(app) {
                            let badge_class = (app === 'frappe' || app === 'erpnext') ? 'badge-primary' : 'badge-success';
                            let core_label = (app === 'frappe' || app === 'erpnext') ? ' (core)' : '';
                            apps_html += `<span class="badge ${badge_class}" style="margin: 2px; padding: 5px 10px;">${app}${core_label}</span>`;
                        });
                        apps_html += '</div>';
                    } else {
                        apps_html += '<span class="text-muted">' + __('No apps installed') + '</span>';
                    }

                    // Show operation status if not idle
                    if (status && status !== 'Idle') {
                        let status_class = status === 'Completed' ? 'text-success' : (status === 'Failed' ? 'text-danger' : 'text-info');
                        apps_html += `<br><small class="${status_class}"><strong>${__('Last Operation')}:</strong> ${status}</small>`;
                    }

                    apps_html += '</div>';

                    frm.set_df_property('section_break_apps', 'description', apps_html);
                    frm.refresh_field('section_break_apps');
                }
            }
        });
    },

    show_manage_apps_dialog: function(frm) {
        // Fetch available and installed apps, then show dialog
        frappe.call({
            method: 'sites_setup.api.get_site_apps',
            args: {
                provisioning_id: frm.doc.name
            },
            freeze: true,
            freeze_message: __('Loading apps...'),
            callback: function(r) {
                if (r.message && r.message.success) {
                    let installed_apps = r.message.installed_apps || [];
                    let available_apps = r.message.available_apps || [];
                    let core_apps = ['frappe', 'erpnext'];

                    // Build the dialog fields
                    let fields = [
                        {
                            fieldtype: 'HTML',
                            fieldname: 'apps_info',
                            options: `<p class="text-muted">${__('Check apps to install, uncheck to uninstall. Core apps (frappe, erpnext) cannot be uninstalled.')}</p>`
                        }
                    ];

                    // Add a checkbox for each available app
                    available_apps.forEach(function(app) {
                        let is_installed = installed_apps.includes(app);
                        let is_core = core_apps.includes(app);

                        fields.push({
                            fieldtype: 'Check',
                            fieldname: 'app_' + app,
                            label: app + (is_core ? ' (core - required)' : ''),
                            default: is_installed ? 1 : 0,
                            read_only: is_core ? 1 : 0,
                            description: is_core ? __('Core app cannot be uninstalled') : ''
                        });
                    });

                    // Create and show the dialog
                    let d = new frappe.ui.Dialog({
                        title: __('Manage Apps for {0}', [frm.doc.assigned_site]),
                        fields: fields,
                        size: 'large',
                        primary_action_label: __('Apply Changes'),
                        primary_action: function() {
                            let values = d.get_values();
                            let apps_to_install = [];
                            let apps_to_uninstall = [];

                            // Determine what changed
                            available_apps.forEach(function(app) {
                                let field_name = 'app_' + app;
                                let is_checked = values[field_name] ? true : false;
                                let was_installed = installed_apps.includes(app);
                                let is_core = core_apps.includes(app);

                                if (!is_core) {
                                    if (is_checked && !was_installed) {
                                        apps_to_install.push(app);
                                    } else if (!is_checked && was_installed) {
                                        apps_to_uninstall.push(app);
                                    }
                                }
                            });

                            if (apps_to_install.length === 0 && apps_to_uninstall.length === 0) {
                                frappe.msgprint(__('No changes to apply.'));
                                return;
                            }

                            // Confirm the changes
                            let confirm_msg = '';
                            if (apps_to_install.length > 0) {
                                confirm_msg += __('Apps to install: {0}', [apps_to_install.join(', ')]) + '<br>';
                            }
                            if (apps_to_uninstall.length > 0) {
                                confirm_msg += __('Apps to uninstall: {0}', [apps_to_uninstall.join(', ')]) + '<br>';
                            }
                            confirm_msg += '<br><strong>' + __('This operation may take several minutes.') + '</strong>';

                            frappe.confirm(
                                confirm_msg,
                                function() {
                                    d.hide();

                                    // Call the API to manage apps
                                    frappe.call({
                                        method: 'sites_setup.api.manage_site_apps',
                                        args: {
                                            provisioning_id: frm.doc.name,
                                            apps_to_install: JSON.stringify(apps_to_install),
                                            apps_to_uninstall: JSON.stringify(apps_to_uninstall)
                                        },
                                        freeze: true,
                                        freeze_message: __('Starting app management...'),
                                        callback: function(r) {
                                            if (r.message && r.message.success) {
                                                frappe.show_alert({
                                                    message: r.message.message,
                                                    indicator: 'blue'
                                                });
                                                // Reload the form to show progress
                                                frm.reload_doc();
                                            }
                                        },
                                        error: function(r) {
                                            frappe.msgprint({
                                                title: __('Error'),
                                                message: __('Failed to start app management. Please try again.'),
                                                indicator: 'red'
                                            });
                                        }
                                    });
                                }
                            );
                        }
                    });

                    d.show();
                } else {
                    frappe.msgprint({
                        title: __('Error'),
                        message: __('Failed to load apps. Please try again.'),
                        indicator: 'red'
                    });
                }
            },
            error: function() {
                frappe.msgprint({
                    title: __('Error'),
                    message: __('Failed to connect to server. Please try again.'),
                    indicator: 'red'
                });
            }
        });
    }
});
