# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class Users(models.Model):
    _inherit = 'res.users'

    analytic_account_id = fields.Many2one('account.analytic.account', string= 'Analytic Account')
