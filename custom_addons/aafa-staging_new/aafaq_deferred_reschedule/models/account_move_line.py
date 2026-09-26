# -*- coding: utf-8 -*-
from datetime import timedelta
from itertools import chain

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tools import format_date
from odoo.tools.misc import formatLang


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    deferred_source_line_id = fields.Many2one(
        comodel_name="account.move.line",
        string="Deferred Source Line",
        index="btree_not_null",
        copy=False,
        ondelete="set null",
        help="Invoice/bill line that generated this deferral journal item.",
    )

    @api.model
    def _get_deferred_lines_values(self, account_id, balance, ref, analytic_distribution, line=None):
        values = super()._get_deferred_lines_values(
            account_id, balance, ref, analytic_distribution, line=line
        )
        source_line_id = False
        if line is not None and not isinstance(line, dict) and line.ids:
            source_line_id = line.id
        elif isinstance(line, dict):
            source_line_id = line.get("id") or line.get("deferred_source_line_id")
        if source_line_id:
            values["deferred_source_line_id"] = source_line_id
        return values

    def _load_records_write(self, values):
        # Only Odoo base import uses this path. The invoice form wizard calls
        # `_reschedule_deferred_end_date` directly and must stay unchanged.
        if "deferred_end_date" in values:
            self._apply_imported_deferred_end_date(values.pop("deferred_end_date"))
        super()._load_records_write(values)

    def _apply_imported_deferred_end_date(self, new_end_date):
        """Apply an imported deferred end date without writing posted invoice lines."""
        self.ensure_one()
        if self._should_reschedule_on_import(new_end_date):
            self._reschedule_deferred_end_date(new_end_date)
            return
        new_end_date = fields.Date.to_date(new_end_date) if new_end_date else new_end_date
        if new_end_date != self.deferred_end_date:
            self.with_context(skip_readonly_check=True).write({
                "deferred_end_date": new_end_date,
            })

    def _should_reschedule_on_import(self, new_end_date):
        self.ensure_one()
        move = self.move_id
        if not move.is_invoice(include_receipts=True) or move.state != "posted":
            return False
        if not self.deferred_start_date or not self.deferred_end_date:
            return False
        if not self._has_deferred_compatible_account():
            return False
        if not move.deferred_move_ids:
            return False
        if self.display_type in ("line_section", "line_note"):
            return False
        return fields.Date.to_date(new_end_date) != self.deferred_end_date

    def _get_deferred_pnl_line(self, move):
        """Return the P&L journal item of a deferral move that matches this source line."""
        self.ensure_one()
        pnl_lines = move.line_ids.filtered(lambda aml: aml.account_id == self.account_id)
        linked = pnl_lines.filtered(lambda aml: aml.deferred_source_line_id == self)
        if linked:
            return linked[:1]
        if self.product_id:
            pnl_lines = pnl_lines.filtered(lambda aml: aml.product_id == self.product_id)
        return pnl_lines[:1]

    def _is_full_deferral_move(self, move):
        """True if `move` is the initial full reversal of this source line."""
        self.ensure_one()
        pnl_line = self._get_deferred_pnl_line(move)
        if not pnl_line:
            return False
        return self.company_currency_id.compare_amounts(pnl_line.balance, -self.balance) == 0

    def _get_candidate_deferred_moves(self):
        """Return deferral journal entries belonging to this invoice line."""
        self.ensure_one()
        linked_lines = self.env["account.move.line"].search([
            ("deferred_source_line_id", "=", self.id),
            ("move_id", "in", self.move_id.deferred_move_ids.ids),
        ])
        if linked_lines:
            return linked_lines.move_id

        siblings = self.move_id.line_ids.filtered(
            lambda line: (
                line != self
                and line.deferred_start_date
                and line.account_id == self.account_id
                and line.product_id == self.product_id
            )
        )
        candidates = self.env["account.move"]
        for deferred_move in self.move_id.deferred_move_ids:
            if self._get_deferred_pnl_line(deferred_move):
                candidates |= deferred_move
        if siblings and candidates:
            raise UserError(_(
                "Unable to uniquely match deferred entries for %(line)s. "
                "Several invoice lines share the same account and product.",
                line=self.display_name,
            ))
        return candidates

    def _get_deferred_moves_for_line(self):
        """
        Split this line's deferral entries into:
        - the initial full deferral
        - posted recognition moves
        - draft recognition moves
        """
        self.ensure_one()
        full_moves = self.env["account.move"]
        posted_recognition = self.env["account.move"]
        draft_recognition = self.env["account.move"]
        for move in self._get_candidate_deferred_moves():
            if self._is_full_deferral_move(move):
                full_moves |= move
            elif move.state == "posted":
                posted_recognition |= move
            elif move.state == "draft":
                draft_recognition |= move
        return full_moves, posted_recognition, draft_recognition

    def _get_posted_deferred_recognition_balance(self, posted_recognition=None):
        self.ensure_one()
        if posted_recognition is None:
            _full, posted_recognition, _draft = self._get_deferred_moves_for_line()
        posted_balance = 0.0
        for move in posted_recognition:
            pnl_line = self._get_deferred_pnl_line(move)
            posted_balance += pnl_line.balance if pnl_line else 0.0
        return self.company_currency_id.round(posted_balance)

    def _get_remaining_deferred_start_date(self, posted_recognition=None):
        self.ensure_one()
        if posted_recognition is None:
            _full, posted_recognition, _draft = self._get_deferred_moves_for_line()
        if posted_recognition:
            return max(posted_recognition.mapped("date")) + timedelta(days=1)
        return self.deferred_start_date

    def _get_remaining_deferred_periods(self, start_date, end_date):
        return [
            (max(start_date, date.replace(day=1)), min(date, end_date), "current")
            for date in self._get_deferred_ends_of_month(start_date, end_date)
        ]

    def _prepare_reschedule_wizard_line_vals(self):
        self.ensure_one()
        _full, posted_recognition, _draft = self._get_deferred_moves_for_line()
        posted_amount = self._get_posted_deferred_recognition_balance(posted_recognition)
        remaining_amount = self.company_currency_id.round(self.balance - posted_amount)
        remaining_start = self._get_remaining_deferred_start_date(posted_recognition)
        return {
            "source_line_id": self.id,
            "move_id": self.move_id.id,
            "partner_id": self.move_id.partner_id.id,
            "name": self.name,
            "product_id": self.product_id.id,
            "original_amount": self.balance,
            "posted_amount": posted_amount,
            "remaining_amount": remaining_amount,
            "deferred_start_date": self.deferred_start_date,
            "deferred_end_date": self.deferred_end_date,
            "remaining_start_date": remaining_start,
            "new_end_date": self.deferred_end_date,
        }

    def _check_deferred_reschedule(self, new_end_date, posted_recognition=None, remaining_amount=None):
        self.ensure_one()
        if self.move_id.state != "posted":
            raise UserError(_("You can only reschedule deferrals on a posted invoice or bill."))
        if not self.deferred_start_date or not self.deferred_end_date:
            raise UserError(_("This line has no deferred dates."))
        if any(len(move.deferred_original_move_ids) > 1 for move in self.move_id.deferred_move_ids):
            raise UserError(_(
                "You cannot reschedule grouped deferral entries. You can create a credit note instead."
            ))
        if not new_end_date:
            raise UserError(_("Please set a new deferred end date."))
        if new_end_date < self.deferred_start_date:
            raise UserError(_("The new deferred end date cannot be before the deferred start date."))

        if posted_recognition is None:
            _full, posted_recognition, _draft = self._get_deferred_moves_for_line()
        if posted_recognition:
            last_posted_date = max(posted_recognition.mapped("date"))
            if new_end_date <= last_posted_date:
                raise UserError(_(
                    "The new deferred end date must be after the last posted deferral date (%(date)s).",
                    date=format_date(self.env, last_posted_date),
                ))

        if remaining_amount is None:
            remaining_amount = self.balance - self._get_posted_deferred_recognition_balance(posted_recognition)
        if self.company_currency_id.is_zero(remaining_amount):
            raise UserError(_("There is no remaining deferred amount to reschedule."))

        remaining_start = self._get_remaining_deferred_start_date(posted_recognition)
        periods = self._get_remaining_deferred_periods(remaining_start, new_end_date)
        if not periods:
            raise UserError(_("The new deferred end date does not leave any remaining period to recognize."))
        return remaining_start, periods, remaining_amount

    def _prepare_remaining_deferred_line_values(self, remaining_start, new_end_date, remaining_amount):
        self.ensure_one()
        return {
            "id": self.id,
            "deferred_start_date": remaining_start,
            "deferred_end_date": new_end_date,
            "balance": remaining_amount,
            "account_id": self.account_id,
            "product_id": self.product_id.id,
            "product_category_id": self.product_category_id.id,
            "move_id": self.move_id.id,
            "deferred_source_line_id": self.id,
        }

    def _create_remaining_deferred_recognition_moves(self, periods, remaining_amount):
        """Create recognition entries for remaining periods using the leftover balance."""
        self.ensure_one()
        deferred_type = "expense" if self.account_id.internal_group == "expense" else "revenue"
        company = self.company_id
        deferred_account = (
            company.deferred_expense_account_id
            if deferred_type == "expense"
            else company.deferred_revenue_account_id
        )
        deferred_journal = (
            company.deferred_expense_journal_id
            if deferred_type == "expense"
            else company.deferred_revenue_journal_id
        )
        if not deferred_journal:
            raise UserError(_("Please set the deferred journal in the accounting settings."))
        if not deferred_account:
            raise UserError(_("Please set the deferred accounts in the accounting settings."))

        remaining_start = periods[0][0]
        new_end = periods[-1][1]
        virtual_line = self._prepare_remaining_deferred_line_values(
            remaining_start, new_end, remaining_amount
        )
        ref = _("Deferral of %s", self.move_id.name or "")
        move_vals_template = {
            "move_type": "entry",
            "deferred_original_move_ids": [Command.set(self.move_id.ids)],
            "journal_id": deferred_journal.id,
            "company_id": company.id,
            "partner_id": self.partner_id.id,
            "auto_post": "at_date",
            "ref": ref,
            "name": False,
        }

        deferral_moves_vals = []
        deferral_moves_line_vals = []
        leftover = remaining_amount
        AccountMove = self.env["account.move"]
        for period_index, period in enumerate(periods):
            force_balance = leftover if period_index == len(periods) - 1 else None
            deferred_amounts = AccountMove._get_deferred_amounts_by_line(
                [virtual_line], [period], deferred_type
            )[0]
            balance = deferred_amounts[period] if force_balance is None else force_balance
            leftover -= self.company_currency_id.round(balance)
            deferral_moves_vals.append({**move_vals_template, "date": period[1]})
            deferral_moves_line_vals.append([
                {
                    **self._get_deferred_lines_values(
                        account.id,
                        coeff * balance,
                        ref,
                        self.analytic_distribution,
                        self,
                    ),
                    "partner_id": self.partner_id.id,
                    "product_id": self.product_id.id,
                }
                for (account, coeff) in [(deferred_amounts["account_id"], 1), (deferred_account, -1)]
            ])

        deferral_moves = AccountMove.create(deferral_moves_vals)
        for deferral_move, lines_vals in zip(deferral_moves, deferral_moves_line_vals):
            for line_vals in lines_vals:
                line_vals["move_id"] = deferral_move.id
        self.env["account.move.line"].create(list(chain(*deferral_moves_line_vals)))

        to_unlink = deferral_moves.filtered(lambda move: move.currency_id.is_zero(move.amount_total))
        to_unlink.unlink()
        remaining_moves = deferral_moves - to_unlink
        if remaining_moves:
            remaining_moves._post(soft=True)
        return remaining_moves

    def _reschedule_deferred_end_date(self, new_end_date):
        """Keep posted recognition entries and rebuild unposted ones for the new end date."""
        self.ensure_one()
        new_end_date = fields.Date.to_date(new_end_date)
        full_moves, posted_recognition, draft_recognition = self._get_deferred_moves_for_line()
        if not full_moves and not posted_recognition and not draft_recognition:
            raise UserError(_("No deferred entries were found for this line."))

        remaining_amount = self.balance - self._get_posted_deferred_recognition_balance(posted_recognition)
        remaining_start, periods, remaining_amount = self._check_deferred_reschedule(
            new_end_date,
            posted_recognition=posted_recognition,
            remaining_amount=remaining_amount,
        )
        old_end_date = self.deferred_end_date
        if new_end_date == old_end_date:
            return self.env["account.move"]

        draft_recognition.unlink()
        self.with_context(skip_readonly_check=True).write({
            "deferred_end_date": new_end_date,
        })
        new_moves = self._create_remaining_deferred_recognition_moves(periods, remaining_amount)

        posted_amount = self._get_posted_deferred_recognition_balance(posted_recognition)
        self.move_id.message_post(body=_(
            "Deferred end date for %(line)s changed from %(old_end)s to %(new_end)s. "
            "Posted amount %(posted)s kept. Remaining %(remaining)s redistributed over "
            "%(periods)s period(s) starting %(remaining_start)s.",
            line=self.name or self.product_id.display_name or self.display_name,
            old_end=format_date(self.env, old_end_date),
            new_end=format_date(self.env, new_end_date),
            posted=formatLang(self.env, posted_amount, currency_obj=self.company_currency_id),
            remaining=formatLang(self.env, remaining_amount, currency_obj=self.company_currency_id),
            periods=len(periods),
            remaining_start=format_date(self.env, remaining_start),
        ))
        return new_moves
