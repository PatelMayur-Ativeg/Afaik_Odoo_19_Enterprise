{
    'name': "Purchase Request Report Xlsx",

    'summary': """
        Purchase Request Report Xlsx
        """,

    'description': """
        Purchase Request Report Xlsx
    """,

    'author': "Rinoy",
    'website': "",
    'category': '',
    'version': '1.0',

    # any module necessary for this one to work correctly
    'depends': ['base','purchase_request','report_xlsx'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'wizard/pr_report_wizard.xml',
        'reports/menu_pr_report_xlsx.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
# -*- coding: utf-8 -*-
