from odoo import api, fields, models

from .transaction_type import TRANSACTION_TYPE_SELECTION


class AccountPayment(models.Model):
    _inherit = "account.payment"

    customer_transaction_ref = fields.Char(
        string="Customer Transaction Ref. No.",
        copy=False,
        index=True,
        help="Customer transaction reference number used in the bank payment file.",
    )
    transaction_type_code = fields.Char(
        string="Transaction Type Code",
        help="Bank transaction type code.",
    )
    bank_to_bank = fields.Char(
        string="Bank to Bank",
        help="Bank-to-bank information for the payment file.",
    )
    charge_type = fields.Selection(
        [
            ("OUR", "OUR - Sender"),
            ("BEN", "BEN - Beneficiary"),
            ("SHA", "SHA - Shared"),
        ],
        string="Charge Type",
        help="Who bears the bank charges.",
    )
    payment_detail_1 = fields.Text(string="Payment Detail 1")
    payment_detail_2 = fields.Text(string="Payment Detail 2")
    regulatory_ttc_code = fields.Char(
        string="Regulatory Reporting TTC Code",
        help="Regulatory reporting TTC code.",
    )
    additional_details = fields.Text(string="Additional Details")
    payment_mode = fields.Selection(
        [
            ("bank_transfer", "Bank Transfer"),
            ("cheque", "Cheque"),
            ("other", "Other"),
        ],
        string="Payment Mode",
        tracking=True,
        help="How this payment will be processed.",
    )
    transaction_type = fields.Selection(
        selection=TRANSACTION_TYPE_SELECTION,
        string="Transaction Type",
        compute="_compute_transaction_type",
        store=True,
        precompute=True,
        index=True,
        help="Customer/Vendor payment or refund based on partner and payment type. "
             "Copied onto the related journal entry.",
    )

    @api.depends("payment_type", "partner_type")
    def _compute_transaction_type(self):
        for payment in self:
            payment.transaction_type = payment._get_transaction_type()

    def _get_transaction_type(self):
        self.ensure_one()
        if getattr(self, "is_internal_transfer", False):
            return "internal_transfer"
        partner_type = self.partner_type
        payment_type = self.payment_type
        if partner_type == "customer" and payment_type == "inbound":
            return "customer_payment"
        if partner_type == "customer" and payment_type == "outbound":
            return "customer_refund"
        if partner_type == "supplier" and payment_type == "outbound":
            return "vendor_payment"
        if partner_type == "supplier" and payment_type == "inbound":
            return "vendor_refund"
        return False
