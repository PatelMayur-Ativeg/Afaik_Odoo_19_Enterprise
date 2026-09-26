# -*- coding: utf-8 -*-

from odoo import api, models


class PurchaseRequisitionCreateAlternative(models.TransientModel):
    _inherit = "purchase.requisition.create.alternative"

    def _get_alternative_values(self):
        vals = super()._get_alternative_values()
        origin_po = self.origin_po_id
        extra = {
            "request_id": origin_po.request_id.id,
            "request_new_product": origin_po.request_new_product,
        }
        records = vals if isinstance(vals, list) else [vals]
        for val in records:
            val.update(extra)
        return vals

    @api.model
    def _get_alternative_line_value(self, order_line, product_tmpl_ids_with_description):
        res_line = super()._get_alternative_line_value(
            order_line, product_tmpl_ids_with_description
        )
        res_line["request_line_id"] = order_line.request_line_id.id
        return res_line
