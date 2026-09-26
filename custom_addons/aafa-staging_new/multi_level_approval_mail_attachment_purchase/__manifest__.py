{
    "name": "Approval Request Mail Attachments - Purchase",
    "version": "19.0.1.0.2",
    "category": "Approvals",
    "summary": "Purchase RFQ and payment-batch invoice/bill attachments for approval request emails.",
    "author": "Aafa",
    "license": "LGPL-3",
    "depends": [
        "multi_level_approval_mail_attachment",
        "purchase",
        "purchase_requisition",
        "purchase_extension",
        "account_batch_payment",
    ],
    "data": [
        "report/purchase_comparison_templates.xml",
        "report/purchase_comparison_report.xml",
        "views/multi_approval_type_views.xml",
    ],
    "installable": True,
    "application": False,
}
