from odoo import api, fields, tools, models, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    account_approval_based_on = fields.Selection(
        [   ('type', 'Type'),
            # ('untaxed_amount', 'Untaxed amount'),
            # ('total', 'Total')
        ], default='type', readonly=False)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    account_approval_based_on = fields.Selection(
        [   ('type', 'Type'),
            # ('untaxed_amount', 'Untaxed amount'),
            # ('total', 'Total')
        ], related='company_id.account_approval_based_on', default='type', readonly=False)
