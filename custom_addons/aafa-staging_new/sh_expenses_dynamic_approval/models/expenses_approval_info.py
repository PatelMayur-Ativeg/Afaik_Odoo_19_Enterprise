from odoo import api, fields, tools, models, _

import logging


_logger = logging.getLogger(__name__)

class ExpensesApprovalInfo(models.Model):
    _name = 'sh.expenses.approval.info'
    _description = "Expenses Approval Information"

    level = fields.Integer(string="Approval Level")
    user_ids = fields.Many2many('res.users', string="Users")
    group_ids = fields.Many2many('res.groups', string="Groups")
    status = fields.Boolean(string="Status")
    approval_date = fields.Datetime(string="Approved Date")
    approved_by = fields.Many2one('res.users', string="Approved By")
    hr_expenses_id = fields.Many2one('hr.expense')
    label_type = fields.Selection([('verified_by', 'Verified By'),('supported_by','Supported By'),('reviewed_by','Reviewed By'),('approved_by','Approved By')])



