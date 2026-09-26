from odoo import api, fields, tools, models, _
from datetime import datetime
import logging


_logger = logging.getLogger(__name__)



class ExpensesRejectionReasonWizard(models.TransientModel):
    _name = 'sh.expenses.reject.reason.wizard'

    name = fields.Char(string="Reason", required=True)

    def action_expenses_reject_order(self):

        active_obj = self.env[self.env.context.get('active_model')].browse(
            self.env.context.get('active_id'))
        active_obj.write({
            'reject_reason': self.name,
            'reject_by': self.env.uid,
            'rejection_date': datetime.now(),
            'state': 'reject',
        })

        template_id = active_obj.env.ref(
            "sh_expenses_dynamic_approval.email_template_for_reject_expenses_request")

        if template_id:
            template_id.sudo().send_mail(active_obj.id, force_send=True, email_values={
                'email_from': active_obj.env.user.email, 'email_to': active_obj.employee_id.user_id.email})

        notifications = []
        if active_obj.employee_id:
            notifications.append([active_obj.employee_id.address_home_id, 'res.partner', {
                'title': _('Notitification'),
                'message': 'Dear User!! your PR %s is rejected' % (active_obj.name),
                'sticky': True,
                'warning': True
            }])
            active_obj.env['bus.bus']._sendone(notifications)
