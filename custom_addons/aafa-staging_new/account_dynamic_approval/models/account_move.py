from odoo import api, fields, tools, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
import logging

from .approval_tools import send_approval_notifications


_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    approval_level_id = fields.Many2one(
        'sh.account.approval.config', string="Approval Level")
    state = fields.Selection(
        selection_add=[('waiting_for_approval', 'Waiting for Approval'), ('reject', 'Reject')],
        ondelete={'waiting_for_approval': 'set default', 'reject': 'set default'})
    status_in_payment = fields.Selection(
        selection_add=[
            ('waiting_for_approval', 'Waiting for Approval'),
            ('reject', 'Reject'),
        ],
        ondelete={'waiting_for_approval': 'set default', 'reject': 'set default'},
    )
    level = fields.Integer(string="Next Approval Level", readonly=True)
    user_ids = fields.Many2many('res.users', string="Users", readonly=True)
    group_ids = fields.Many2many('res.groups', string="Groups", readonly=True)
    is_boolean = fields.Boolean(
        string="Boolean", compute="compute_is_boolean", search='_search_is_boolean')
    approval_info_line = fields.One2many(
        'account.approval.info', 'move_id', readonly=True)
    rejection_date = fields.Datetime(string="Reject Date", readonly=True)
    reject_by = fields.Many2one('res.users', string="Reject By", readonly=True)
    reject_reason = fields.Char(string="Reject Reason", readonly=True)

    account_approval_type = fields.Selection([
            ('approval', 'Approval'),
            ('non_approval', 'Non_Approval')],)


    @api.onchange('account_approval_type')
    def onchange_approval_type(self):
        for rec in self:
            if rec.account_approval_type:
                rec.approval_level_id = False

    def compute_is_boolean(self):

        if self.env.user.id in self.user_ids.ids or any(
                item in self.env.user.group_ids.ids for item in self.group_ids.ids):
            self.is_boolean = True
        else:
            self.is_boolean = False

    def _search_is_boolean(self, operator, value):
        results = []

        if value:
            po_ids = self.env['account.move'].search([])
            if po_ids:
                for po in po_ids:
                    if self.env.user.id in po.user_ids.ids or any(
                            item in self.env.user.group_ids.ids for item in po.group_ids.ids):
                        results.append(po.id)
        return [('id', 'in', results)]

    @api.depends('payment_state', 'state', 'is_move_sent')
    def _compute_status_in_payment(self):
        approval_moves = self.filtered(lambda move: move.state in ('waiting_for_approval', 'reject'))
        super(AccountMove, self - approval_moves)._compute_status_in_payment()
        for move in approval_moves:
            move.status_in_payment = move.state

    def action_post(self):
        template_id = self.env.ref(
            "account_dynamic_approval.email_template_for_approve_account_invoice")

        if self.account_approval_type=='approval':

            if self.approval_level_id.account_approval_line:
                self.write({
                    'state': 'waiting_for_approval'
                })
                lines = self.approval_level_id.account_approval_line

                self.approval_info_line = False
                for line in lines:
                    dictt = []
                    if line.approve_by == 'group':
                        dictt.append((0, 0, {
                            'level': line.level,
                            'user_ids': False,
                            'group_ids': [(6, 0, line.group_ids.ids)],
                            

                        }))

                    if line.approve_by == 'user':
                        dictt.append((0, 0, {
                            'level': line.level,
                            'user_ids': [(6, 0, line.user_ids.ids)],
                            'group_ids': False,
                            
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
                                'message': 'You have approval notification for Account %s' % (self.name),
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
                                'message': 'You have approval notification for Account %s' % (self.name),
                                'sticky': True,
                                'warning': True
                            }])
                        send_approval_notifications(self.env, notifications)

            else:
                super(AccountMove, self).action_post()
        else:
            super(AccountMove, self).action_post()




    def action_approve_order(self):

        template_id = self.env.ref(
            "account_dynamic_approval.email_template_for_approve_account_invoice")

        info = self.approval_info_line.filtered(
            lambda x: x.level == self.level)

        if info:
            info.status = True
            info.approval_date = datetime.now()
            info.approved_by = self.env.user

        line_id = self.env['sh.account.approval.line'].search(
            [('account_approval_config_id', '=', self.approval_level_id.id), ('level', '=', self.level)])

        next_line = self.env['sh.account.approval.line'].search(
            [('account_approval_config_id', '=', self.approval_level_id.id), ('id', '>', line_id.id)], limit=1)

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
                            'email_from': self.env.user.email, 'email_to': user.email, 'email_cc': self.user_id.email})

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
                            'email_from': self.env.user.email, 'email_to': user.email, 'email_cc': self.user_id.email})

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
                "account_dynamic_approval.email_template_for_confirm_account_invoice")
            if template_id:
                template_id.sudo().send_mail(self.id, force_send=True, email_values={
                    'email_from': self.env.user.email, 'email_to': self.user_id.email})

            notifications = []
            if self.user_id:
                notifications.append([self.user_id.partner_id, 'res.partner', {
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
            super(AccountMove, self).action_post()

    def action_reset_to_draft(self):
        self.write({
            'state': 'draft'
        })
