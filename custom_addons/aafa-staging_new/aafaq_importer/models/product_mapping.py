from odoo import models, fields, api

class ProductMapping(models.Model):
    _name = "product.mapping"
    _description = "Product Mapping"
    _order = 'sequence, id desc'

    sequence = fields.Integer(default=10)
    name = fields.Char()
    analytic_account_ids = fields.Many2many(
        'account.analytic.account',
        'product_mapping_analytic_account_rel',
        'mapping_id',
        'analytic_account_id',
        string="Analytic Accounts",
        help="Analytic accounts to apply at 100% each when forming distribution",
    )
