##############################################################################
#
#    Copyright Domiup (<http://domiup.com>).
#
##############################################################################

from odoo import api, models
from odoo.fields import Domain


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        domain = Domain(domain or Domain.TRUE)
        ctx = self._context
        if ctx.get("has_deputy_groups"):
            group_ids = ctx["has_deputy_groups"]
            if group_ids and isinstance(group_ids, list | tuple):
                sql = """
                    SELECT uid FROM res_groups_users_rel WHERE gid IN %s
                """
                self._cr.execute(sql, (tuple(group_ids),))
                user_ids = [x[0] for x in self._cr.fetchall()]
                domain &= Domain("id", "in", user_ids)
        return super().name_search(name, domain, operator, limit)
