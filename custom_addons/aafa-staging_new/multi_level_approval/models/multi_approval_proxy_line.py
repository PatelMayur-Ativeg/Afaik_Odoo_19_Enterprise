##############################################################################
#
#    Copyright Domiup (<http://domiup.com>).
#
##############################################################################

from odoo import fields, models



class MultiApprovalProxyLine(models.Model):
    _name = "multi.approval.proxy.line"
    _description = "Approval Proxy Line"

    start_date = fields.Datetime(string="Start Date", required=True)
    end_date = fields.Datetime(string="End Date", required=True)
    type_id = fields.Many2one(string="Type", comodel_name="multi.approval.type", ondelete="cascade")
    approval_type_line_id = fields.Many2one('multi.approval.type.line', string='Approver', required=True, domain="[('type_id', '=', type_id)]", ondelete="cascade")
    user_id = fields.Many2one('res.users', related="approval_type_line_id.user_id")
    proxy_user_ids = fields.Many2many(
        comodel_name='res.users',
        relation='multi_approval_proxy_line_user_rel',
        column1='proxy_line_id',
        column2='user_id',
        string='Proxy Approvers'
    )

    _type_approver_unique = models.Constraint(
        "UNIQUE(type_id, approval_type_line_id)",
        "The approver must be unique per approval type!",
    )

    def get_proxy_users(self):
        if not self:
            return []
        return self.mapped('proxy_user_ids').ids