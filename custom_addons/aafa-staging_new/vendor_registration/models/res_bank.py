# Copyright 2017 Tecnativa - Carlos Dauden <carlos.dauden@tecnativa.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3).

from odoo import fields, models


class ResBank(models.Model):
    _inherit = "res.bank"

    acc_holder_name = fields.Char('Account Holder Name')
    iban = fields.Char('IBAN Code')
    ifcs_code = fields.Char('IFCS Code')
    bank_address = fields.Char('Bank Address')
    swift_code = fields.Char('Swift Code')
