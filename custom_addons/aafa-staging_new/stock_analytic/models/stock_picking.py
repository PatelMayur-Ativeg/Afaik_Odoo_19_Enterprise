
from odoo import models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def button_validate(self):
        self = self.with_context(validate_analytic=True)
        return super().button_validate()
