##############################################################################
#
#    Copyright Domiup (<http://domiup.com>).
#
##############################################################################

import uuid

from odoo import api, fields, models


class MultiApprovalToken(models.Model):
    _name = "multi.approval.token"
    _description = "Approval Public Token"
    _order = "id desc"

    approval_id = fields.Many2one(
        "multi.approval",
        string="Approval",
        required=True,
        ondelete="cascade",
        index=True,
    )
    line_id = fields.Many2one(
        "multi.approval.line",
        string="Approval Line",
        required=True,
        ondelete="cascade",
        index=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Approver",
        required=True,
        ondelete="cascade",
        index=True,
    )
    token = fields.Char(
        string="Token",
        required=True,
        copy=False,
        index=True,
        default=lambda self: str(uuid.uuid4()),
    )
    state = fields.Selection(
        [
            ("active", "Active"),
            ("used", "Used"),
            ("revoked", "Revoked"),
        ],
        default="active",
        required=True,
        index=True,
    )
    used_date = fields.Datetime(copy=False)
    approve_url = fields.Char(compute="_compute_urls")
    reject_url = fields.Char(compute="_compute_urls")

    _token_uniq = models.Constraint(
        "UNIQUE(token)",
        "The approval token must be unique!",
    )

    @api.depends("token", "approval_id.public_uuid")
    def _compute_urls(self):
        base_url = (
            self.env["ir.config_parameter"].sudo().get_param("web.base.url") or ""
        ).rstrip("/")
        for rec in self:
            if rec.token and rec.approval_id.public_uuid:
                prefix = (
                    f"{base_url}/multi_approval/"
                    f"{rec.approval_id.public_uuid}/{rec.token}"
                )
                rec.approve_url = f"{prefix}/approve"
                rec.reject_url = f"{prefix}/reject"
            else:
                rec.approve_url = False
                rec.reject_url = False

    def mark_used(self):
        self.write({"state": "used", "used_date": fields.Datetime.now()})

    def mark_revoked(self):
        self.write({"state": "revoked"})
