from odoo import api, fields, tools, models, _
from datetime import datetime
import json
import logging


_logger = logging.getLogger(__name__)

class PurchaseRequestLine(models.Model):
    _inherit = 'purchase.request.line'



    vendor_id_domain = fields.Char(
        compute="_oe_compute_vendor_id",
        readonly=True,
        store=False,
    )

    @api.depends('requisition_action')
    def _oe_compute_vendor_id(self):
        for rec in self:
            if rec.requisition_action in ('partial','purchase_order'):
                rec.vendor_id_domain = json.dumps(
                    [('id', 'in', rec.product_id.seller_ids.mapped('partner_id').ids)]
                )
            else:
                rec.vendor_id_domain = []