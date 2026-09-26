# -*- coding: utf-8 -*-

from odoo import models


class PurchaseRequisitionCreateAlternative(models.TransientModel):
    _inherit = 'purchase.requisition.create.alternative'

    def _get_alternative_values(self):
        vals = super()._get_alternative_values()
        origin_po = self.origin_po_id
        extra = {
            'origin': origin_po.origin,
            'employee_id': origin_po.employee_id.id,
            'department_id': origin_po.department_id.id,
            'custom_requisition_id': origin_po.custom_requisition_id.id,
            'po_categ_id': origin_po.po_categ_id.id,
        }
        records = vals if isinstance(vals, list) else [vals]
        for val in records:
            val.update(extra)
        return vals
