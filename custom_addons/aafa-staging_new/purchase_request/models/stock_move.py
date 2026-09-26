# Copyright 2018-2019 ForgeFlow, S.L.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare

class StockPicking(models.Model):
    _inherit = "stock.picking"

    request_id = fields.Many2one('purchase.request')

class StockMove(models.Model):
    _inherit = "stock.move"

    purchase_request_line_id = fields.Many2one(
        comodel_name="purchase.request.line",
        string="Created Purchase Request Line",
        ondelete="set null",
        readonly=True,
        copy=False,
        index=True,
    )

class StockLocation(models.Model):
    _inherit = "stock.location"

    show_pr_qty = fields.Boolean("Show PR Qty", default=False)