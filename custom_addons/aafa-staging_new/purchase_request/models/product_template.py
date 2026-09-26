# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = "product.category"

    pr_category_id = fields.Many2one(
        "purchase.request.category", string="Category Type"
    )
