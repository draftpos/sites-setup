frappe.ui.form.on('Sites Setup Settings', {
    refresh: function(frm) {
        // Show dashboard with site stats
        frm.trigger('show_sites_dashboard');

        // Add Test SSH Connection button
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
        });

        // Add View Server Summary button
        frm.add_custom_button(__('Server Summary'), function() {
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
    },

    show_sites_dashboard: function(frm) {
        // Fetch and display site statistics
        frappe.call({
            method: 'sites_setup.api.get_sites_stats',
            callback: function(r) {
                if (r.message) {
                    let stats = r.message;
                    let stats_html = `
                        <div class="row" style="margin: 20px 0;">
                            <div class="col-sm-4">
                                <div class="stat-box text-center" style="padding: 20px; background: #f5f5f5; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                    <div style="font-size: 36px; font-weight: bold; color: #333;">${stats.total_sites}</div>
                                    <div style="font-size: 14px; color: #888;">Total Sites</div>
                                    <div style="font-size: 11px; color: #aaa; margin-top: 5px;">
                                        ${stats.site_prefix}${stats.site_min} - ${stats.site_prefix}${stats.site_max}
                                    </div>
                                </div>
                            </div>
                            <div class="col-sm-4">
                                <div class="stat-box text-center" style="padding: 20px; background: #e8f5e9; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                    <div style="font-size: 36px; font-weight: bold; color: #4caf50;">${stats.assigned_count}</div>
                                    <div style="font-size: 14px; color: #888;">Assigned</div>
                                    <div style="font-size: 11px; color: #aaa; margin-top: 5px;">
                                        <a href="/app/site-provisioning?status=Success">View List</a>
                                    </div>
                                </div>
                            </div>
                            <div class="col-sm-4">
                                <div class="stat-box text-center" style="padding: 20px; background: #fff3e0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                    <div style="font-size: 36px; font-weight: bold; color: #ff9800;">${stats.unassigned_count}</div>
                                    <div style="font-size: 14px; color: #888;">Available</div>
                                    <div style="font-size: 11px; color: #aaa; margin-top: 5px;">
                                        <a href="#" onclick="frappe.sites_setup.show_unassigned_sites(); return false;">View Available Sites</a>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="text-center" style="margin-top: 10px;">
                            <a href="/app/site-provisioning/new-site-provisioning-1" class="btn btn-primary btn-sm">
                                + New Site Provisioning
                            </a>
                            <a href="/app/site-provisioning" class="btn btn-default btn-sm" style="margin-left: 10px;">
                                View All Provisioning
                            </a>
                        </div>
                    `;
                    frm.dashboard.add_section(stats_html);
                }
            }
        });
    }
});

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
