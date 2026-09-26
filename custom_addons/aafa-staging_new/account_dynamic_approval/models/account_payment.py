from odoo import api, fields, tools, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
import logging

from .approval_tools import send_approval_notifications


_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    state = fields.Selection(
        # Odoo 19: account.payment has its own computed state field.
        # In v16, payment state was delegated to account.move (via _inherits),
        # which already extended state in account_move.py below.
        selection_add=[
            ('waiting_for_approval', 'Waiting for Approval'),
            ('reject', 'Reject'),
        ],
        ondelete={
            'waiting_for_approval': 'set default',
            'reject': 'set default',
        },
    )

    approval_level_id = fields.Many2one(
        'sh.payment.approval.config', string="Approval Level", compute="compute_approval_level")
    level = fields.Integer(string="Next Approval Level", readonly=True)
    user_ids = fields.Many2many('res.users', string="Users", readonly=True)
    group_ids = fields.Many2many('res.groups', string="Groups", readonly=True)
    is_boolean = fields.Boolean(
        string="Boolean", compute="compute_is_boolean", search='_search_is_boolean')
    approval_info_line = fields.One2many(
        'payment.approval.info', 'payment_id', readonly=True)
    rejection_date = fields.Datetime(string="Reject Date", readonly=True)
    reject_by = fields.Many2one('res.users', string="Reject By", readonly=True)
    reject_reason = fields.Char(string="Reject Reason", readonly=True)
    batch_payment_approval_id = fields.Many2one('batch.payment.approval')

    @api.depends(
        'reconciled_invoice_ids.payment_state',
        'reconciled_bill_ids.payment_state',
        'move_id.line_ids.amount_residual',
    )
    def _compute_state(self):
        # Keep approval workflow states; standard compute only applies to others.
        approval_payments = self.filtered(
            lambda payment: payment.state in ('waiting_for_approval', 'reject')
        )
        super(AccountPayment, self - approval_payments)._compute_state()

    def compute_is_boolean(self):
        if self.env.user.id in self.user_ids.ids or any(
                item in self.env.user.group_ids.ids for item in self.group_ids.ids):
            self.is_boolean = True
        else:
            self.is_boolean = False

    def _search_is_boolean(self, operator, value):
        results = []

        if value:
            pay_ids = self.env['account.payment'].search([])
            if pay_ids:
                for po in pay_ids:
                    if self.env.user.id in po.user_ids.ids or any(
                            item in self.env.user.group_ids.ids for item in po.group_ids.ids):
                        results.append(po.id)
        return [('id', 'in', results)]

    def action_post(self):
        template_id = self.env.ref(
            "account_dynamic_approval.email_template_for_approve_vendor_payment")
        
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
            super(AccountPayment, self).action_post()

    @api.depends('amount','payment_type','partner_type')
    def compute_approval_level(self):
        if self.company_id and self.payment_type == 'outbound' and self.partner_type == 'supplier' and not self.batch_payment_approval_id:
                payment_approvals = self.env['sh.payment.approval.config'].search(
                    [('min_amount', '<', self.amount), ('company_ids.id', 'in', [self.env.company.id])])
                listt = []
                for account_approval in payment_approvals:
                    listt.append(account_approval.min_amount)

                if listt:
                    account_approval = payment_approvals.filtered(
                        lambda x: x.min_amount == max(listt))

                    self.update({
                        'approval_level_id': account_approval[0].id
                    })
                else:
                    self.approval_level_id = False

        else:
            self.approval_level_id = False

    def action_approve_order(self):

        template_id = self.env.ref(
            "account_dynamic_approval.email_template_for_approve_vendor_payment")

        info = self.approval_info_line.filtered(
            lambda x: x.level == self.level)

        if info:
            info.status = True
            info.approval_date = datetime.now()
            info.approved_by = self.env.user

        line_id = self.env['sh.payment.approval.line'].search(
            [('payment_approval_config_id', '=', self.approval_level_id.id), ('level', '=', self.level)])

        next_line = self.env['sh.payment.approval.line'].search(
            [('payment_approval_config_id', '=', self.approval_level_id.id), ('id', '>', line_id.id)], limit=1)

        if next_line and not self.batch_payment_approval_id:
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
                            'email_from': self.env.user.email, 'email_to': user.email})

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
                "account_dynamic_approval.email_template_for_confirm_vendor_payment")
            if template_id:
                template_id.sudo().send_mail(self.id, force_send=True, email_values={
                    'email_from': self.env.user.email, 'email_to': self.create_uid.email})

            notifications = []
            if self.create_uid.partner_id:
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
            super(AccountPayment, self).action_post()

    def action_reset_to_draft(self):
        self.write({
            'state': 'draft'
        })


    @api.model
    def create_batch_payment_approval(self):
        batch = self.env['batch.payment.approval'].create({
            'payment_ids': [(4, payment.id, None) for payment in self],
        })

        return {
            "type": "ir.actions.act_window",
            "res_model": "batch.payment.approval",
            "views": [[False, "form"]],
            "res_id": batch.id,
        }
