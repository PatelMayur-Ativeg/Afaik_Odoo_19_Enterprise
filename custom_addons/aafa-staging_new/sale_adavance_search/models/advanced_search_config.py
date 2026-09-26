# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


DEFAULT_MODELS = (
    "sale.order",
    "account.move",
    "account.move.line",
    "stock.picking",
)
DEFAULT_FIELDS = ("name", "origin", "internal_id", "asn_no")
SEARCHABLE_TTYPES = (
    "char",
    "text",
    "html",
    "selection",
    "many2one",
    "integer",
    "float",
)


class AdvancedSearchConfig(models.Model):
    _name = "advanced.search.config"
    _description = "Comma-separated Advanced Search"
    _order = "model_id"

    model_id = fields.Many2one(
        "ir.model",
        string="Model",
        required=True,
        ondelete="cascade",
        index=True,
        domain="[('transient', '=', False), ('abstract', '=', False)]",
    )
    model_name = fields.Char(related="model_id.model", store=True, index=True)
    field_ids = fields.Many2many(
        "ir.model.fields",
        "advanced_search_config_field_rel",
        "config_id",
        "field_id",
        string="Search Fields",
        domain="[('model_id', '=', model_id), ('ttype', 'in', %s)]"
        % (list(SEARCHABLE_TTYPES),),
        help="Search bar fields that accept comma-separated values, e.g. SO001,SO002.",
    )
    field_names = fields.Char(compute="_compute_field_names", string="Fields")
    active = fields.Boolean(default=True)

    _model_uniq = models.Constraint(
        "unique(model_id)",
        "Advanced search is already configured for this model.",
    )

    @api.depends("field_ids")
    def _compute_field_names(self):
        for rec in self:
            rec.field_names = ", ".join(rec.field_ids.mapped("name"))

    @api.onchange("model_id")
    def _onchange_model_id(self):
        if self.field_ids and self.field_ids.mapped("model_id") != self.model_id:
            self.field_ids = False

    @api.model
    def _get_session_mapping(self):
        mapping = {}
        for rec in self.sudo().search([("active", "=", True), ("field_ids", "!=", False)]):
            if rec.model_name:
                mapping[rec.model_name] = rec.field_ids.mapped("name")
        return mapping

    @api.model
    def _install_defaults(self):
        """Seed configs for the original hardcoded models/fields, if still missing."""
        IrModel = self.env["ir.model"].sudo()
        IrField = self.env["ir.model.fields"].sudo()
        for model_name in DEFAULT_MODELS:
            model = IrModel.search([("model", "=", model_name)], limit=1)
            if not model or self.search([("model_id", "=", model.id)], limit=1):
                continue
            search_fields = IrField.search([
                ("model_id", "=", model.id),
                ("name", "in", list(DEFAULT_FIELDS)),
            ])
            if not search_fields:
                continue
            self.create({
                "model_id": model.id,
                "field_ids": [fields.Command.set(search_fields.ids)],
            })
