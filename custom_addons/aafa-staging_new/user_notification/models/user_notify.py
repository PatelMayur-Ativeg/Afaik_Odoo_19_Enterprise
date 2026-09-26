# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class Notification(models.TransientModel):
    _name = 'user.notify'

    def send_email(self, body, users, subject):
        for user in users:
            if user.email:
                mails_send = self.env['mail.mail'].sudo().create({
                    'subject': subject,
                    'body_html': '<p><strong>Dear ' + str(user.name) + '</strong></p><br></br>' + str(body),
                    'auto_delete': True,
                    'email_to': user.email,
                    'message_type': 'email',
                })

                mails_send.send()

    def send_user_notification(self, users, record, name, msg):
        if users:
            msg_id = self.env['mail.message'].create({
                'message_type': "comment",
                "subtype_id": self.env.ref("mail.mt_comment").id,
                'body': "Dear Sir<br></br>" + msg + "<br></br> Best Regards",
                'subject': name,
                'partner_ids': [(4, user.partner_id.id) for user in users],
                'model': record._name,
                'res_id': record.id,
            })
            for user in users:
                notify_id = self.env['mail.notification'].create({
                    'mail_message_id': msg_id.id,
                    'res_partner_id': user.partner_id.id,
                    'notification_type': 'inbox',
                    'notification_status': 'exception',
                })
                print(notify_id)

    def create_activity(self, obj, users, summary):
        for user in users:
            model_id = self.env['ir.model']._get(obj._name).id
            activity = self.env['mail.activity'].sudo().create({
                'res_id': obj.id,
                'res_model_id': model_id,
                'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                'summary': summary,
                'user_id': user.id,
                'date_deadline': fields.date.today()
            })

    def done_activity(self, obj):
        model_id = self.env['ir.model']._get(obj._name).id
        activities = self.env['mail.activity'].search([
            ('res_id', '=', obj.id),
            ('res_model_id', '=', model_id),
        ])
        if activities:
            activities.sudo().action_done()
