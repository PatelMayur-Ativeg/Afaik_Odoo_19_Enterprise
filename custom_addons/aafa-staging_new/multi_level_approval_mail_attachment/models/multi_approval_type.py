# -*- coding: utf-8 -*-

from odoo import fields, models


class MultiApprovalType(models.Model):
    _inherit = "multi.approval.type"

    mail_attachment_line_ids = fields.One2many(
        "multi.approval.mail.attachment.line",
        "type_id",
        string="Request Mail Attachments",
        copy=True,
        help="Files collected from the origin document and attached to the "
        "approval request email. The mail template stays the same; only "
        "these lines change per type.",
    )
