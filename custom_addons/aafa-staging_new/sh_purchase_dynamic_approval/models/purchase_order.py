from odoo import models, fields, api, _
from datetime import datetime, time, date, timedelta

# from odoo.addons.purchase.models.purchase import PurchaseOrder as Purchase

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    is_boolean = fields.Boolean(string="Boolean")