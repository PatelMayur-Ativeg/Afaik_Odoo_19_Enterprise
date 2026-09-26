from odoo import api, fields, tools, models, _


class TermsAndConditions(models.Model):
    _name = 'terms.and.conditions'

    name = fields.Char("Name")
    terms = fields.Html("Terms")
