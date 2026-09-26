# -*- coding: utf-8 -*-

from odoo import models


class PurchaseRequestQuotation(models.TransientModel):
    _inherit = "purchase.request.quotation"

    def _get_rfq_values(self):
        vals = super()._get_rfq_values()
        request = self.origin_pr_id
        if request:
            vals["employee_id"] = request.employee_id.id
            vals["department_id"] = request.department_id.id
        return vals
