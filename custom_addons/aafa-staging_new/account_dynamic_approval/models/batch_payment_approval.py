from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime
import logging

from .approval_tools import send_approval_notifications


_logger = logging.getLogger(__name__)


class BatchPaymentApproval(models.Model):
    _name = "batch.payment.approval"
    _description = "Batch Payment Approval"
    _order = "date desc, id desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True, copy=False, string='Reference', readonly=True, default="New")
    date = fields.Date(required=True, copy=False, default=fields.Date.context_today, readonly=True, tracking=True)
    state = fields.Selection([
        ('draft', 'New'),
        ('waiting_for_approval', 'Waiting For Approval'),
        ('posted', 'Posted'),
        ('reject','Reject')
    ], store=True, default='draft', tracking=True)
    payment_ids = fields.One2many('account.payment', 'batch_payment_approval_id', string="Batch Payment Approval", required=True)
    currency_id = fields.Many2one('res.currency', compute='_compute_currency', store=True, readonly=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=True,
        default=lambda self: self.env.company)
    # amount = fields.Monetary(
    #     currency_field='currency_id',
    #     compute='_compute_from_payment_ids',
    #     store=True,
    # )
    approval_level_id = fields.Many2one(
        'sh.batch.payment.approval.config', string="Approval Level", compute="compute_approval_level")
    level = fields.Integer(string="Next Approval Level", readonly=True)
    user_ids = fields.Many2many('res.users', string="Users", readonly=True)
    group_ids = fields.Many2many('res.groups', string="Groups", readonly=True)
    is_boolean = fields.Boolean(
        string="Boolean", compute="compute_is_boolean", search='_search_is_boolean')
    approval_info_line = fields.One2many(
        'batch.payment.approval.info', 'batch_payment_approval_id', readonly=True)
    rejection_date = fields.Datetime(string="Reject Date", readonly=True)
    reject_by = fields.Many2one('res.users', string="Reject By", readonly=True)
    reject_reason = fields.Char(string="Reject Reason", readonly=True)
    

    @api.depends('name','date')
    def compute_approval_level(self):
        if self.company_id and self.name:
                payment_approvals = self.env['sh.batch.payment.approval.config'].search(
                    [('company_ids.id', 'in', [self.env.company.id])])
                listt = []
                
                for account_approval in payment_approvals:
                    self.update({
                        'approval_level_id': account_approval[0].id
                    })
        else:
            self.approval_level_id = False


    def compute_is_boolean(self):
        if self.env.user.id in self.user_ids.ids or any(
                item in self.env.user.group_ids.ids for item in self.group_ids.ids):
            self.is_boolean = True
        else:
            self.is_boolean = False

    def _search_is_boolean(self, operator, value):
        results = []
        if value:
            pay_ids = self.env['batch.payment.approval'].search([])
            if pay_ids:
                for po in pay_ids:
                    if self.env.user.id in po.user_ids.ids or any(
                            item in self.env.user.group_ids.ids for item in po.group_ids.ids):
                        results.append(po.id)
        return [('id', 'in', results)]
    

    @api.depends('name')
    def _compute_currency(self):
        for batch in self:
            batch.currency_id = self.env.company.currency_id



    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals['name'] == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('batch.payment.approval.sequence')
        return super().create(vals_list)
    

    def validate_batch_button(self):
        for rec in self:
            for line in rec.payment_ids:
                line.action_post()
            rec.write({'state':"posted"}) 
            
    def action_request_approval(self):
        template_id = self.env.ref(
            "account_dynamic_approval.email_template_for_approve_batch_paymentapproval")
        
        if self.approval_level_id.payment_approval_line:
            self.write({
                'state': 'waiting_for_approval'
            })
            lines = self.approval_level_id.payment_approval_line
            
            self.approval_info_line = False
            for line in lines:
                dictt = []
                if line.approve_by == 'group':
                    dictt.append((0, 0, {
                        'level': line.level,
                        'user_ids': False,
                        'group_ids': [(6, 0, line.group_ids.ids)],
                        'label_type':line.label_type
                    }))


                if line.approve_by == 'user':
                    dictt.append((0, 0, {
                        'level': line.level,
                        'user_ids': [(6, 0, line.user_ids.ids)],
                        'group_ids': False,
                        'label_type':line.label_type
                    }))

                self.update({
                    'approval_info_line': dictt
                })

            if lines[0].approve_by == 'group':
                self.write({
                    'level': lines[0].level,
                    'group_ids': [(6, 0, lines[0].group_ids.ids)],
                    'user_ids': False
                })

                users = self.env['res.users'].search(
                    [('group_ids', 'in', lines[0].group_ids.ids)])

                if template_id and users:
                    for user in users:
                        template_id.sudo().send_mail(self.id, force_send=True, email_values={
                            'email_from': self.env.user.email, 'email_to': user.email})

                notifications = []
                if users:
                    for user in users:
                        notifications.append([user.partner_id, 'res.partner', {
                            'title': _('Notitification'),
                            'message': 'You have approval notification for Payment %s' % (self.name),
                            'sticky': True,
                            'warning': True
                        }])
                    send_approval_notifications(self.env, notifications)

            if lines[0].approve_by == 'user':
                self.write({
                    'level': lines[0].level,
                    'user_ids': [(6, 0, lines[0].user_ids.ids)],
                    'group_ids': False
                })

                if template_id and lines[0].user_ids:
                    for user in lines[0].user_ids:
                        template_id.sudo().send_mail(self.id, force_send=True, email_values={
                            'email_from': self.env.user.email, 'email_to': user.email})

                notifications = []
                if lines[0].user_ids:
                    for user in lines[0].user_ids:
                        notifications.append([user.partner_id, 'res.partner', {
                            'title': _('Notitification'),
                            'message': 'You have approval notification for Payment %s' % (self.name),
                            'sticky': True,
                            'warning': True
                        }])
                    send_approval_notifications(self.env, notifications)

        else:
            self.validate_batch_button()


    def action_post(self):
        template_id = self.env.ref(
            "account_dynamic_approval.email_template_for_approve_batch_paymentapproval")

        info = self.approval_info_line.filtered(
            lambda x: x.level == self.level)

        if info:
            info.status = True
            info.approval_date = datetime.now()
            info.approved_by = self.env.user

        line_id = self.env['sh.batch.payment.approval.line'].search(
            [('batch_payment_approval_config_id', '=', self.approval_level_id.id), ('level', '=', self.level)])

        next_line = self.env['sh.batch.payment.approval.line'].search(
            [('batch_payment_approval_config_id', '=', self.approval_level_id.id), ('id', '>', line_id.id)], limit=1)

        if next_line:
            if next_line.approve_by == 'group':
                self.write({
                    'level': next_line.level,
                    'group_ids': [(6, 0, next_line.group_ids.ids)],
                    'user_ids': False
                })
                users = self.env['res.users'].search(
                    [('group_ids', 'in', next_line.group_ids.ids)])

                if template_id and users and self.approval_level_id.is_boolean:
                    for user in users:
                        template_id.sudo().send_mail(self.id, force_send=True, email_values={
                            'email_from': self.env.user.email, 'email_to': user.email, 'email_cc': self.create_uid.email})

                # if template_id and users and not self.approval_level_id.is_boolean:
                #     for user in users:
                #         template_id.sudo().send_mail(self.id, force_send=True, email_values={
                #             'email_from': self.env.user.email, 'email_to': user.email})

                notifications = []
                if users:
                    for user in users:
                        notifications.append([user.partner_id, 'res.partner', {
                            'title': _('Notitification'),
                            'message': 'You have approval notification for account order %s' % (self.name),
                            'sticky': True,
                            'warning': True
                        }])
                    send_approval_notifications(self.env, notifications)

            if next_line.approve_by == 'user':
                self.write({
                    'level': next_line.level,
                    'user_ids': [(6, 0, next_line.user_ids.ids)],
                    'group_ids': False
                })
                if template_id and next_line.user_ids and self.approval_level_id.is_boolean:
                    for user in next_line.user_ids:
                        template_id.sudo().send_mail(self.id, force_send=True, email_values={
                            'email_from': self.env.user.email, 'email_to': user.email, 'email_cc': self.create_uid.email})

                # if template_id and next_line.user_ids and not self.approval_level_id.is_boolean:
                #     for user in next_line.user_ids:
                #         template_id.sudo().send_mail(self.id, force_send=True, email_values={
                #             'email_from': self.env.user.email, 'email_to': user.email})

                notifications = []
                if next_line.user_ids:
                    for user in next_line.user_ids:
                        notifications.append([user.partner_id, 'res.partner', {
                            'title': _('Notitification'),
                            'message': 'You have approval notification for account order %s' % (self.name),
                            'sticky': True,
                            'warning': True
                        }])
                    send_approval_notifications(self.env, notifications)

        else:
            template_id = self.env.ref(
                "account_dynamic_approval.email_template_for_confirm_batch_payment")
            if template_id:
                template_id.sudo().send_mail(self.id, force_send=True, email_values={
                    'email_from': self.env.user.email, 'email_to': self.create_uid.email})

            notifications = []
            if self.create_uid:
                notifications.append([self.create_uid.partner_id, 'res.partner', {
                    'title': _('Notitification'),
                    'message': 'Dear User!! your Account %s is confirmed' % (self.name),
                    'sticky': True,
                    'warning': True
                }])
                send_approval_notifications(self.env, notifications)

            self.write({
                'level': False,
                'group_ids': False,
                'user_ids': False,
                # 'state': 'posted',
            })
            self.validate_batch_button()

    def action_reset_to_draft(self):
        for rec in self:
            rec.write({
                'level': False,
                'group_ids': False,
                'user_ids': False,
                'state': 'draft',
                'rejection_date': False,
                'reject_by': False,
                'reject_reason':False
            })
