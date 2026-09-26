from odoo import models, _
from odoo.tools import html2plaintext


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def _get_batch_report_memo(self):
        self.ensure_one()
        if "memo" in self._fields and self.memo:
            return self.memo
        return self.payment_reference or ""

    def _is_customer_payment(self):
        self.ensure_one()
        return self.partner_type == "customer" or self.payment_type == "inbound"

    def _get_payment_report_labels(self):
        self.ensure_one()
        if self._is_customer_payment():
            return {
                "partner": _("Customer"),
                "partner_name": _("Customer Name"),
                "partner_info": _("Customer Information"),
                "doc_section": _("Invoice Reconciliation"),
                "doc_no": _("Invoice No."),
                "doc_date": _("Invoice Date"),
                "doc_amount": _("Payment Amount"),
                "doc_description": _("Invoice Description"),
                "empty_docs": _("No invoices allocated to this payment."),
            }
        return {
            "partner": _("Vendor"),
            "partner_name": _("Vendor Name"),
            "partner_info": _("Vendor Information"),
            "doc_section": _("Bill Reconciliation"),
            "doc_no": _("Bill No."),
            "doc_date": _("Bill Date"),
            "doc_amount": _("Payment Amount"),
            "doc_description": _("Bill Description"),
            "empty_docs": _("No bills allocated to this payment."),
        }

    def _get_batch_report_bank_details(self):
        self.ensure_one()
        bank = self.partner_bank_id
        if not bank and self.partner_id:
            bank = self.partner_id.bank_ids[:1]
        beneficiary = ""
        if bank:
            if "acc_holder_name" in bank._fields and bank.acc_holder_name:
                beneficiary = bank.acc_holder_name
            elif bank.partner_id:
                beneficiary = bank.partner_id.name or ""
        return {
            "beneficiary_name": beneficiary or (self.partner_id.name or ""),
            "iban": bank.acc_number if bank else "",
            "currency": self.currency_id.name or "",
        }

    def _get_move_report_description(self, move):
        if move.narration:
            description = html2plaintext(move.narration).strip()
            if description:
                return description
        lines = move.invoice_line_ids.filtered(lambda line: not line.display_type and line.name)
        if lines:
            return lines[0].name
        return move.ref or move.invoice_origin or ""

    def _get_amount_allocated_to_move(self, move):
        self.ensure_one()
        if not self.move_id or not move:
            return 0.0
        amount = 0.0
        for aml in self.move_id.line_ids:
            for partial in aml.matched_debit_ids | aml.matched_credit_ids:
                other = (
                    partial.debit_move_id
                    if partial.credit_move_id == aml
                    else partial.credit_move_id
                )
                if other.move_id != move:
                    continue
                if partial.credit_move_id == aml:
                    amount += abs(partial.credit_amount_currency)
                else:
                    amount += abs(partial.debit_amount_currency)
        return self.currency_id.round(amount) if self.currency_id else amount

    def _get_batch_report_bill_lines(self):
        self.ensure_one()
        lines = []
        is_customer = self._is_customer_payment()
        invoice_lines = self.env["account.payment.invoice"] if "account.payment.invoice" in self.env else False
        if invoice_lines is not False and "payment_invoice_ids" in self._fields:
            invoice_lines = self.payment_invoice_ids.filtered(lambda line: line.invoice_id)
            allocated = invoice_lines.filtered(lambda line: line.reconcile_amount)
            if allocated:
                invoice_lines = allocated

        if invoice_lines:
            for index, line in enumerate(invoice_lines, start=1):
                invoice = line.invoice_id
                lines.append({
                    "index": index,
                    "bill_no": invoice.name or "",
                    "bill_date": invoice.invoice_date or invoice.date,
                    "paid": line.reconcile_amount or 0.0,
                    "description": self._get_move_report_description(invoice),
                })
            return lines

        moves = self.env["account.move"]
        if is_customer:
            if "reconciled_invoice_ids" in self._fields:
                moves = self.reconciled_invoice_ids
            customer_types = ("out_invoice", "out_refund", "out_receipt")
            if not moves and "invoice_ids" in self._fields:
                moves = self.invoice_ids.filtered(lambda move: move.move_type in customer_types)
        else:
            if "reconciled_bill_ids" in self._fields:
                moves = self.reconciled_bill_ids
            vendor_types = ("in_invoice", "in_refund", "in_receipt")
            if not moves and "invoice_ids" in self._fields:
                moves = self.invoice_ids.filtered(lambda move: move.move_type in vendor_types)
        for index, move in enumerate(moves, start=1):
            lines.append({
                "index": index,
                "bill_no": move.name or "",
                "bill_date": move.invoice_date or move.date,
                "paid": self._get_amount_allocated_to_move(move),
                "description": self._get_move_report_description(move),
            })
        return lines

    def _get_batch_report_bill_data(self):
        self.ensure_one()
        lines = self._get_batch_report_bill_lines()
        return {
            "lines": lines,
            "paid": sum(line["paid"] for line in lines),
        }
