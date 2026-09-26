# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command


class AccountMove(models.Model):
    _inherit = "account.move"

    has_draft_deferred_moves = fields.Boolean(compute="_compute_has_draft_deferred_moves")

    @api.depends("state", "deferred_move_ids.state")
    def _compute_has_draft_deferred_moves(self):
        for move in self:
            move.has_draft_deferred_moves = (
                move.state == "posted"
                and any(deferred.state == "draft" for deferred in move.deferred_move_ids)
            )

    def _pop_imported_deferred_end_date_updates(self, values):
        """Pull deferred end-date o2m updates out of import vals.

        Odoo base import on bills/invoices writes
        ``invoice_line_ids`` as ``Command.link`` + ``Command.update``.
        Posted moves reject that One2many as readonly, so the date must
        be applied on the line instead.
        """
        self.ensure_one()
        updates = []
        extracted_line_ids = set()
        for field_name in ("invoice_line_ids", "line_ids"):
            commands = values.get(field_name)
            if not commands:
                continue
            remaining = []
            for command in commands:
                if (
                    command
                    and command[0] == Command.UPDATE
                    and len(command) >= 3
                    and isinstance(command[2], dict)
                    and "deferred_end_date" in command[2]
                ):
                    line_vals = dict(command[2])
                    new_end_date = line_vals.pop("deferred_end_date")
                    line = self.env["account.move.line"].browse(command[1]).exists()
                    if line:
                        updates.append((line, new_end_date))
                        extracted_line_ids.add(line.id)
                    if line_vals:
                        remaining.append(Command.update(command[1], line_vals))
                else:
                    remaining.append(command)

            remaining_update_ids = {
                command[1]
                for command in remaining
                if command and command[0] == Command.UPDATE
            }
            remaining = [
                command
                for command in remaining
                if not (
                    command
                    and command[0] == Command.LINK
                    and command[1] in extracted_line_ids
                    and command[1] not in remaining_update_ids
                )
            ]
            if remaining:
                values[field_name] = remaining
            else:
                values.pop(field_name, None)
        return updates

    def _load_records_write(self, values):
        # Vendor bill / invoice import writes nested invoice_line_ids.
        # Posted moves block that field, so reschedule the lines first.
        values = dict(values)
        for line, new_end_date in self._pop_imported_deferred_end_date_updates(values):
            line._apply_imported_deferred_end_date(new_end_date)
        super()._load_records_write(values)

    def _get_reschedulable_deferred_lines(self):
        return self.mapped("line_ids").filtered(
            lambda line: (
                line.deferred_start_date
                and line.deferred_end_date
                and line._has_deferred_compatible_account()
            )
        )

    def _check_can_reschedule_deferred(self):
        for move in self:
            if move.state != "posted":
                raise UserError(_("You can only reschedule deferrals on a posted invoice or bill."))
            if not move.deferred_move_ids:
                raise UserError(_("This document has no deferred entries."))
            if any(len(deferred.deferred_original_move_ids) > 1 for deferred in move.deferred_move_ids):
                raise UserError(_(
                    "You cannot reschedule grouped deferral entries. You can create a credit note instead."
                ))
            if not any(deferred.state == "draft" for deferred in move.deferred_move_ids):
                raise UserError(_("There are no unposted deferred entries left to reschedule."))
            if not move._get_reschedulable_deferred_lines():
                raise UserError(_("This document has no deferred invoice lines."))

    def _iter_reschedulable_moves(self):
        """Return posted moves that still have unposted deferrals, skipping the rest."""
        eligible = self.env["account.move"]
        for move in self:
            try:
                move._check_can_reschedule_deferred()
            except UserError:
                continue
            eligible |= move
        return eligible

    def action_open_reschedule_deferral(self):
        self.ensure_one()
        self._check_can_reschedule_deferred()
        wizard_lines = [
            Command.create(line._prepare_reschedule_wizard_line_vals())
            for line in self._get_reschedulable_deferred_lines()
        ]
        wizard = self.env["account.deferred.reschedule.wizard"].create({
            "move_id": self.id,
            "is_bulk": False,
            "line_ids": wizard_lines,
        })
        return self._action_open_reschedule_wizard(wizard)

    def action_open_reschedule_deferral_multi(self):
        eligible = self._iter_reschedulable_moves()
        if not eligible:
            raise UserError(_(
                "None of the selected documents can be rescheduled. "
                "Posted invoices/bills with unposted deferred entries are required."
            ))
        skipped = self - eligible
        warning_message = False
        if skipped:
            warning_message = _(
                "Skipped %(count)s document(s) that cannot be rescheduled: %(names)s",
                count=len(skipped),
                names=", ".join(skipped.mapped("display_name")),
            )
        wizard_lines = [
            Command.create(line._prepare_reschedule_wizard_line_vals())
            for line in eligible._get_reschedulable_deferred_lines()
        ]
        wizard = self.env["account.deferred.reschedule.wizard"].create({
            "move_id": eligible[:1].id,
            "is_bulk": True,
            "warning_message": warning_message,
            "line_ids": wizard_lines,
        })
        return self._action_open_reschedule_wizard(wizard, bulk=True)

    def _action_open_reschedule_wizard(self, wizard, bulk=False):
        return {
            "type": "ir.actions.act_window",
            "name": _("Reschedule Deferral") if not bulk else _("Bulk Reschedule Deferral"),
            "res_model": "account.deferred.reschedule.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
            "context": {"dialog_size": "extra-large"} if bulk else {},
        }
