# -*- coding: utf-8 -*-
from odoo import api, fields, tools, models, _
from odoo.exceptions import UserError, ValidationError


class BudgetApprovalConfig(models.Model):
    _name = 'budget.approval.config'
    _description = 'Budget Approval Configuration'

    name = fields.Char()
    is_boolean = fields.Boolean(string="User Always in CC")
    company_ids = fields.Many2many(
        'res.company', string="Allowed Companies", default=lambda self: self.env.company)
    budget_approval_line = fields.One2many(
        'budget.approval.line', 'budget_approval_config_id')
   

    @api.constrains('budget_approval_line')
    def approval_line_level(self):
        if self.budget_approval_line:
            levels = self.budget_approval_line.mapped('level')
            if len(levels) != len(set(levels)):
                raise ValidationError('Levels must be different!!!')


