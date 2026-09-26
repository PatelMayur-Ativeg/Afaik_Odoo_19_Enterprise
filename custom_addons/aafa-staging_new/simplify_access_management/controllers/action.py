# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
from odoo.exceptions import UserError

from odoo.addons.web.controllers.home import Home
from odoo.addons.web.controllers.utils import ensure_db
from odoo.addons.web.controllers.action import Action


# =====================================================
# Action Controller Extension (SAFE)
# =====================================================
class CustomActionController(Action):

    @http.route('/web/action/load', type='jsonrpc', auth="user")
    def load(self, action_id, additional_context=None):
        result = super().load(action_id, additional_context=additional_context)

        if not result:
            return result

        cids = request.httprequest.cookies.get('cids')
        try:
            cids = int(cids.split(',')[0]) if cids else request.env.company.id
        except Exception:
            cids = request.env.company.id

        remove_views = request.env['remove.action'].sudo().search([
            ('view_data_ids', '!=', False),
            ('access_management_id.company_ids', 'in', cids),
            ('access_management_id', 'in', request.env.user.access_management_ids.ids),
            ('model_id.model', '=', result.get('res_model'))
        ]).mapped('view_data_ids.techname')

        if result.get('views'):
            result['views'] = [
                v for v in result['views']
                if v[1] not in remove_views
            ]

        if result.get('views') and not result['views']:
            raise UserError(_("You don't have permission to access any views."))

        return result


# =====================================================
# Home Controller Extension (SAFE)
# =====================================================
class HomeExtended(Home):

    @http.route()
    def web_client(self, s_action=None, **kw):
        ensure_db()
        # request.env['ir.ui.view'].flush_recordset()
        # request.env.flush_all()
        # request.env['ir.qweb'].clear_caches()
        # request.env['ir.actions.actions'].clear_caches()
        # request.env.registry.clear_cache()
        request.env.registry.clear_all_caches()
        
        user = request.env.user.browse(request.session.uid)
        # if len(user.company_ids) > 1:
        #     request.env['ir.ui.menu'].clear_caches()
        if not kw.get('debug') or kw.get('debug') != "0":
            cids = request.httprequest.cookies.get('cids') and request.httprequest.cookies.get('cids').split(',')[0] or request.env.company.id
            access_management = request.env['access.management'].sudo().search([('active','=',True),('disable_debug_mode','=',True),('user_ids','in',user.id)],limit=1)
            
            # cids = list(map(lambda l:int(l) ,cids.split("-")))
            if access_management and access_management.is_apply_on_without_company:
                return request.redirect('/web?debug=0')
            elif cids in access_management.company_ids.ids:
                return request.redirect('/web?debug=0')
                # request.session.debug = '0'

        return super(HomeExtended, self).web_client(s_action=s_action, **kw)
