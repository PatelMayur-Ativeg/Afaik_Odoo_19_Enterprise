##############################################################################
#
#    Copyright Domiup (<http://domiup.com>).
#
##############################################################################

from odoo import api, fields, models


class TestApproval(models.TransientModel):
    _name = "test.approval"
    _description = "Test Approval"

    name = fields.Char()
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("to_approve", "To Approved"),
            ("to_approve_2", "To Approved 2"),
            ("approve", "Approved"),
            ("refuse", "Refused"),
        ]
    )
    user_id = fields.Many2one("res.users")
    field_1 = fields.Char()
    field_2 = fields.Char()
    field_3 = fields.Char(store=True, compute="_compute_field_3")

    @api.depends("field_2")
    def _compute_field_3(self):
        for rec in self:
            rec.field_3 = f"{rec.field_2} cloned"

    def btn_approve(self):
        self.filtered(lambda r: r.state == "to_approve").state = "approve"

    def btn_refuse(self):
        self.filtered(lambda r: r.state == "to_approve").state = "refuse"
