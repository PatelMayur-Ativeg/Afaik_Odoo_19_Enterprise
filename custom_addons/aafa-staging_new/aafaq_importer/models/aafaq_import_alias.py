import ast

from odoo import api, fields, models, _

from .aafaq_import_constants import (
    HELD_EMAIL_RECORD_TYPES,
    RECORD_TYPE_ALIAS_NAME,
    RECORD_TYPE_JOURNAL_MAP,
    RECORD_TYPE_SELECTION,
)


class AafaqImportAlias(models.Model):
    _name = "aafaq.import.alias"
    _description = "Aafaq Import Email Alias"
    _inherit = ["mail.alias.mixin"]
    _order = "record_type, id"

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    record_type = fields.Selection(RECORD_TYPE_SELECTION, required=True, index=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Journal",
        domain="[('company_id', '=', company_id)]",
        help="Used for Journal / Adjustment entry imports created from this alias.",
    )
    user_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        domain="[('share', '=', False)]",
        help="Optional default salesperson set on queues created from this alias.",
    )
    queue_count = fields.Integer(compute="_compute_queue_count")
    held_mail_count = fields.Integer(compute="_compute_held_mail_count")
    suggested_alias_name = fields.Char(compute="_compute_suggested_alias_name")

    _record_type_company_uniq = models.Constraint(
        "unique(record_type, company_id)",
        "Only one email alias is allowed per record type and company.",
    )

    @api.depends("record_type")
    def _compute_suggested_alias_name(self):
        for record in self:
            record.suggested_alias_name = RECORD_TYPE_ALIAS_NAME.get(record.record_type) or ""

    def _compute_queue_count(self):
        counts = {}
        if self.ids:
            grouped = self.env["aafaq.import.queue"]._read_group(
                [("alias_config_id", "in", self.ids)],
                ["alias_config_id"],
                ["__count"],
            )
            counts = {alias.id: count for alias, count in grouped}
        for record in self:
            record.queue_count = counts.get(record.id, 0)

    def _compute_held_mail_count(self):
        counts = {}
        if self.ids:
            grouped = self.env["aafaq.import.held.mail"]._read_group(
                [("alias_config_id", "in", self.ids), ("state", "=", "onhold")],
                ["alias_config_id"],
                ["__count"],
            )
            counts = {alias.id: count for alias, count in grouped}
        for record in self:
            record.held_mail_count = counts.get(record.id, 0)

    @api.onchange("record_type", "company_id")
    def _onchange_record_type(self):
        if self.record_type and not self.name:
            label = dict(RECORD_TYPE_SELECTION).get(self.record_type)
            self.name = label
        if self.record_type and not self.alias_name:
            self.alias_name = RECORD_TYPE_ALIAS_NAME.get(self.record_type)
        if self.record_type in RECORD_TYPE_JOURNAL_MAP:
            self.journal_id = self._default_journal(self.record_type, self.company_id)
        else:
            self.journal_id = False

    def _default_journal(self, record_type, company):
        journal_name = RECORD_TYPE_JOURNAL_MAP.get(record_type)
        if not journal_name:
            return False
        domain = [("name", "=", journal_name)]
        if company:
            domain.append(("company_id", "=", company.id))
        return self.env["account.journal"].search(domain, limit=1)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            record_type = vals.get("record_type")
            if record_type and not vals.get("name"):
                vals["name"] = dict(RECORD_TYPE_SELECTION).get(record_type)
            if record_type and not vals.get("alias_name"):
                vals["alias_name"] = RECORD_TYPE_ALIAS_NAME.get(record_type)
            if record_type in RECORD_TYPE_JOURNAL_MAP and not vals.get("journal_id"):
                company = self.env["res.company"].browse(
                    vals.get("company_id") or self.env.company.id
                )
                journal = self._default_journal(record_type, company)
                if journal:
                    vals["journal_id"] = journal.id
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        sync_fields = {"record_type", "company_id", "journal_id", "user_id", "active"}
        if sync_fields & set(vals):
            for record in self.filtered("alias_id"):
                record.alias_id.sudo().write(record._alias_get_creation_values())
        return res

    def _alias_get_creation_values(self):
        values = super()._alias_get_creation_values()
        target_model = (
            "aafaq.import.held.mail"
            if self.record_type in HELD_EMAIL_RECORD_TYPES
            else "aafaq.import.queue"
        )
        values["alias_model_id"] = self.env["ir.model"]._get(target_model).id
        values["alias_contact"] = self.alias_contact or "everyone"
        values["alias_incoming_local"] = True
        if self.id:
            defaults = {}
            if self.alias_defaults:
                try:
                    defaults = dict(ast.literal_eval(self.alias_defaults))
                except (ValueError, SyntaxError):
                    defaults = {}
            defaults.update(self._prepare_alias_defaults())
            values["alias_defaults"] = repr(defaults)
        return values

    @api.model
    def _retarget_held_mail_aliases(self):
        """Keep alias targets in sync: JV/AE -> held.mail, all others (incl. COA) -> import.queue."""
        aliases = self.search([("alias_id", "!=", False)])
        for record in aliases:
            record.alias_id.sudo().write(record._alias_get_creation_values())

    def _prepare_alias_defaults(self):
        self.ensure_one()
        journal = self.journal_id or self._default_journal(self.record_type, self.company_id)
        return {
            "record_type": self.record_type,
            "company_id": self.company_id.id,
            "journal_id": journal.id if journal else False,
            "user_id": self.user_id.id if self.user_id else False,
            "import_source": "email",
            "alias_config_id": self.id,
        }

    def action_view_queues(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Import Queues"),
            "res_model": "aafaq.import.queue",
            "view_mode": "list,form",
            "domain": [("alias_config_id", "=", self.id)],
            "context": {"default_alias_config_id": self.id},
        }

    def action_view_held_mails(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Held Emails"),
            "res_model": "aafaq.import.held.mail",
            "view_mode": "list,form",
            "domain": [("alias_config_id", "=", self.id), ("state", "=", "onhold")],
            "context": {
                "default_alias_config_id": self.id,
                "search_default_filter_onhold": 1,
            },
        }
