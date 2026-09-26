# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class RejectReasonWizard(models.TransientModel):
    _name = "reject.reason.wizard"
    
    reject_reason = fields.Char("Reject Reason")

    def action_reject_reason_apply(self):
        register_vals = self.env['vendor.registration'].browse(self.env.context.get('active_ids'))
        register_vals.write({
            'reject_reason': self.reject_reason,
            'state': 'rejected'
        })
        register_vals.send_create_vendor_reject_notify(self.env.user)
        return True
    
