# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

{
    "name": "Purchase Dynamic Approval | Purchase Order Dynamic Approval | Request For Quotation Dynamic Approval | Dynamic Purchase Approval | Purchase Approval Process | Purchase Order Approval Process",
    "author": "Softhealer Technologies",
    "website": "https://www.softhealer.com",
    "support": "support@softhealer.com",
    "category": "Purchases",
    "summary": "Dynamic Purchase Order Approval,Dynamic Purchase Approval,Purchase Multi Approval,Purchase Order Multiple Approval, Purchase Order Double Approval,RFQ Dynamic Approval,PO Dynamic Approval,PO Multi Approval,RFQ Multi Approval Odoo",
    "description": """This module allows you to set dynamic and multi-level approvals in the request for quotation/purchase order so each order can be approved by many levels. Purchase orders can be approved based on untaxed/ total amount and approved by particular users or groups they get emails notification about orders that waiting for approval. When a purchase order/RFQ approves or rejects user gets a notification about it.""",
    "version": "1.2",
    "depends": ['base',"purchase_request", "bus",'web_domain_field',"stock_analytic","uom","product"],
    # "odoo_purchase_order_line_no"
    "data": [
        'security/ir.model.access.csv',
        'security/security.xml',
        'data/mail_data.xml',
        'views/purchase_approval_line.xml',
        'views/purchase_approval_config.xml',
        'views/res_config_setting.xml',
        'views/approval_info.xml',
        'views/rejection_wizard.xml',
        'views/inherit_purchase_order.xml',

    ],
    "license": "OPL-1",
    "images": ["static/description/background.png", ],
    "auto_install": False,
    "installable": True,
    "application": True,
    "price": 30,
    "currency": "EUR"
}
