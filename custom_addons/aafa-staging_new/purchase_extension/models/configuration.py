from odoo import models, fields, api, _
from datetime import datetime, time, date, timedelta

class PurchaseCategory(models.Model):
    _name = 'purchase.category'
    
    name = fields.Char(string="Purchase Category")
