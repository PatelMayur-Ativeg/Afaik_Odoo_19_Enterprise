# -*- coding: utf-8 -*-

from odoo import models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def _get_rfq_compare_group(self):
        """Return this PO plus any alternative RFQs in the same compare group."""
        self.ensure_one()
        alternatives = (
            self.alternative_po_ids
            if "alternative_po_ids" in self._fields
            else self.env["purchase.order"]
        )
        return self | alternatives

    def _is_rfq_chosen_order(self):
        """A chosen RFQ still has at least one comparable line with quantity."""
        self.ensure_one()
        return any(
            not line.display_type and line.product_qty > 0 for line in self.order_line
        )

    def _get_chosen_rfq_orders(self):
        """POs selected in Compare Order Lines; fallback to the requested PO."""
        self.ensure_one()
        group = self._get_rfq_compare_group()
        chosen = group.filtered(lambda po: po._is_rfq_chosen_order())
        return chosen or self

    def _get_eliminated_rfq_orders(self):
        """Alternative RFQs that were not chosen. Empty when there are no alternatives."""
        self.ensure_one()
        group = self._get_rfq_compare_group()
        if group == self:
            return self.browse()
        return group - self._get_chosen_rfq_orders()

    def _get_all_compared_rfq_orders(self):
        """Every RFQ in the Compare Order Lines group, chosen or eliminated."""
        self.ensure_one()
        return self._get_rfq_compare_group()

    def _get_rfq_comparison_lines(self):
        """Comparable purchase lines across this RFQ and its alternatives."""
        self.ensure_one()
        lines = self._get_rfq_compare_group().mapped("order_line").filtered(
            lambda line: not line.display_type
        )
        return lines.sorted(
            lambda line: (
                line.product_id.display_name or "",
                line.order_id.name or "",
                line.id,
            )
        )

    def _get_rfq_comparison_groups(self):
        """Group comparison lines by product for the QWeb report."""
        groups = []
        product = None
        bucket = self.env["purchase.order.line"]
        for line in self._get_rfq_comparison_lines():
            if product is None or line.product_id != product:
                if product is not None:
                    groups.append((product, bucket))
                product = line.product_id
                bucket = line
            else:
                bucket |= line
        if product is not None:
            groups.append((product, bucket))
        return groups

    def _get_rfq_selection_reasons(self):
        """Unique choose reasons from selected comparison lines."""
        self.ensure_one()
        reasons = []
        seen = set()
        lines = self._get_rfq_comparison_lines()
        chosen = lines.filtered(lambda line: line.product_qty > 0)
        for line in chosen or lines:
            reason = (line.choose_reason or "").strip() if "choose_reason" in line._fields else ""
            if reason and reason not in seen:
                seen.add(reason)
                reasons.append(reason)
        return reasons
