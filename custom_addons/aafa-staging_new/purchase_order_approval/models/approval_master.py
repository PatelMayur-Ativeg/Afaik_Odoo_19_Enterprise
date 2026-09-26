# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api


class ApprovalMaster(models.Model):
    _name = 'approval.master'

    name = fields.Char(string='Approval Name')
    user_ids = fields.One2many('approval.lines', 'approval_id', string='Approver')
    min_amount = fields.Float(string='Minimum Amount')
    mx_amount = fields.Float(string='Maximum Amount')

    def add_level(self):
        rec = self.env['approval.lines'].create({'approval_level': 'Level ' + str(len(self.user_ids) + 1)})
        self.user_ids += rec

    def remove_level(self):
        if self.user_ids:
            self.user_ids = self.user_ids[:-1]





