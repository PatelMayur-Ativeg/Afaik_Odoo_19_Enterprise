{
    "name": "Approval Request Mail Attachments",
    "version": "19.0.1.0.0",
    "category": "Approvals",
    "summary": "Configure dynamic attachments on approval request emails per approval type.",
    "author": "Aafa",
    "license": "LGPL-3",
    "depends": [
        "multi_level_approval_configuration",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/mail_approval_lines_templates.xml",
        "views/multi_approval_type_views.xml",
    ],
    "installable": True,
    "application": False,
}
