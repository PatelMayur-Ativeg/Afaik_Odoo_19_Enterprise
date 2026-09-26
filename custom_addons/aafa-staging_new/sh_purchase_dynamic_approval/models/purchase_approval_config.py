# -*- coding: utf-8 -*-
from odoo import api, fields, tools, models, _
from odoo.exceptions import UserError, ValidationError


class PurchaseApprovalConfig(models.Model):
    _name = 'sh.purchase.approval.config'
    _description = 'Purchase Approval Configuration'

    name = fields.Char()
    pr_category_ids = fields.Many2many(
        comodel_name="purchase.request.category",
        relation="sh_purchase_approval_config_category_rel",
        column1="config_id",
        column2="category_id",
        string="Categories",
        required=True,
    )
    # min_amount = fields.Float(string="Minimum Amount", required=True)
    company_ids = fields.Many2many(
        'res.company', string="Allowed Companies", default=lambda self: self.env.company)
    # currency_ids = fields.Many2many(
    #     'res.currency', string="Allowed Currencies", default=lambda self: self.env.company.currency_id)
    is_boolean = fields.Boolean(string="User Always in CC")
    purchase_approval_line = fields.One2many(
        'sh.purchase.approval.line', 'purchase_approval_config_id')
    primary_approval = fields.Selection([('line_manager', 'Line Manager'),('own_approval', 'Own Approval')], default='line_manager')
    buyer = fields.Many2one('res.users', string="Buyer")

    @api.constrains('purchase_approval_line')
    def approval_line_level(self):
        if self.purchase_approval_line:
            levels = self.purchase_approval_line.mapped('level')
            if len(levels) != len(set(levels)):
                raise ValidationError('Levels must be different!!!')
