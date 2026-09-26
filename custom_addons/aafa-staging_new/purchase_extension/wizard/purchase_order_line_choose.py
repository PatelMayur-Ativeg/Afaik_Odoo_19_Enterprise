# -*- coding: utf-8 -*-

from odoo import fields, models


class PurchaseOrderLineChooseWizard(models.TransientModel):
    _name = 'purchase.order.line.choose.wizard'
    _description = 'Choose Purchase Order Line Reason'

    line_id = fields.Many2one(
        'purchase.order.line',
        string="Order Line",
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(related='line_id.product_id', readonly=True)
    partner_id = fields.Many2one(related='line_id.partner_id', string="Vendor", readonly=True)
    reason = fields.Text(string="Reason", required=True)

    def action_confirm(self):
        self.ensure_one()
        self.line_id.action_choose_confirm(self.reason)
        return {'type': 'ir.actions.act_window_close'}
