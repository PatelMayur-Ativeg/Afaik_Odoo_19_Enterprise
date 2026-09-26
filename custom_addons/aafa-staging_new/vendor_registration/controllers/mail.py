from odoo import http, fields, exceptions,_
from odoo.http import request
# from odoo.addons.portal.controllers.mail import PortalChatter

class PortalChatterInh(http.Controller):

    @http.route(['/mail/chatter_post'], type='json', methods=['POST'], auth='public', website=True)
    def portal_chatter_post(self, res_model, res_id, message, attachment_ids=None, attachment_tokens=None, **kw):
        res = super(PortalChatterInh, self).portal_chatter_post(res_model, res_id, message, attachment_ids, attachment_tokens, **kw)
        if (message or attachment_ids) and res_model == 'purchase.order':
            record = request.env[res_model].browse(res_id)
            group = request.env.ref(
                'vendor_registration.vendor_po_notification_group',
                raise_if_not_found=False,
            )
            users = request.env['res.users'].sudo().search(
                [('group_ids', 'in', group.ids)]
            ) if group else request.env['res.users']
            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
            subject = 'Vendor Sent a Message'

            body = '{} has sent an message or attachment.'.format(record.partner_id.name ) + ' Click here to check: <a target=_BLANK href="{}/web?#id='.format(
                base_url) + str(
                record.id) + '&view_type=form&model=vendor.registration&action=" style="font-weight: bold">' + str(
                record.name) + '</a>'
            request.env['user.notify'].send_email(body, users, subject)
        return res