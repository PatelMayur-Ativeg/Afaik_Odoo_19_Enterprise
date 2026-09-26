from odoo import models, fields, api, tools
from odoo.exceptions import ValidationError

class CurrencyAccountMapping(models.Model):
    _name = "currency.account.mapping"
    _description = "Currency AC Map"
    _order = 'sequence, id desc'
    _rec_name = "currency_id"

    sequence = fields.Integer(default=10)
    currency_id = fields.Many2one(
        'res.currency',
        string="Currency",
        required=True
    )
    account_id = fields.Many2one(
        'account.account',
        string="Chart of Account",
        required=True,
    )
    customer_type = fields.Selection([
        ("customer_wakala_asset", "Wakala Assets Customers"),
        ("customer_wakala_lib", "Wakala Liability Customers"),
    ],  required=True)

    _sql_constraints = [
        (
            'currency_account_unique',
            'unique(currency_id, account_id)',
            'Mapping already exists for this currency with the same account!'
        )
    ]

    @api.model
    @tools.ormcache('code, record_type')
    def get_account_by_currency_code(self, code, record_type):
        mapping_id = self.search([('currency_id.name', '=', code),('customer_type', '=', record_type)], limit=1)
        return mapping_id.account_id.id

    @api.model_create_multi
    def create(self, vals_list):
        self.env.registry.clear_cache()
        return super(CurrencyAccountMapping, self).create(vals_list)

    def write(self, vals):
        self.env.registry.clear_cache()
        return super(CurrencyAccountMapping, self).write(vals)

    def unlink(self):
        self.env.registry.clear_cache()
        return super(CurrencyAccountMapping, self).unlink()
