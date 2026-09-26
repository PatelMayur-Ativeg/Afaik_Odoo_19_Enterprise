# -*- coding: utf-8 -*-

from odoo import fields, models


class MultiApprovalTypeLine(models.Model):
    _inherit = "multi.approval.type.line"

    signature_label = fields.Char(
        string="Signature Label",
        help="Role printed on the report, for example Checked By or Approved By. "
        "If empty, Approved By is used.",
    )
