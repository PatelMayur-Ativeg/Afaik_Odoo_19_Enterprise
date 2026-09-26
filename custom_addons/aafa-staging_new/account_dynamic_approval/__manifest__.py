# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

{
    "name": "Vendor Bill Dynamic Approval",
    "author": "Rinoy",
    "category": "Account",
    "summary": "Vendor Bill Dynamic Approval",
    "version": "19.0.1.0.1",
    "depends": ["account", "bus"],
    "data": [
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'data/mail_data.xml',
        'views/account_approval_info_view.xml',
        'views/account_approval_config_view.xml',
        'views/account_approval_lines_view.xml',
        'wizard/account_rejection_wizard_view.xml',
        'views/res_config_view.xml',
        'views/batch_payment_approval.xml',
        'views/account_move_view.xml',
        'views/account_payment_view.xml',
        'report/account_report_template.xml',

    ],
    "license": "OPL-1",
    "images": ["static/description/background.png", ],
    "auto_install": False,
    "installable": True,
    "application": True,
}
