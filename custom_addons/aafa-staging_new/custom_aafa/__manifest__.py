{
    "name": "Aafa Custom.",
    "summary": "Aafa Custom for Purchase ,",
    'version': '1.1',
    "category": "Aafa Custom for Purchase ,",
    'depends': ['base', 'web', 'contacts', 'sale_management', 'purchase', 'stock', 'account', 'sale_stock', 'product',
                'account_budget', 'hr', 'hr_expense', 'account_batch_payment'],

    "data": [
        'data/vendor_sequence.xml',
        'security/vendor_approver_security.xml',
        'security/ir.model.access.csv',
        'data/aafa_vendor_option_data.xml',
        # 'data/transaction_type_data.xml',
        'views/aafa_vendor_option_views.xml',
        'views/res_partner_inherit_views.xml',
        'views/crossovered_budget_inherit.xml',
        'views/account_inherit.xml',
        'views/account_journal_views.xml',
        'views/account_move_views.xml',
        'views/inherited_res_user.xml',
        'report/local_purchase_report_template_vat.xml',
        'report/local_purchase_report_template.xml',
        'report/local_purchase_report.xml',
        "views/expense.xml",
        "views/account_payment_inherit.xml",
        "views/account_batch_payment_inherit.xml",
        "views/purchase_order_views.xml",
        'views/budget_approval_config.xml',
        'views/budget_approval_line.xml',
        'views/approve_info.xml',
        'data/mail_data.xml',

    ],
    "assets": {
        "web.assets_backend": [
            "custom_aafa/static/src/views/fields/many2one/many2one_create_edit.js",
        ],
    },
    "application": True,
    "installable": True,
    'auto_install': True,

}
