# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountDeferredRescheduleWizard(models.TransientModel):
    _name = "account.deferred.reschedule.wizard"
    _description = "Reschedule Deferred End Date"

    move_id = fields.Many2one(
        comodel_name="account.move",
        string="Invoice/Bill",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    is_bulk = fields.Boolean(readonly=True)
    warning_message = fields.Text(readonly=True)
    apply_end_date = fields.Date(string="Set New End Date On All Lines")
    company_currency_id = fields.Many2one(related="move_id.company_currency_id")
    line_ids = fields.One2many(
        comodel_name="account.deferred.reschedule.wizard.line",
        inverse_name="wizard_id",
        string="Deferred Lines",
    )

    def _reopen(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Bulk Reschedule Deferral") if self.is_bulk else _("Reschedule Deferral"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": {"dialog_size": "extra-large"} if self.is_bulk else {},
        }

    def action_confirm(self):
        self.ensure_one()
        if self.is_bulk:
            self.line_ids.source_line_id.move_id._check_can_reschedule_deferred()
        else:
            self.move_id._check_can_reschedule_deferred()
        for line in self.line_ids:
            line.source_line_id._reschedule_deferred_end_date(line.new_end_date)
        return {"type": "ir.actions.act_window_close"}

    def action_apply_end_date_to_all(self):
        self.ensure_one()
        if not self.apply_end_date:
            raise UserError(_("Please set a date to apply to all lines."))
        self.line_ids.write({"new_end_date": self.apply_end_date})
        return self._reopen()


class AccountDeferredRescheduleWizardLine(models.TransientModel):
    _name = "account.deferred.reschedule.wizard.line"
    _description = "Reschedule Deferred End Date Line"
    _order = "move_id, id"

    wizard_id = fields.Many2one(
        comodel_name="account.deferred.reschedule.wizard",
        required=True,
        ondelete="cascade",
    )
    source_line_id = fields.Many2one(
        comodel_name="account.move.line",
        string="Source Line",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    move_id = fields.Many2one(
        comodel_name="account.move",
        string="Invoice/Bill",
        readonly=True,
        ondelete="cascade",
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Partner",
        readonly=True,
        ondelete="set null",
    )
    name = fields.Char(string="Label", readonly=True)
    product_id = fields.Many2one(comodel_name="product.product", string="Product", readonly=True)
    company_currency_id = fields.Many2one(related="wizard_id.company_currency_id")
    original_amount = fields.Monetary(string="Original Amount", currency_field="company_currency_id", readonly=True)
    posted_amount = fields.Monetary(string="Posted Amount", currency_field="company_currency_id", readonly=True)
    remaining_amount = fields.Monetary(string="Remaining Amount", currency_field="company_currency_id", readonly=True)
    deferred_start_date = fields.Date(string="Start Date", readonly=True)
    deferred_end_date = fields.Date(string="Current End Date", readonly=True)
    remaining_start_date = fields.Date(string="Remaining Start Date", readonly=True)
    new_end_date = fields.Date(string="New End Date", required=True)
    remaining_period_count = fields.Integer(
        string="Remaining Periods",
        compute="_compute_preview",
    )
    new_period_amount = fields.Monetary(
        string="New Period Amount",
        currency_field="company_currency_id",
        compute="_compute_preview",
    )

    @api.depends("new_end_date", "remaining_start_date", "remaining_amount")
    def _compute_preview(self):
        for line in self:
            if (
                not line.new_end_date
                or not line.remaining_start_date
                or line.new_end_date < line.remaining_start_date
            ):
                line.remaining_period_count = 0
                line.new_period_amount = 0.0
                continue
            periods = line.source_line_id._get_remaining_deferred_periods(
                line.remaining_start_date,
                line.new_end_date,
            ) if line.source_line_id else []
            line.remaining_period_count = len(periods)
            line.new_period_amount = (
                line.remaining_amount / len(periods) if periods else 0.0
            )
