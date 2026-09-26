from odoo import api, fields, models, _


class AccountBatchPayment(models.Model):
    _inherit = "account.batch.payment"

    partner_count = fields.Integer(
        string="Partners",
        compute="_compute_partner_count",
    )

    @api.depends("payment_ids", "payment_ids.partner_id")
    def _compute_partner_count(self):
        for batch in self:
            batch.partner_count = len(batch.payment_ids.mapped("partner_id"))

    def _get_batch_report_amount(self):
        """Batch amount is signed (negative for outbound). PDF widgets insert
        U+FEFF after a minus sign, which wkhtmltopdf renders as garbage."""
        self.ensure_one()
        return abs(self.amount or 0.0)

    def _convert_payment_amount(self, payment):
        self.ensure_one()
        amount = abs(payment.amount or 0.0)
        if (
            payment.currency_id
            and self.currency_id
            and payment.currency_id != self.currency_id
        ):
            return payment.currency_id._convert(
                amount,
                self.currency_id,
                self.company_id,
                payment.date or fields.Date.context_today(self),
            )
        return amount

    def _is_customer_batch(self):
        self.ensure_one()
        if self.batch_type:
            return self.batch_type == "inbound"
        payment = self.payment_ids[:1]
        return payment.partner_type == "customer" or payment.payment_type == "inbound"

    def _get_batch_report_labels(self):
        self.ensure_one()
        if self._is_customer_batch():
            return {
                "partner_count": _("Total Customers"),
                "partner_name": _("Customer Name"),
                "partner": _("Customer"),
                "partner_info": _("Customer Information"),
                "doc_section": _("Invoice Reconciliation"),
                "doc_no": _("Invoice No."),
                "doc_date": _("Invoice Date"),
                "doc_amount": _("Payment Amount"),
                "doc_description": _("Invoice Description"),
                "empty_docs": _("No invoices allocated to this payment."),
            }
        return {
            "partner_count": _("Total Vendors"),
            "partner_name": _("Vendor Name"),
            "partner": _("Vendor"),
            "partner_info": _("Vendor Information"),
            "doc_section": _("Bill Reconciliation"),
            "doc_no": _("Bill No."),
            "doc_date": _("Bill Date"),
            "doc_amount": _("Payment Amount"),
            "doc_description": _("Bill Description"),
            "empty_docs": _("No bills allocated to this payment."),
        }

    def print_batch_payment(self):
        return self.env.ref(
            "aafa_reports.action_report_payment_batch_approval"
        ).report_action(self, config=False)
