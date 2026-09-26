from odoo import models, fields, api, _
from datetime import datetime, time, date, timedelta

class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'
    
    total_real_amount = fields.Monetary(string="Total Real Amount",compute='_sum_real_amt')
    
    @api.depends('budget_line_ids.real_amount')
    def _sum_real_amt(self):
        for order in self:
            amount_remain = 0.0
            for line in order.budget_line_ids:
                amount_remain += line.real_amount
            currency = order.currency_id or order.partner_id.property_purchase_currency_id or self.env.company.currency_id
            order.update({
                'total_real_amount': currency.round(amount_remain),
            })