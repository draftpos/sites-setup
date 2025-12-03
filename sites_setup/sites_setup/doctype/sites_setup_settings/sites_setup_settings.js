frappe.ui.form.on('Sites Setup Settings', {
    refresh: function(frm) {
        // Show dashboard with site stats
        frm.trigger('show_sites_dashboard');

        // Add Sync Sites button
        frm.add_custom_button(__('Sync Sites'), function() {
            frappe.call({
                method: 'sites_setup.sites_setup.doctype.available_site.available_site.sync_sites',
                freeze: true,
                freeze_message: __('Syncing sites...'),
                callback: function(r) {
                    if (r.message) {
                        frm.reload_doc();
                    }
                }
            });
        }, __('Actions'));

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
                                <a href="/app/available-site?status=Assigned" style="text-decoration: none;">
                                    <div class="stat-box text-center" style="padding: 20px; background: #e8f5e9; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); cursor: pointer;">
                                        <div style="font-size: 36px; font-weight: bold; color: #4caf50;">${stats.assigned_count}</div>
                                        <div style="font-size: 14px; color: #888;">Assigned</div>
                                        <div style="font-size: 11px; color: #4caf50; margin-top: 5px;">
                                            Click to view
                                        </div>
                                    </div>
                                </a>
                            </div>
                            <div class="col-sm-4">
                                <a href="/app/available-site?status=Available" style="text-decoration: none;">
                                    <div class="stat-box text-center" style="padding: 20px; background: #fff3e0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); cursor: pointer;">
                                        <div style="font-size: 36px; font-weight: bold; color: #ff9800;">${stats.unassigned_count}</div>
                                        <div style="font-size: 14px; color: #888;">Available</div>
                                        <div style="font-size: 11px; color: #ff9800; margin-top: 5px;">
                                            Click to view
                                        </div>
                                    </div>
                                </a>
                            </div>
                        </div>
                        <div class="text-center" style="margin-top: 10px;">
                            <a href="/app/site-provisioning/new" class="btn btn-primary btn-sm">
                                + New Site Provisioning
                            </a>
                            <a href="/app/site-provisioning" class="btn btn-default btn-sm" style="margin-left: 10px;">
                                View All Provisioning
                            </a>
                            <a href="/app/available-site" class="btn btn-default btn-sm" style="margin-left: 10px;">
                                View All Sites
                            </a>
                        </div>
                    `;
                    frm.dashboard.add_section(stats_html);
                }
            }
        });
    }
});
