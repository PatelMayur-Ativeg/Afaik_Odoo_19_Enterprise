# -*- coding: utf-8 -*-

from datetime import timedelta, date

from dateutil.relativedelta import relativedelta
from odoo import models, fields


class Document(models.Model):
    _inherit = 'documents.document'
    expiry_date = fields.Date('Expiry Date', tracking=True, default=fields.Date.today() + relativedelta(years=1))
    notify_before = fields.Integer('Notify Before', tracking=True, default=30)

    def mail_reminder(self):
        date_now = date.today() + timedelta(days=1)
        match = self.search([])
        print('Match >>>>>>>>>>>>>', match)
        for i in match:
            if i.expiry_date:
                exp_date = i.expiry_date - timedelta(days=i.notify_before)
                if date_now == exp_date:
                    template_id = self.env.ref('document_expiry.notify_document_expire_email')
                    template_id.send_mail(i.id, force_send=True)
