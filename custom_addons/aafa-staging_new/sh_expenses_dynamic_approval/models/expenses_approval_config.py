# -*- coding: utf-8 -*-
from odoo import api, fields, tools, models, _
from odoo.exceptions import UserError, ValidationError


class ExpensesApprovalConfig(models.Model):
    _name = 'sh.expenses.approval.config'
    _description = 'Expenses Approval Configuration'

    name = fields.Char()
    company_ids = fields.Many2many(
        'res.company', string="Allowed Companies", default=lambda self: self.env.company)
    is_boolean = fields.Boolean(string="User Always in CC")
    expenses_approval_line = fields.One2many(
        'sh.expenses.approval.line', 'expenses_approval_config_id')
    primary_approval = fields.Selection([('line_manager', 'Line Manager'),('own_approval', 'Own Approval')], default='line_manager')

    @api.constrains('expenses_approval_line')
    def approval_line_level(self):
        if self.expenses_approval_line:
            levels = self.expenses_approval_line.mapped('level')
            if len(levels) != len(set(levels)):
                raise ValidationError('Levels must be different!!!')
