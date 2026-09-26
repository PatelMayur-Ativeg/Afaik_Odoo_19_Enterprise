{
    "name": "Approval Report Signatures",
    "version": "19.0.1.0.1",
    "category": "Approvals",
    "summary": "Print creator and approver signatures on selected reports from approval type configuration.",
    "author": "Aafa",
    "license": "LGPL-3",
    "depends": [
        "web",
        "multi_level_approval_configuration",
    ],
    "data": [
        "views/multi_approval_type_views.xml",
        "views/res_users_views.xml",
        "report/approval_signature_templates.xml",
    ],
    "installable": True,
    "application": False,
}
