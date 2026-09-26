# -*- coding: utf-8 -*-

{
    "name": "Purchase Requisition Custom",
    "summary": "Purchase Requisition Custom",
    "version": "1.2",
    'license': 'OPL-1',
    "category": "Purchase",
    "depends": [
        "purchase",
        "purchase_requisition",
        "analytic",
        "account",
        "purchase_stock",
        "hr",
        "custom_aafa",
        "account_budget",
    ],
    "data": [
        'security/ir.model.access.csv',
        'data/purchase_requisition_sequence.xml',
        'data/res_partner_data.xml',
        'wizard/purchase_order_line_choose_views.xml',
        'views/purchase_inherit_views.xml',
        'views/configuration_view.xml',
        'views/purchase_requisition_view.xml'
    ],
    "assets": {
        "web.assets_backend": [
            "purchase_extension/static/src/fields/choose_reason_popover.js",
            "purchase_extension/static/src/fields/choose_reason_popover.xml",
            "purchase_extension/static/src/fields/choose_reason_popover.scss",
        ],
    },
 
    "installable": True,
    "application": True,
    "auto_install": False,
}
