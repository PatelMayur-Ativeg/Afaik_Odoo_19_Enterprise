from odoo import fields, models


class AccountAccount(models.Model):
    _inherit = "account.account"

    aafaq_queue_id = fields.Many2one(
        "aafaq.import.queue",
        string="Import Queue",
        ondelete="set null",
        index=True,
        copy=False,
    )
