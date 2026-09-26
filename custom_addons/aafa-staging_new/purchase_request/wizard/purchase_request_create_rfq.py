# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from datetime import datetime

import logging


_logger = logging.getLogger(__name__)

class PurchaseRequestQuotation(models.TransientModel):
    _name = 'purchase.request.quotation'
    _description = 'Wizard to preset values for RFQ'

    origin_pr_id = fields.Many2one(
        'purchase.request', help="The original PO that this alternative PO is being created for."
    )
    partner_id = fields.Many2one(
        'res.partner', string='Vendor', required=True,
        help="Choose a vendor for RFQ")


    def action_create_rfq(self):
        vals = self._get_rfq_values()
        alt_po = self.env['purchase.order'].create(vals)

        # return {
        #     'type': 'ir.actions.act_window',
        #     'view_mode': 'form',
        #     'res_model': 'purchase.request',
        #     'res_id': self.id,
        #     'context': {
        #         'active_id': self.id,
        #     },
        # }

    def _get_rfq_values(self):
        vals = {
            'date_order': datetime.now(),
            'partner_id': self.partner_id.id,
            'request_id': self.origin_pr_id.id,
            'request_new_product':True,
            'origin':self.origin_pr_id.name,
            'state':'draft'
            # 'user_id': self.origin_pr_id.user_id.id,
            # 'dest_address_id': self.origin_po_id.dest_address_id.id,
        }
        request = self.origin_pr_id
        if request:
            vals['order_line'] = [
                (0, 0, {
                    "display_type": 'line_note',
                    "name": line.desc,
                    "product_qty": 0,
                })
                for line in request.new_line_ids
            ]
        return vals
