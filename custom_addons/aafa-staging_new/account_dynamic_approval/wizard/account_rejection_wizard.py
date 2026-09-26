from odoo import api, fields, tools, models, _
from datetime import datetime

from ..models.approval_tools import send_approval_notifications


class RejectionReasonWizard(models.TransientModel):
    _name = 'account.reject.reason.wizard'

    name = fields.Char(string="Reason", required=True)

    def action_reject_order(self):
        active_obj = self.env[self.env.context.get('active_model')].browse(
            self.env.context.get('active_id'))
        active_obj.write({
            'reject_reason': self.name,
            'reject_by': active_obj.env.user,
            'rejection_date': datetime.now(),
            'state': 'reject',
        })

        template_id = active_obj.env.ref(
            "account_dynamic_approval.email_template_for_reject_account_invoice")

        if template_id:
            template_id.sudo().send_mail(active_obj.id, force_send=True, email_values={
                'email_from': active_obj.env.user.email, 'email_to': active_obj.user_id.email})

        notifications = []
        if active_obj.user_id:
            notifications.append([active_obj.user_id.partner_id, 'res.partner', {
                'title': _('Notitification'),
                'message': 'Dear User!! your Purchase order %s is rejected' % (active_obj.name),
                'sticky': True,
                'warning': True
            }])
            send_approval_notifications(active_obj.env, notifications)


class PaymentRejectionReasonWizard(models.TransientModel):
    _name = 'payment.reject.reason.wizard'

    name = fields.Char(string="Reason", required=True)

    def action_reject_order(self):
        active_obj = self.env[self.env.context.get('active_model')].browse(
            self.env.context.get('active_id'))
        active_obj.write({
            'reject_reason': self.name,
            'reject_by': active_obj.env.user,
            'rejection_date': datetime.now(),
            'state': 'reject',
        })

        template_id = active_obj.env.ref(
            "account_dynamic_approval.email_template_for_reject_vendor_payment")

        if template_id:
            template_id.sudo().send_mail(active_obj.id, force_send=True, email_values={
                'email_from': active_obj.env.user.email, 'email_to': active_obj.create_uid.email})

        notifications = []
        if active_obj.create_uid:
            notifications.append([active_obj.create_uid.partner_id, 'res.partner', {
                'title': _('Notitification'),
                'message': 'Dear User!! your Record %s is rejected' % (active_obj.name),
                'sticky': True,
                'warning': True
            }])
            send_approval_notifications(active_obj.env, notifications)

class BatchPaymentRejectionReasonWizard(models.TransientModel):
    _name = 'batch.payment.reject.reason.wizard'

    name = fields.Char(string="Reason", required=True)

    def action_reject_order(self):
        active_obj = self.env[self.env.context.get('active_model')].browse(
            self.env.context.get('active_id'))
        active_obj.write({
            'reject_reason': self.name,
            'reject_by': active_obj.env.user,
            'rejection_date': datetime.now(),
            'state': 'reject',
        })

        template_id = active_obj.env.ref(
            "account_dynamic_approval.email_template_for_reject_batch_payment")

        if template_id:
            template_id.sudo().send_mail(active_obj.id, force_send=True, email_values={
                'email_from': active_obj.env.user.email, 'email_to': active_obj.create_uid.email})

        notifications = []
        if active_obj.create_uid:
            notifications.append([active_obj.create_uid.partner_id, 'res.partner', {
                'title': _('Notitification'),
                'message': 'Dear User!! your Record %s is rejected' % (active_obj.name),
                'sticky': True,
                'warning': True
            }])
            send_approval_notifications(active_obj.env, notifications)