from odoo import api, fields, models


class AccountBatchPayment(models.Model):
    _inherit = "account.batch.payment"

    payment_mode = fields.Selection(
        [
            ("bank_transfer", "Bank Transfer"),
            ("cheque", "Cheque"),
            ("other", "Other"),
        ],
        string="Payment Mode",
        tracking=True,
        help="How payments in this batch will be processed.",
    )
    memo = fields.Text(
        string="Memo",
        help="General purpose notes for this payment batch.",
    )

    @api.onchange("payment_mode")
    def _onchange_batch_payment_mode(self):
        if self.payment_mode:
            for payment in self.payment_ids:
                if not payment.payment_mode:
                    payment.payment_mode = self.payment_mode

    @api.onchange("payment_ids")
    def _onchange_payment_ids_payment_mode(self):
        if self.payment_mode:
            for payment in self.payment_ids:
                if not payment.payment_mode:
                    payment.payment_mode = self.payment_mode
