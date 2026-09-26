# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api


class ApprovalLines(models.Model):
    _name = 'approval.lines'

    approval_level = fields.Char(string="Levels Of Approval")
    approval_user_id = fields.Many2many('res.users', string='Approval Users')
    approval_id = fields.Many2one('approval.master', string='Approval ID')
