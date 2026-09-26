# -*- coding: utf-8 -*-
from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon

from freezegun import freeze_time


@tagged("post_install", "-at_install")
class TestDeferredReschedule(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.expense_account = cls.env["account.account"].create({
            "name": "Deferred Test Expense",
            "code": "DEFTESTEXP",
            "account_type": "expense",
        })
        cls.company.deferred_expense_journal_id = cls.env["account.journal"].create({
            "name": "Deferred Expense Journal",
            "code": "DEFEXP",
            "type": "general",
            "company_id": cls.company.id,
        })
        cls.company.deferred_revenue_journal_id = cls.env["account.journal"].create({
            "name": "Deferred Revenue Journal",
            "code": "DEFREV",
            "type": "general",
            "company_id": cls.company.id,
        })
        cls.company.deferred_expense_account_id = cls.company_data["default_account_deferred_expense"].id
        cls.company.deferred_revenue_account_id = cls.company_data["default_account_deferred_revenue"].id
        cls.company.generate_deferred_expense_entries_method = "on_validation"
        cls.company.deferred_expense_amount_computation_method = "month"

    def _create_bill(self, price_unit, start_date, end_date, date="2023-01-01"):
        return self.env["account.move"].create({
            "move_type": "in_invoice",
            "partner_id": self.partner_a.id,
            "date": date,
            "invoice_date": date,
            "invoice_line_ids": [Command.create({
                "product_id": self.product_a.id,
                "account_id": self.expense_account.id,
                "price_unit": price_unit,
                "quantity": 1,
                "tax_ids": [Command.clear()],
                "deferred_start_date": start_date,
                "deferred_end_date": end_date,
            })],
        })

    def _get_source_line(self, move):
        return move.invoice_line_ids.filtered(
            lambda line: line.account_id == self.expense_account
        )[:1]

    def _get_recognition_moves(self, source_line):
        _full, posted, draft = source_line._get_deferred_moves_for_line()
        return posted, draft, posted | draft

    def _get_pnl_amount(self, source_line, move):
        pnl_line = source_line._get_deferred_pnl_line(move)
        return pnl_line.balance if pnl_line else 0.0

    @freeze_time("2023-04-01")
    def test_source_line_linked_on_generated_entries(self):
        bill = self._create_bill(12000, "2023-01-01", "2023-12-31")
        bill.action_post()
        source_line = self._get_source_line(bill)
        self.assertTrue(source_line)
        linked_moves = self.env["account.move.line"].search([
            ("deferred_source_line_id", "=", source_line.id),
        ]).move_id
        self.assertEqual(linked_moves, bill.deferred_move_ids)
        self.assertEqual(len(bill.deferred_move_ids), 13)

    @freeze_time("2023-04-01")
    def test_extend_end_date_keeps_posted_and_spreads_remaining(self):
        bill = self._create_bill(12000, "2023-01-01", "2023-12-31")
        bill.action_post()
        source_line = self._get_source_line(bill)
        posted, draft, recognition = self._get_recognition_moves(source_line)
        self.assertEqual(len(posted), 3)
        self.assertEqual(len(draft), 9)
        posted_amounts = [self._get_pnl_amount(source_line, move) for move in posted.sorted("date")]
        self.assertEqual(posted_amounts, [1000.0, 1000.0, 1000.0])
        posted_ids = posted.ids
        full_moves, _, _ = source_line._get_deferred_moves_for_line()
        full_amount = self._get_pnl_amount(source_line, full_moves[:1])
        self.assertEqual(full_amount, -12000.0)

        wizard_action = bill.action_open_reschedule_deferral()
        wizard = self.env["account.deferred.reschedule.wizard"].browse(wizard_action["res_id"])
        self.assertFalse(wizard.is_bulk)
        self.assertEqual(wizard.move_id, bill)
        self.assertEqual(len(wizard.line_ids), 1)
        self.assertEqual(wizard.line_ids.posted_amount, 3000.0)
        self.assertEqual(wizard.line_ids.remaining_amount, 9000.0)
        wizard.line_ids.new_end_date = "2024-04-30"
        self.assertEqual(wizard.line_ids.remaining_period_count, 13)
        wizard.action_confirm()

        source_line.invalidate_recordset()
        bill.invalidate_recordset(["deferred_move_ids"])
        self.assertEqual(source_line.deferred_end_date, fields.Date.to_date("2024-04-30"))
        posted_after, draft_after, recognition_after = self._get_recognition_moves(source_line)
        self.assertEqual(sorted(posted_after.ids), sorted(posted_ids))
        self.assertEqual(len(draft_after), 13)
        self.assertEqual(len(recognition_after), 16)
        for move in posted_after.sorted("date"):
            self.assertEqual(self._get_pnl_amount(source_line, move), 1000.0)
        full_after, _, _ = source_line._get_deferred_moves_for_line()
        self.assertEqual(self._get_pnl_amount(source_line, full_after[:1]), -12000.0)

        draft_amounts = [
            source_line.company_currency_id.round(self._get_pnl_amount(source_line, move))
            for move in draft_after.sorted("date")
        ]
        self.assertEqual(source_line.company_currency_id.round(sum(draft_amounts)), 9000.0)
        equal_share = source_line.company_currency_id.round(9000.0 / 13)
        self.assertTrue(all(
            source_line.company_currency_id.compare_amounts(amount, equal_share) in (0, -1, 1)
            and abs(amount - equal_share) < 0.02
            for amount in draft_amounts[:-1]
        ))
        self.assertEqual(source_line.company_currency_id.round(sum(draft_amounts[:-1]) + draft_amounts[-1]), 9000.0)

    @freeze_time("2023-04-01")
    def test_shorten_end_date_unlinks_extra_drafts(self):
        bill = self._create_bill(12000, "2023-01-01", "2023-12-31")
        bill.action_post()
        source_line = self._get_source_line(bill)
        posted, draft, _recognition = self._get_recognition_moves(source_line)
        self.assertEqual(len(draft), 9)
        posted_ids = posted.ids

        wizard_action = bill.action_open_reschedule_deferral()
        wizard = self.env["account.deferred.reschedule.wizard"].browse(wizard_action["res_id"])
        wizard.line_ids.new_end_date = "2023-08-31"
        self.assertEqual(wizard.line_ids.remaining_period_count, 5)
        wizard.action_confirm()

        posted_after, draft_after, recognition_after = self._get_recognition_moves(source_line)
        self.assertEqual(sorted(posted_after.ids), sorted(posted_ids))
        self.assertEqual(len(draft_after), 5)
        self.assertEqual(len(recognition_after), 8)
        self.assertEqual(source_line.deferred_end_date, fields.Date.to_date("2023-08-31"))
        for move in posted_after:
            self.assertEqual(self._get_pnl_amount(source_line, move), 1000.0)
        draft_amounts = [
            source_line.company_currency_id.round(self._get_pnl_amount(source_line, move))
            for move in draft_after.sorted("date")
        ]
        self.assertEqual(draft_amounts, [1800.0, 1800.0, 1800.0, 1800.0, 1800.0])
        self.assertEqual(max(draft_after.mapped("date")), fields.Date.to_date("2023-08-31"))

    @freeze_time("2023-04-01")
    def test_new_end_date_before_last_posted_period_raises(self):
        bill = self._create_bill(12000, "2023-01-01", "2023-12-31")
        bill.action_post()
        source_line = self._get_source_line(bill)

        wizard_action = bill.action_open_reschedule_deferral()
        wizard = self.env["account.deferred.reschedule.wizard"].browse(wizard_action["res_id"])
        wizard.line_ids.new_end_date = "2023-03-15"
        with self.assertRaises(UserError):
            wizard.action_confirm()
        self.assertEqual(source_line.deferred_end_date, fields.Date.to_date("2023-12-31"))
        _posted, draft, recognition = self._get_recognition_moves(source_line)
        self.assertEqual(len(draft), 9)
        self.assertEqual(len(recognition), 12)

    @freeze_time("2023-04-01")
    def test_bulk_wizard_apply_date_and_confirm(self):
        bill1 = self._create_bill(12000, "2023-01-01", "2023-12-31")
        bill2 = self._create_bill(6000, "2023-01-01", "2023-12-31")
        (bill1 | bill2).action_post()

        action = (bill1 | bill2).action_open_reschedule_deferral_multi()
        wizard = self.env["account.deferred.reschedule.wizard"].browse(action["res_id"])
        self.assertTrue(wizard.is_bulk)
        self.assertEqual(len(wizard.line_ids), 2)
        self.assertEqual(set(wizard.line_ids.mapped("move_id").ids), set((bill1 | bill2).ids))

        wizard.apply_end_date = "2024-06-30"
        wizard.action_apply_end_date_to_all()
        self.assertEqual(
            set(wizard.line_ids.mapped("new_end_date")),
            {fields.Date.to_date("2024-06-30")},
        )
        wizard.action_confirm()

        self.assertEqual(self._get_source_line(bill1).deferred_end_date, fields.Date.to_date("2024-06-30"))
        self.assertEqual(self._get_source_line(bill2).deferred_end_date, fields.Date.to_date("2024-06-30"))

    @freeze_time("2023-04-01")
    def test_bulk_wizard_skips_ineligible_moves(self):
        posted = self._create_bill(12000, "2023-01-01", "2023-12-31")
        draft = self._create_bill(6000, "2023-01-01", "2023-12-31")
        posted.action_post()

        action = (posted | draft).action_open_reschedule_deferral_multi()
        wizard = self.env["account.deferred.reschedule.wizard"].browse(action["res_id"])
        self.assertTrue(wizard.warning_message)
        self.assertEqual(wizard.line_ids.move_id, posted)

    @freeze_time("2023-04-01")
    def test_base_import_load_reschedules_deferred_end_date(self):
        bill1 = self._create_bill(12000, "2023-01-01", "2023-12-31")
        bill2 = self._create_bill(6000, "2023-01-01", "2023-12-31")
        (bill1 | bill2).action_post()
        line1 = self._get_source_line(bill1)
        line2 = self._get_source_line(bill2)
        posted1, draft1, _recognition1 = self._get_recognition_moves(line1)
        posted1_ids = posted1.ids
        self.assertEqual(len(draft1), 9)

        result = self.env["account.move.line"].with_context(import_file=True).load(
            [".id", "deferred_end_date"],
            [
                [str(line1.id), "2024-06-30"],
                [str(line2.id), "2024-04-30"],
            ],
        )
        error_messages = [
            message for message in result.get("messages") or []
            if message.get("type") == "error"
        ]
        self.assertFalse(error_messages, error_messages)
        self.assertEqual(line1.deferred_end_date, fields.Date.to_date("2024-06-30"))
        self.assertEqual(line2.deferred_end_date, fields.Date.to_date("2024-04-30"))

        posted_after, draft_after, _recognition_after = self._get_recognition_moves(line1)
        self.assertEqual(sorted(posted_after.ids), sorted(posted1_ids))
        self.assertEqual(len(draft_after), 15)
        self.assertEqual(max(draft_after.mapped("date")), fields.Date.to_date("2024-06-30"))

    @freeze_time("2023-04-01")
    def test_bill_import_invoice_line_ids_reschedules_deferred_end_date(self):
        """Vendor Bill import writes invoice_line_ids, which is readonly on posted moves."""
        bill = self._create_bill(12000, "2023-01-01", "2023-12-31")
        bill.action_post()
        source_line = self._get_source_line(bill)
        posted, draft, _recognition = self._get_recognition_moves(source_line)
        posted_ids = posted.ids
        self.assertEqual(len(draft), 9)

        result = self.env["account.move"].with_context(import_file=True).load(
            [".id", "invoice_line_ids/.id", "invoice_line_ids/deferred_end_date"],
            [[str(bill.id), str(source_line.id), "2024-06-30"]],
        )
        error_messages = [
            message for message in result.get("messages") or []
            if message.get("type") == "error"
        ]
        self.assertFalse(error_messages, error_messages)
        self.assertEqual(source_line.deferred_end_date, fields.Date.to_date("2024-06-30"))

        posted_after, draft_after, _recognition_after = self._get_recognition_moves(source_line)
        self.assertEqual(sorted(posted_after.ids), sorted(posted_ids))
        self.assertEqual(len(draft_after), 15)
        self.assertEqual(max(draft_after.mapped("date")), fields.Date.to_date("2024-06-30"))

    @freeze_time("2023-04-01")
    def test_bill_load_records_write_link_update_commands(self):
        """Import converter emits Command.link + Command.update on invoice_line_ids."""
        bill = self._create_bill(12000, "2023-01-01", "2023-12-31")
        bill.action_post()
        source_line = self._get_source_line(bill)
        posted, _draft, _recognition = self._get_recognition_moves(source_line)
        posted_ids = posted.ids

        bill.with_context(import_file=True)._load_records_write({
            "invoice_line_ids": [
                Command.link(source_line.id),
                Command.update(source_line.id, {"deferred_end_date": fields.Date.to_date("2024-06-30")}),
            ],
        })

        self.assertEqual(source_line.deferred_end_date, fields.Date.to_date("2024-06-30"))
        posted_after, draft_after, _recognition_after = self._get_recognition_moves(source_line)
        self.assertEqual(sorted(posted_after.ids), sorted(posted_ids))
        self.assertEqual(len(draft_after), 15)

    @freeze_time("2023-04-01")
    def test_load_records_write_reschedules_like_wizard(self):
        bill = self._create_bill(12000, "2023-01-01", "2023-12-31")
        bill.action_post()
        source_line = self._get_source_line(bill)
        posted, _draft, _recognition = self._get_recognition_moves(source_line)
        posted_ids = posted.ids

        source_line.with_context(import_file=True)._load_records_write({
            "deferred_end_date": fields.Date.to_date("2023-08-31"),
        })

        posted_after, draft_after, _recognition_after = self._get_recognition_moves(source_line)
        self.assertEqual(source_line.deferred_end_date, fields.Date.to_date("2023-08-31"))
        self.assertEqual(sorted(posted_after.ids), sorted(posted_ids))
        self.assertEqual(len(draft_after), 5)
        self.assertEqual(
            [
                source_line.company_currency_id.round(self._get_pnl_amount(source_line, move))
                for move in draft_after.sorted("date")
            ],
            [1800.0, 1800.0, 1800.0, 1800.0, 1800.0],
        )
