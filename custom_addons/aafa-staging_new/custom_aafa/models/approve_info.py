from odoo import api, fields, tools, models, _

import logging


_logger = logging.getLogger(__name__)

class BudgetApprovalInfo(models.Model):
    _name = 'budget.approval.info'
    _description = "Approval Information"

    level = fields.Integer(string="Approval Level")
    user_ids = fields.Many2many('res.users', string="Users")
    status = fields.Boolean(string="Status")
    approval_date = fields.Datetime(string="Approved Date")
    approved_by = fields.Many2one('res.users', string="Approved By")
    cross_budget_id = fields.Many2one('budget.analytic')
    label_type = fields.Selection([('cfo_approve', 'CFO Approve'),('coo_approve','COO Approve'),('ceo_approve','CEO Approve')])
