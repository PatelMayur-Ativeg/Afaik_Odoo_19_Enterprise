# -*- coding: utf-8 -*-
import logging

from odoo import api, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class MultiApprovalMailAttachmentLine(models.Model):
    _inherit = "multi.approval.mail.attachment.line"

    @api.model
    def _selection_source(self):
        return super()._selection_source() + [
            ("po_chosen_report", "Chosen RFQ Purchase Order PDF"),
            ("po_eliminated_chatter", "Eliminated RFQ chatter attachments"),
            ("po_all_rfq_chatter", "All compared RFQ chatter attachments"),
            ("po_comparison_sheet", "RFQ Comparison Sheet PDF"),
            (
                "batch_payment_move_chatter",
                "Payment batch invoice/bill chatter attachments",
            ),
        ]

    @api.onchange("source")
    def _onchange_source(self):
        if self.source == "po_chosen_report" and not self.report_id:
            self.report_id = self.env.ref(
                "purchase.action_report_purchase_order",
                raise_if_not_found=False,
            )
        elif self.source == "po_comparison_sheet":
            self.report_id = self.env.ref(
                "multi_level_approval_mail_attachment_purchase.action_report_purchase_rfq_comparison",
                raise_if_not_found=False,
            )

    @api.constrains("source", "report_id")
    def _check_po_source_options(self):
        for rec in self:
            if rec.source == "po_chosen_report" and not rec.report_id:
                raise ValidationError(
                    self.env._(
                        "A report is required on attachment line '%s'."
                    )
                    % (rec.name or rec.source)
                )

    def _get_purchase_origin(self, request):
        origin = self._get_origin(request)
        if not origin or origin._name != "purchase.order":
            return self.env["purchase.order"]
        return origin

    def _collect_po_chosen_report(self, request):
        origin = self._get_purchase_origin(request)
        if not origin:
            return self.env["ir.attachment"]
        chosen = origin._get_chosen_rfq_orders()
        return self._render_report_attachments(chosen, request)

    def _collect_po_eliminated_chatter(self, request):
        origin = self._get_purchase_origin(request)
        if not origin:
            return self.env["ir.attachment"]
        eliminated = origin._get_eliminated_rfq_orders()
        attachments = self.env["ir.attachment"]
        for order in eliminated:
            attachments |= self._copy_attachments_for_request(
                self._get_record_all_attachments(order),
                request,
                name_prefix=order.display_name,
            )
        return attachments

    def _collect_po_all_rfq_chatter(self, request):
        origin = self._get_purchase_origin(request)
        if not origin:
            return self.env["ir.attachment"]
        attachments = self.env["ir.attachment"]
        for order in origin._get_all_compared_rfq_orders():
            attachments |= self._copy_attachments_for_request(
                self._get_record_all_attachments(order),
                request,
                name_prefix=order.display_name,
            )
        return attachments

    def _collect_po_comparison_sheet(self, request):
        origin = self._get_purchase_origin(request)
        if not origin:
            return self.env["ir.attachment"]
        report = self.report_id or self.env.ref(
            "multi_level_approval_mail_attachment_purchase.action_report_purchase_rfq_comparison",
            raise_if_not_found=False,
        )
        return self._render_report_attachments(origin, request, report=report)

    def _get_batch_payment_origin(self, request):
        origin = self._get_origin(request)
        if not origin or origin._name != "account.batch.payment":
            return self.env["account.batch.payment"]
        return origin

    def _get_batch_payment_related_moves(self, origin):
        moves = self.env["account.move"]
        if not origin or origin._name != "account.batch.payment":
            return moves
        payments = origin.sudo().payment_ids
        if not payments:
            return moves
        paths = (
            "payment_invoice_ids.invoice_id",
            "payment_reversal_ids.invoice_id",
            "invoice_ids",
            "reconciled_invoice_ids",
            "reconciled_bill_ids",
        )
        for path in paths:
            root_field = path.split(".", 1)[0]
            if root_field not in payments._fields:
                continue
            try:
                moves |= payments.mapped(path)
            except Exception:
                _logger.exception(
                    "Failed to map '%s' on batch payments for attachment line %s",
                    path,
                    self.display_name,
                )
        return moves.exists()

    def _collect_batch_payment_move_chatter(self, request):
        origin = self._get_batch_payment_origin(request)
        attachments = self.env["ir.attachment"]
        for move in self._get_batch_payment_related_moves(origin):
            attachments |= self._copy_attachments_for_request(
                self._get_record_all_attachments(move),
                request,
                name_prefix=move.display_name,
            )
        return attachments
