# -*- coding: utf-8 -*-

from odoo import _, api, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("request_id"):
                request = self.env["purchase.request"].browse(vals["request_id"])
                vals.setdefault("employee_id", request.employee_id.id)
                vals.setdefault("department_id", request.department_id.id)
                if request.name and not vals.get("origin"):
                    vals["origin"] = request.name
        return super().create(vals_list)

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
        if self.custom_requisition_id:
            return {
                "type": "ir.actions.act_window",
                "name": _("Purchase Requisition"),
                "res_model": "material.purchase.requisition",
                "view_mode": "form",
                "res_id": self.custom_requisition_id.id,
            }
        return super().action_view_purchase_request()
