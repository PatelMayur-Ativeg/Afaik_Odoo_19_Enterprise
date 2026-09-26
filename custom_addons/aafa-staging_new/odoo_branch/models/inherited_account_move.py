# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare




class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.constrains('branch_id')
    def _get_onclick_image(self):
        for rec in self:
            if rec.branch_id:
                for aml in rec.line_ids:
                    if not aml.branch_id:
                        aml.branch_id = rec.branch_id.id

    @api.model
    def default_get(self, default_fields):
        res = super(AccountMove, self).default_get(default_fields)
        branch_id = False
        if self._context.get('branch_id'):
            branch_id = self._context.get('branch_id')
        elif self.env.user.branch_id:
            branch_id = self.env.user.branch_id.id
        res.update({
            'branch_id' : branch_id
        })
        return res


    branch_id = fields.Many2one('res.branch', string="Branch")

    def check_move_line_branch(self):
        for rec in self.env['account.move.line'].search([]):
            if rec.move_id.branch_id:
                rec.branch_id = rec.move_id.branch_id.id





class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.model
    def default_get(self, default_fields):
        res = super(AccountMoveLine, self).default_get(default_fields)
        branch_id = False

        print(self._context,'==================context \n\n')

        if self._context.get('branch_id'):
            branch_id = self._context.get('branch_id')
        elif self.env.user.branch_id:
            branch_id = self.env.user.branch_id.id
        if self.move_id.branch_id:
            branch_id = self.move_id.branch_id.id
        res.update({'branch_id' : branch_id})
        return res

    branch_id = fields.Many2one('res.branch', string="Branch")
