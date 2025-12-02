frappe.listview_settings['Site Provisioning'] = {
    add_fields: ['status', 'requested_subdomain', 'assigned_site', 'server_ip', 'domain_created', 'admin_password_set', 'is_unassigned'],

    get_indicator: function(doc) {
        if (doc.status === 'Success') {
            return [__('Success'), 'green', 'status,=,Success'];
        } else if (doc.status === 'Failed') {
            return [__('Failed'), 'red', 'status,=,Failed'];
        } else if (doc.status === 'Running') {
            return [__('Running'), 'blue', 'status,=,Running'];
        } else if (doc.status === 'Pending') {
            return [__('Pending'), 'orange', 'status,=,Pending'];
        } else if (doc.status === 'Unassigned') {
            return [__('Unassigned'), 'grey', 'status,=,Unassigned'];
        }
    },

    onload: function(listview) {
        // Add custom buttons for System Managers
        if (frappe.user_roles.includes('System Manager')) {
            // Settings button
            listview.page.add_inner_button(__('Settings'), function() {
                frappe.set_route('Form', 'Sites Setup Settings');
            });

            // View Unassigned Sites button
            listview.page.add_inner_button(__('Available Sites'), function() {
                frappe.sites_setup.show_unassigned_sites();
            });

            // Server Summary button
            listview.page.add_inner_button(__('Server Summary'), function() {
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
            });

            // Show quick stats in sidebar
            frappe.call({
                method: 'sites_setup.api.get_sites_stats',
                callback: function(r) {
                    if (r.message) {
                        let stats = r.message;
                        let stats_html = `
                            <div class="stat-wrapper" style="padding: 10px; background: #f8f8f8; border-radius: 4px; margin-bottom: 10px;">
                                <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                                    <span>Total Sites:</span>
                                    <strong>${stats.total_sites}</strong>
                                </div>
                                <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                                    <span>Assigned:</span>
                                    <strong style="color: #4caf50;">${stats.assigned_count}</strong>
                                </div>
                                <div style="display: flex; justify-content: space-between;">
                                    <span>Available:</span>
                                    <strong style="color: #ff9800;">${stats.unassigned_count}</strong>
                                </div>
                            </div>
                        `;
                        // Add stats to page
                        if (listview.page.sidebar) {
                            $(stats_html).prependTo(listview.page.sidebar);
                        }
                    }
                }
            });
        }
    },

    formatters: {
        requested_subdomain: function(value, df, doc) {
            if (value && doc.status === 'Success') {
                return `<a href="https://${value}" target="_blank">${value}</a>`;
            }
            return value || '';
        }
    }
};

// Global namespace for sites_setup functions
frappe.sites_setup = frappe.sites_setup || {};

frappe.sites_setup.show_unassigned_sites = function() {
    frappe.call({
        method: 'sites_setup.api.get_unassigned_sites',
        callback: function(r) {
            if (r.message && r.message.length > 0) {
                let html = '<div style="max-height: 400px; overflow-y: auto;">';
                html += '<table class="table table-bordered table-hover">';
                html += '<thead><tr><th>#</th><th>Site Name</th></tr></thead>';
                html += '<tbody>';
                r.message.forEach(function(site, index) {
                    html += `<tr>
                        <td>${index + 1}</td>
                        <td><code>${site}</code></td>
                    </tr>`;
                });
                html += '</tbody></table></div>';
                html += `<p class="text-muted" style="margin-top: 10px;">Total: ${r.message.length} sites available for assignment</p>`;

                frappe.msgprint({
                    title: __('Available (Unassigned) Sites'),
                    message: html,
                    indicator: 'orange'
                });
            } else {
                frappe.msgprint({
                    title: __('No Sites Available'),
                    message: __('All sites in the pool have been assigned.'),
                    indicator: 'red'
                });
            }
        }
    });
};
