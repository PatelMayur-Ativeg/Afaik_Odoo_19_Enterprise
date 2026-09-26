{
    "name": "Aafa Reports",
    "summary": "Custom reports for Aafa, including Payment Approval Batch.",
    "version": "19.0.1.0.1",
    "category": "Accounting/Accounting",
    "depends": ["custom_aafa", "account_batch_payment"],
    "data": [
        "report/payment_batch_report_template.xml",
        "report/payment_batch_report.xml",
        "views/account_batch_payment_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": True,
    "license": "LGPL-3",
}
