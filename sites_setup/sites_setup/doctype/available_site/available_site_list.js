frappe.listview_settings['Available Site'] = {
    hide_name_column: true,
    filters: [['status', '=', 'Available']],

    get_indicator: function(doc) {
        if (doc.status === 'Available') {
            return [__('Available'), 'green', 'status,=,Available'];
        } else if (doc.status === 'Assigned') {
            return [__('Assigned'), 'blue', 'status,=,Assigned'];
        }
    },

    onload: function(listview) {
        // Add button to go to Settings (Single DocType - must use specific name)
        listview.page.add_inner_button(__('Settings'), function() {
            frappe.set_route('Form', 'Sites Setup Settings', 'Sites Setup Settings');
        });

        // Add button to go to Site Provisioning
        listview.page.add_inner_button(__('All Provisioning'), function() {
            frappe.set_route('List', 'Site Provisioning');
        });

        // Add Sync button
        listview.page.add_inner_button(__('Sync Sites'), function() {
            frappe.call({
                method: 'sites_setup.sites_setup.doctype.available_site.available_site.sync_sites',
                freeze: true,
                freeze_message: __('Syncing sites...'),
                callback: function(r) {
                    if (r.message) {
                        listview.refresh();
                    }
                }
            });
        });

        // Add quick provision button
        listview.page.add_inner_button(__('New Provisioning'), function() {
            frappe.new_doc('Site Provisioning');
        }, __('Create'));
    },

    button: {
        show: function(doc) {
            return doc.status === 'Available';
        },
        get_label: function() {
            return __('Provision');
        },
        get_description: function(doc) {
            return __('Create a new provisioning for {0}', [doc.site_name]);
        },
        action: function(doc) {
            frappe.new_doc('Site Provisioning', {
                assigned_site: doc.site_name
            });
        }
    },

    formatters: {
        site_name: function(value) {
            return `<code>${value}</code>`;
        }
    }
};
