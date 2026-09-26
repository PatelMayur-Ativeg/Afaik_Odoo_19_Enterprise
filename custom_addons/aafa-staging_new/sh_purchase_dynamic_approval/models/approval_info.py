from odoo import api, fields, tools, models, _

import logging

_logger = logging.getLogger(__name__)


class ApprovalInfo(models.Model):
    _name = 'sh.approval.info'
    _description = "Approval Information"

    level = fields.Integer(string="Approval Level")
    user_ids = fields.Many2many('res.users', string="Users")
    group_ids = fields.Many2many('res.groups', string="Groups")
    status = fields.Boolean(string="Status")
    approval_date = fields.Datetime(string="Approved Date")
    approved_by = fields.Many2one('res.users', string="Approved By")
    purchase_request_id = fields.Many2one('purchase.request')
    label_type = fields.Selection(
        [('verified_by', 'Verified By'), ('supported_by', 'Supported By'), ('reviewed_by', 'Reviewed By'),
         ('approved_by', 'Approved By')])
    purchase_approval_line_id = fields.Many2one('sh.purchase.approval.line', 'Approval Line')
    show_in_report = fields.Boolean("Show in report", related="purchase_approval_line_id.show_in_report")
