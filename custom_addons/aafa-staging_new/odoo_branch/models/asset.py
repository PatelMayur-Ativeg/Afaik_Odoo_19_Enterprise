# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class Assets(models.Model):
    _inherit = 'account.asset'

    def compute_depreciation_board(self):
        res = super(Assets, self).compute_depreciation_board()
        for line in self.depreciation_move_ids:
            line.branch_id = self.branch_id.id
        return res
    @api.model
    def default_get(self, default_fields):
        res = super(Assets, self).default_get(default_fields)
        if self.env.user.branch_id:
            res.update({
                'branch_id' : self.env.user.branch_id.id or False
            })
        return res

    branch_id = fields.Many2one('res.branch', string="Branch")