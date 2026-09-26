##############################################################################
#
#    Copyright Domiup (<http://domiup.com>).
#
##############################################################################

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class MultiApprovalLine(models.Model):
    _name = "multi.approval.line"
    _description = "Approval Line"
    _order = "sequence"

    name = fields.Char(string="Title", required=True)
    user_id = fields.Many2one(string="User", comodel_name="res.users", required=True)
    proxy_user_ids = fields.Many2many(
        'res.users',
        'multi_approval_line_user_rel',
        'multi_approval_line_id',
        'user_id',
        string="Proxy Users"
    )
    sequence = fields.Integer()
    require_opt = fields.Selection(
        [
            ("Required", "Required"),
            ("Optional", "Optional"),
        ],
        string="Type of Approval",
        default="Required",
    )
    approval_id = fields.Many2one(string="Approval", comodel_name="multi.approval")
    state = fields.Selection(
        [
            ("Draft", "Draft"),
            ("Waiting for Approval", "Waiting for Approval"),
            ("Approved", "Approved"),
            ("Refused", "Refused"),
            ("Cancel", "Cancel"),
        ],
        default="Draft",
    )
    refused_reason = fields.Text()
    deadline = fields.Date()
    request_date = fields.Datetime(
        string="Requested On",
        readonly=True,
        copy=False,
        help="When this approver was asked to review the request.",
    )
    approved_date = fields.Datetime(
        string="Approved On",
        readonly=True,
        copy=False,
        help="When this approver approved the request.",
    )
    last_reminder_date = fields.Datetime(
        string="Last Reminder On",
        readonly=True,
        copy=False,
        help="When the last pending-approval reminder email was sent.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        for vals in vals_list:
            if vals.get("state") == "Waiting for Approval":
                vals.setdefault("request_date", now)
            if vals.get("state") == "Approved":
                vals.setdefault("approved_date", now)
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        if vals.get("state") == "Approved":
            vals.setdefault("approved_date", fields.Datetime.now())
        res = super().write(vals)
        if vals.get("state") == "Waiting for Approval":
            missing = self.filtered(lambda line: not line.request_date)
            if missing:
                super(MultiApprovalLine, missing).write(
                    {"request_date": fields.Datetime.now()}
                )
        return res

    # 13.0.1.1
    def set_approved(self):
        self.ensure_one()
        self.write({"state": "Approved", "user_id": self.env.user.id})

    def set_refused(self, reason=""):
        self.ensure_one()
        self.write({"state": "Refused", "refused_reason": reason, "user_id": self.env.user.id})

    def get_proxy_lines(self):
        return self.filtered(
            lambda line: line.start_date <= fields.Datetime.now() <= line.end_date
        )
