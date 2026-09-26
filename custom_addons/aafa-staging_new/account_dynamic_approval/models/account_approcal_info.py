from odoo import api, fields, tools, models, _


class AccountApprovalInfo(models.Model):
    _name = 'account.approval.info'
    _description = "Approval Information"

    level = fields.Integer(string="Approval Level")
    user_ids = fields.Many2many('res.users', string="Users")
    group_ids = fields.Many2many('res.groups', string="Groups")
    status = fields.Boolean(string="Status")
    approval_date = fields.Datetime(string="Approved Date")
    approved_by = fields.Many2one('res.users', string="Approved By")
    move_id = fields.Many2one('account.move', "Invoice")


class PaymentApprovalInfo(models.Model):
    _name = 'payment.approval.info'
    _description = "Approval Information"

    level = fields.Integer(string="Approval Level")
    user_ids = fields.Many2many('res.users', string="Users")
    group_ids = fields.Many2many('res.groups', string="Groups")
    status = fields.Boolean(string="Status")
    approval_date = fields.Datetime(string="Approved Date")
    approved_by = fields.Many2one('res.users', string="Approved By")
    payment_id = fields.Many2one('account.payment', "Payment ID")
    label_type = fields.Selection([('verified_by', 'Verified By'),('supported_by','Supported By'),('reviewed_by','Reviewed By'),('approved_by','Approved By')])


class BatchPaymentApprovalInfo(models.Model):
    _name = 'batch.payment.approval.info'
    _description = "Batch Approval Information"

    level = fields.Integer(string="Approval Level")
    user_ids = fields.Many2many('res.users', string="Users")
    group_ids = fields.Many2many('res.groups', string="Groups")
    status = fields.Boolean(string="Status")
    approval_date = fields.Datetime(string="Approved Date")
    approved_by = fields.Many2one('res.users', string="Approved By")
    batch_payment_approval_id = fields.Many2one('batch.payment.approval', "Batch Payment Approval ID")
    label_type = fields.Selection([('verified_by', 'Verified By'),('supported_by','Supported By'),('reviewed_by','Reviewed By'),('approved_by','Approved By')])