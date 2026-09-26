from odoo import models, fields, api
import base64
import requests
import logging

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _name = "res.partner"
    _inherit = ["res.partner"]

    aafaq_queue_id = fields.Many2one('aafaq.import.queue', ondelete='set null', string='Import Queue')
    internal_id = fields.Char(
        string="Internal ID", help="Reference ID from Internal system Aafaq", index=True, copy=False)
    customer_type = fields.Selection([
        ("customer", "Financing Customers"),
        ("customer_wakala_asset", "Wakala Assets Customers"),
        ("customer_wakala_lib", "Wakala Liability Customers"),
    ])
    finacle_acct_num = fields.Char(string="Finacle Account Number")
    cif_id = fields.Char(string="CIF ID")
    scheme_description = fields.Char(string="CIF ID")

    schm_code = fields.Char(string="Scheme Code")
    gl_sub_head_code = fields.Char("GL Sub Head Code")
    currency_code = fields.Char("Currence Code")
    account_id = fields.Many2one(
        'account.account',
        string="Chart of Account",
        tracking=True
    )

    gl_analytic_account_ids = fields.Many2many(
        'account.analytic.account',
        'res_partner_gl_analytic_account_rel',
        'partner_id',
        'analytic_account_id',
        string="GL Analytic Accounts",
        help="Analytic accounts for GL",
    )

    scheme_analytic_account_ids = fields.Many2many(
        'account.analytic.account',
        'res_partner_scheme_analytic_account_rel',
        'partner_id',
        'analytic_account_id',
        string="Scheme Analytic Accounts",
        help="Analytic accounts for Scheme",
    )

    segment_analytic_account_ids = fields.Many2many(
        'account.analytic.account',
        'res_partner_segment_analytic_account_rel',
        'partner_id',
        'analytic_account_id',
        string="Segment Analytic Accounts",
        help="Analytic accounts for Segment",
    )

    subsegment_analytic_account_ids = fields.Many2many(
        'account.analytic.account',
        'res_partner_subsegment_analytic_account_rel',
        'partner_id',
        'analytic_account_id',
        string="Subsegment Analytic Accounts",
        help="Analytic accounts for Subsegment",
    )

    adv_type_analytic_account_ids = fields.Many2many(
        'account.analytic.account',
        'res_partner_adv_type_analytic_account_rel',
        'partner_id',
        'analytic_account_id',
        string="Advance Type Analytic Accounts",
        help="Analytic accounts for Advance Type",
    )
    gl_desc = fields.Char(string="GL Description")
    fs_classification = fields.Char(string="FS Classification")

    def get_analytic_distribution(self, normalize=False):
        """Build analytic_distribution dict from stored analytic accounts (100% each)."""
        self.ensure_one()

        accounts = (
            self.scheme_analytic_account_ids
            | self.gl_analytic_account_ids
            | self.adv_type_analytic_account_ids
        )

        result = {str(account.id): 100 for account in accounts}

        if normalize and result:
            total = sum(result.values())
            if total:
                result = {k: (v / total) * 100 for k, v in result.items()}

        return result

    def _parse_m2m_ids(self, commands):
        """Extract record ids from Many2many write commands or a bare id list."""
        if not commands:
            return []
        if isinstance(commands, (list, tuple)) and commands and isinstance(commands[0], int):
            return list(commands)
        ids = []
        for command in commands:
            if not command:
                continue
            if command[0] == 6:
                ids.extend(command[2] or [])
            elif command[0] in (4, 1) and command[1]:
                ids.append(command[1])
        return ids

    def _process_tags(self, vals):
        for tag_field in (
            'scheme_analytic_account_ids',
            # 'gl_analytic_account_ids',  # replace on import, do not merge
            'segment_analytic_account_ids',
            'subsegment_analytic_account_ids',
            'adv_type_analytic_account_ids',
        ):
            if tag_field in vals:
                new_ids = self._parse_m2m_ids(vals[tag_field])
                vals[tag_field] = [(6, 0, list(set(self[tag_field].ids + new_ids)))]

    def write(self, vals):
        if self.env.context.get('use_import'):
            self._process_tags(vals)
        return super().write(vals)
