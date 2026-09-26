##############################################################################
#
#    Copyright Domiup (<http://domiup.com>).
#
##############################################################################

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class MultiApprovalTypeLine(models.Model):
    _name = "multi.approval.type.line"
    _description = "Approval Type Lines"
    _order = "sequence"

    name = fields.Char(string="Title", required=True)
    user_id = fields.Many2one(string="User", comodel_name="res.users", required=True)
    proxy_line_ids = fields.One2many("multi.approval.proxy.line", 'approval_type_line_id')
    sequence = fields.Integer()
    require_opt = fields.Selection(
        [
            ("Required", "Required"),
            ("Optional", "Optional"),
        ],
        string="Type of Approval",
        default="Required",
    )
    type_id = fields.Many2one(string="Type", comodel_name="multi.approval.type")

    def get_user(self):
        self.ensure_one()
        return self.user_id.id

    def get_proxy_lines(self):
        return self.proxy_line_ids.filtered(
            lambda line: line.start_date <= fields.Datetime.now() <= line.end_date
        )
