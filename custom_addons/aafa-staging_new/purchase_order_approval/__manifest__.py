# -*- coding: utf-8 -*-
{
    'name': "Purchase Approvals",
    'version': '1.0',
    'summary': """
        Dynamic Approval Management Application""",
    'sequence': 4,

    'description': """
        Every purchase order can have multiple approvals  through this application
    """,

    'author': "soyeb",
    'website': "http://primeminds.co",
    'depends': ['base', 'purchase', 'sale', 'purchase_requisition', 'product', 'analytic'],
    'auto_install': False,
    'installable': True,
    'application': True,
    'data': [
        'security/ir.model.access.csv',
        'views/approval_master.xml',
        'views/purchase_order_inherit.xml',
    ],

    'demo': [
    ],
}
