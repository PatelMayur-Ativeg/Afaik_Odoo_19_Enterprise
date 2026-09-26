# -*- coding: utf-8 -*-

from odoo import models


class MultiApprovalType(models.Model):
    _inherit = "multi.approval.type"

    def action_load_po_rfq_mail_attachments(self):
        """Create the standard RFQ comparison attachment lines if missing."""
        report_po = self.env.ref(
            "purchase.action_report_purchase_order",
            raise_if_not_found=False,
        )
        report_cmp = self.env.ref(
            "multi_level_approval_mail_attachment_purchase.action_report_purchase_rfq_comparison",
            raise_if_not_found=False,
        )
        defaults = [
            {
                "name": "Chosen RFQ Purchase Order PDF",
                "source": "po_chosen_report",
                "sequence": 10,
                "report_id": report_po.id if report_po else False,
            },
            {
                "name": "Eliminated RFQ Chatter Attachments",
                "source": "po_eliminated_chatter",
                "sequence": 20,
            },
            {
                "name": "All Compared RFQ Chatter Attachments",
                "source": "po_all_rfq_chatter",
                "sequence": 25,
            },
            {
                "name": "RFQ Comparison Sheet PDF",
                "source": "po_comparison_sheet",
                "sequence": 30,
                "report_id": report_cmp.id if report_cmp else False,
            },
        ]
        Line = self.env["multi.approval.mail.attachment.line"]
        for rec in self:
            existing = set(rec.mail_attachment_line_ids.mapped("source"))
            vals_list = [
                dict(vals, type_id=rec.id)
                for vals in defaults
                if vals["source"] not in existing
            ]
            if vals_list:
                Line.create(vals_list)
        return True

    def action_load_batch_payment_mail_attachments(self):
        Line = self.env["multi.approval.mail.attachment.line"]
        for rec in self:
            if rec.model_id != "account.batch.payment":
                continue
            existing = set(rec.mail_attachment_line_ids.mapped("source"))
            if "batch_payment_move_chatter" in existing:
                continue
            Line.create(
                {
                    "type_id": rec.id,
                    "name": "Linked payment invoice/bill chatter attachments",
                    "source": "batch_payment_move_chatter",
                    "sequence": 10,
                }
            )
        return True
