# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

{
    "name": "Expenses Dynamic Approval | Expenses Order Dynamic Approval | Request For Quotation Dynamic Approval | Dynamic Expenses Approval | Expenses Approval Process | Expenses Order Approval Process",
    "author": "Softhealer Technologies",
    "website": "https://www.softhealer.com",
    "support": "support@softhealer.com",
    "category": "Expensess",
    "summary": "Dynamic Expenses Order Approval,Dynamic Expenses Approval,Expenses Multi Approval,Expenses Order Multiple Approval, Expenses Order Double Approval,RFQ Dynamic Approval,PO Dynamic Approval,PO Multi Approval,RFQ Multi Approval Odoo",
    "description": """This module allows you to set dynamic and multi-level approvals in the request for quotation/Expenses order so each order can be approved by many levels. Expenses orders can be approved based on untaxed/ total amount and approved by particular users or groups they get emails notification about orders that waiting for approval. When a Expenses order/RFQ approves or rejects user gets a notification about it.""",
    "version": "1.0",
    "depends": ['base','hr','hr_expense','account',"bus",'web_domain_field'],
    # "odoo_Expenses_order_line_no"
    "data": [
        'security/ir.model.access.csv',
        'views/expenses_approval_info.xml',
        'views/expenses_approval_config.xml',
        'views/expenses_approval_line.xml',
        'views/expenses_rejection_wizard.xml',
        'views/inherit_hr_expenses.xml',

        # 'views/res_config_setting.xml',
        'data/mail_data.xml',

    ],
    "license": "OPL-1",
    "images": ["static/description/background.png", ],
    "auto_install": False,
    "installable": True,
    "application": True,
    "price": 30,
    "currency": "EUR"
}
