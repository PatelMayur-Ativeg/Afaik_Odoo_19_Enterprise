from odoo import api, fields, tools, models, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    approval_based_on = fields.Selection(
        [
            ('pr_category', 'Request Category'),
        ], default='pr_category', readonly=False)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    approval_based_on = fields.Selection(
        [
            ('pr_category', 'Request Category'),
        ], related='company_id.approval_based_on', default='pr_category', readonly=False)
