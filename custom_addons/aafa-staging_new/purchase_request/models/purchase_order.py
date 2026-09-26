# Copyright 2018-2019 ForgeFlow, S.L.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from odoo import _, fields, models
import logging


_logger = logging.getLogger(__name__)

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    request_id = fields.Many2one('purchase.request')
    request_new_product = fields.Boolean(default=False)
    is_rfq_prev = fields.Boolean(default=False)

    def write(self, values):
        if 'state' in values:
            if values.get('state') == 'done' and self.state == 'draft':
                values['is_rfq_prev'] = True
        return super(PurchaseOrder, self).write(values)

    def button_unlock(self):
        if self.is_rfq_prev:
            self.write({'state': 'draft', 'is_rfq_prev':False})
        else:
            self.write({'state': 'purchase'})

    def action_view_purchase_request(self):
        self.ensure_one()
        if self.request_id:
            return {
                "type": "ir.actions.act_window",
                "name": _("Purchase Request"),
                "res_model": "purchase.request",
                "view_mode": "form",
                "res_id": self.request_id.id,
            }
        try:
            return super().action_view_purchase_request()
        except AttributeError:
            return True

class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    request_line_id = fields.Many2one('purchase.request.line')
    request_new_product = fields.Boolean(related='order_id.request_new_product')

