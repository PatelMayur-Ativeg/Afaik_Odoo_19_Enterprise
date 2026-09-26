# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from odoo import fields, models


class PurchaseRequestCategory(models.Model):
    _name = "purchase.request.category"
    _description = "Purchase Request Category"
    _order = "name"

    name = fields.Char(string="Name", required=True, translate=True)
    code = fields.Char(string="Code")
    active = fields.Boolean(default=True)
