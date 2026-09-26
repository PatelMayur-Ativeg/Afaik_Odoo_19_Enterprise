# -*- coding: utf-8 -*-

from odoo import api, fields, models


class PurchaseRequest(models.Model):
    _inherit = "purchase.request"

    purchase_order_ids = fields.One2many(
        "purchase.order",
        "request_id",
        string="RFQs / Purchase Orders",
    )

    def _get_linked_purchase_orders(self):
        self.ensure_one()
        orders = self.purchase_order_ids
        return orders | orders.mapped("alternative_po_ids")

    def _sync_linked_purchase_orders(self):
        """Ensure RFQs, POs and their alternatives all point back to this PR."""
        self.ensure_one()
        orders = self._get_linked_purchase_orders()
        extras = orders.mapped("alternative_po_ids") - self.purchase_order_ids
        if extras:
            extras.write({
                "request_id": self.id,
                "employee_id": self.employee_id.id,
                "department_id": self.department_id.id,
            })
            extras.filtered(lambda po: not po.origin).write({"origin": self.name})
        return self._get_linked_purchase_orders()

    @api.depends("purchase_order_ids", "purchase_order_ids.alternative_po_ids")
    def _compute_purchase_count(self):
        for rec in self:
            rec.purchase_count = len(rec._get_linked_purchase_orders())

    def action_view_purchase_order(self):
        action = self.env["ir.actions.actions"]._for_xml_id("purchase.purchase_rfq")
        order_ids = self._sync_linked_purchase_orders()
        if len(order_ids) > 1:
            action["domain"] = [("id", "in", order_ids.ids)]
        elif order_ids:
            action["views"] = [
                (self.env.ref("purchase.purchase_order_form").id, "form")
            ]
            action["res_id"] = order_ids.id
        else:
            action["domain"] = [("id", "=", False)]
        action["context"] = {
            "default_request_id": self.id,
            "default_origin": self.name,
            "default_employee_id": self.employee_id.id,
            "default_department_id": self.department_id.id,
        }
        return action
