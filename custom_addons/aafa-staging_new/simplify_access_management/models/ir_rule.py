# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools,_
from odoo.exceptions import ValidationError, UserError
from odoo.tools import config
from odoo.osv import expression
from odoo.tools.safe_eval import safe_eval

class ir_rule(models.Model):
    _inherit = 'ir.rule'


    @api.model
    @tools.conditional(
        'xml' not in config['dev_mode'],
        tools.ormcache(
            'self.env.uid',
            'self.env.su',
            'model_name',
            'mode',
            'tuple(self._compute_domain_context_values())',
        ),
    )
    def _compute_domain(self, model_name, mode="read"):
        res = super()._compute_domain(model_name, mode)

        cr = self.env.cr
        user = self.env.user
        company = self.env.company

        # -------------------------------
        # Check module state
        # -------------------------------
        cr.execute("SELECT state FROM ir_module_module WHERE name=%s", ('simplify_access_management',))
        data = cr.fetchone()

        cr.execute("SELECT id FROM ir_module_module WHERE state IN %s", (('to upgrade', 'to remove', 'to install'),))
        all_data = cr.fetchone()

        read_value = not (data and data[0] != 'installed')

        model_list = [
            'mail.activity', 'res.users.log', 'res.users',
            'mail.channel', 'mail.alias', 'bus.presence', 'res.lang'
        ]

        # -------------------------------
        # Readonly user check
        # -------------------------------
        if user.id and read_value and not all_data and model_name not in model_list:
            cr.execute("""
                SELECT am.id FROM access_management am
                WHERE active = TRUE AND readonly = TRUE
                AND am.id IN (
                    SELECT au.access_management_id
                    FROM access_management_users_rel_ah au
                    WHERE user_id = %s
                    AND am.id IN (
                        SELECT ac.access_management_id
                        FROM access_management_comapnay_rel ac
                        WHERE ac.company_id = %s
                    )
                )
            """, (user.id, company.id))

            if cr.fetchone():
                if mode != 'read' and model_name != 'mail.channel.partner':
                    raise UserError(_('%s is a read-only user. So you cannot make changes!') % user.name)

        # -------------------------------
        # Config parameter check
        # -------------------------------
        cr.execute("""
            SELECT value FROM ir_config_parameter WHERE key=%s
        """, ('uninstall_simplify_access_management',))
        value = cr.fetchone()

        if not value:
            cr.execute("SELECT state FROM ir_module_module WHERE name=%s", ('simplify_access_management',))
            module_state = cr.fetchone()
            module_state = module_state and module_state[0]

            if model_name and module_state == 'installed':

                cr.execute("SELECT id FROM ir_model WHERE model=%s", (model_name,))
                model_row = cr.fetchone()
                model_id = model_row and model_row[0]

                if model_id and user:
                    cr.execute("""
                        SELECT dm.id
                        FROM access_domain_ah dm
                        WHERE dm.model_id = %s
                        AND dm.apply_domain
                        AND dm.access_management_id IN (
                            SELECT am.id FROM access_management am
                            WHERE active = TRUE
                            AND am.id IN (
                                SELECT amusr.access_management_id
                                FROM access_management_users_rel_ah amusr
                                WHERE amusr.user_id = %s
                            )
                        )
                    """, (model_id, user.id))

                    rows = cr.fetchall()
                    ids = [r[0] for r in rows]

                    if not ids:
                        return res

                    access_domains = self.env['access.domain.ah'].browse(ids).filtered(
                        lambda r: company in r.access_management_id.company_ids
                    )

                    if access_domains:
                        domain_list = []
                        eval_context = self._eval_context()

                        for access in access_domains.sudo():
                            dom = safe_eval(access.domain, eval_context) if access.domain else []
                            if dom:
                                dom = expression.normalize_domain(dom)
                                domain_list.append(dom)

                        if domain_list:
                            return expression.OR(domain_list)

        return res