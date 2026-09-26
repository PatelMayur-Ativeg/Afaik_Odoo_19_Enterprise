# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields


class PurchaseOrderApproval(models.Model):
    _name = 'purchase.order.approval'

    approval_level = fields.Char(string="Level Of Approval")
    user_ids = fields.Many2many('res.users', string='Approval Ids')
    approval_status = fields.Boolean('Status')
    order_id = fields.Many2one('purchase.order', string='Order Id')
