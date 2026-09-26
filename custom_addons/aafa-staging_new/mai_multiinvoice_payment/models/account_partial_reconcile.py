# -*- coding: utf-8 -*-

from odoo import fields, models


class AccountPartialReconcile(models.Model):
    _inherit = "account.partial.reconcile"

    payment_id = fields.Many2one("account.payment", "Payment", ondelete="restrict")
