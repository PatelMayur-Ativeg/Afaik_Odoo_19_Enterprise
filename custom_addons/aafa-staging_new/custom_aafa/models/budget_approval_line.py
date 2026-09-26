from odoo import api, fields, tools, models, _

class BudgetApprovalLine(models.Model):
    _name = 'budget.approval.line'
    _description = 'Dynamic Budget Approval'

    level=fields.Integer(string="Level",required=True)
    user_ids = fields.Many2many('res.users', string="Users")
    budget_approval_config_id=fields.Many2one('budget.approval.config')
    is_boolean=fields.Boolean()
    label_type = fields.Selection([('cfo_approve', 'CFO Approve'),('coo_approve','COO Approve'),('ceo_approve','CEO Approve')])
    is_send_email = fields.Boolean(string="Send Email", default=True)

