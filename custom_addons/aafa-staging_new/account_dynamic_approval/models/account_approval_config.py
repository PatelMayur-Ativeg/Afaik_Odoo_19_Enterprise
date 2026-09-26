# -*- coding: utf-8 -*-
from odoo import api, fields, tools, models, _
from odoo.exceptions import UserError, ValidationError


class AccountApprovalConfig(models.Model):
    _name = 'sh.account.approval.config'
    _description = 'Account Approval Configuration'

    name = fields.Char()
    min_amount = fields.Float(string="Minimum Amount", required=True)
    company_ids = fields.Many2many(
        'res.company', string="Allowed Companies", default=lambda self: self.env.company)
    is_boolean = fields.Boolean(string="User Always in CC")
    account_approval_line = fields.One2many(
        'sh.account.approval.line', 'account_approval_config_id')
    approval_type = fields.Selection([
            ('approval', 'Approval'),
            ('non_approval', 'Non_Approval')],)


    @api.constrains('account_approval_line')
    def approval_line_level(self):
        if self.account_approval_line:
            levels = self.account_approval_line.mapped('level')
            if len(levels) != len(set(levels)):
                raise ValidationError('Levels must be different!!!')


class PaymentApprovalConfig(models.Model):
    _name = 'sh.payment.approval.config'
    _description = 'Payment Approval Configuration'

    name = fields.Char()
    min_amount = fields.Float(string="Minimum Amount", required=True)
    company_ids = fields.Many2many(
        'res.company', string="Allowed Companies", default=lambda self: self.env.company)
    is_boolean = fields.Boolean(string="User Always in CC")
    payment_approval_line = fields.One2many(
        'sh.payment.approval.line', 'payment_approval_config_id')

    @api.constrains('payment_approval_line')
    def approval_line_level(self):
        if self.payment_approval_line:
            levels = self.payment_approval_line.mapped('level')
            if len(levels) != len(set(levels)):
                raise ValidationError('Levels must be different!!!')
            

class BatchPaymentApprovalConfig(models.Model):
    _name = 'sh.batch.payment.approval.config'
    _description = 'Batch Payment Approval Configuration'

    name = fields.Char()
    # min_amount = fields.Float(string="Minimum Amount", required=True)
    company_ids = fields.Many2many(
        'res.company', string="Allowed Companies", default=lambda self: self.env.company)
    is_boolean = fields.Boolean(string="User Always in CC")
    payment_approval_line = fields.One2many(
        'sh.batch.payment.approval.line', 'batch_payment_approval_config_id')

    @api.constrains('payment_approval_line')
    def approval_line_level(self):
        if self.payment_approval_line:
            levels = self.payment_approval_line.mapped('level')
            if len(levels) != len(set(levels)):
                raise ValidationError('Levels must be different!!!')