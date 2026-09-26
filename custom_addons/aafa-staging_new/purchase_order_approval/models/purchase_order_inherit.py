# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    level_of_approval = fields.Integer('Current Approval Level', default=0)
    approval_sequence = fields.One2many('purchase.order.approval', 'order_id', string='Approval Sequence')

    @api.constrains('amount_total')
    @api.onchange('amount_total')
    def _button_show(self):
        for order in self:
            approver_rec = self.env['approval.master'].search([
                ('mx_amount', '>=', order.amount_total),
                ('min_amount', '<=', order.amount_total),
            ])
            approval_lines = []
            for line in approver_rec.user_ids:
                approval_lines.append((0, 0, {
                    'approval_level': line.approval_level,
                    'user_ids': [(6, 0, line.approval_user_id.ids)],
                }))
            order.write({
                'approval_sequence': [(5, 0, 0)] + approval_lines,
            })

    def _approval_allowed(self):
        for line in self.approval_sequence.search([('approval_status','=',False)]):
            print("4444444444", self.env.user.id, line.user_ids.ids)
            if self.env.user.id in line.user_ids.ids:
                line.approval_status = True
            # else:
            #     break
        if any(al.approval_status == False for al in self.approval_sequence):
            return False
        else:
            return True







