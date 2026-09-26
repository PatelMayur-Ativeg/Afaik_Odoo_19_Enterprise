# -*- coding: utf-8 -*-

from odoo import _, api, fields, models, Command
from odoo.exceptions import UserError


class AccountPaymentInvoices(models.Model):
    _name = 'account.payment.invoice'
    _description = "Payment Invoice Line"
    _order = 'sequence, id'

    CHECKED_SEQ_STEP = 10
    UNCHECKED_SEQ_BASE = 1000

    sequence = fields.Integer(string='Sequence', default=0)
    invoice_id = fields.Many2one('account.move', string='Invoice', index=True)
    move_type = fields.Selection(related="invoice_id.move_type", store=True)
    payment_id = fields.Many2one('account.payment', string='Payment')
    payment_reverse_id = fields.Many2one('account.payment', string='Payment')
    currency_id = fields.Many2one(related='invoice_id.currency_id')
    origin = fields.Char(related='invoice_id.invoice_origin')
    date_invoice = fields.Date(related='invoice_id.invoice_date')
    date_due = fields.Date(related='invoice_id.invoice_date_due')
    payment_state = fields.Selection(related='payment_id.state', store=True)
    reverse_payment_state = fields.Selection(related='payment_reverse_id.state', store=True)
    reconcile_amount = fields.Monetary(string='Reconcile Amount')
    amount_total = fields.Monetary(related="invoice_id.amount_total")
    residual = fields.Monetary(related="invoice_id.amount_residual")
    residual_reconcile = fields.Monetary("Amount Remaining Reconcile", compute="_compute_residual_reconcile", store=True, precompute=True, readonly=False)
    checked = fields.Boolean()

    def _get_sibling_lines(self):
        self.ensure_one()
        if self.payment_id:
            return self.payment_id.payment_invoice_ids
        if self.payment_reverse_id:
            return self.payment_reverse_id.payment_reversal_ids
        return self.env['account.payment.invoice']

    def _apply_check_sequence(self):
        """Move checked lines to top (low sequence); unchecked stay at bottom."""
        for rec in self:
            siblings = rec._get_sibling_lines() - rec
            if rec.checked:
                other_checked = siblings.filtered('checked')
                if other_checked:
                    rec.sequence = min(other_checked.mapped('sequence')) - rec.CHECKED_SEQ_STEP
                else:
                    rec.sequence = rec.CHECKED_SEQ_STEP
            else:
                other_unchecked = siblings.filtered(lambda l: not l.checked)
                if other_unchecked:
                    rec.sequence = max(other_unchecked.mapped('sequence')) + rec.CHECKED_SEQ_STEP
                else:
                    rec.sequence = rec.UNCHECKED_SEQ_BASE

    def write(self, vals):
        res = super().write(vals)
        if 'checked' in vals:
            self._apply_check_sequence()
        return res

    @api.depends('reconcile_amount', 'payment_id.state', 'payment_reverse_id.state')
    def _compute_residual_reconcile(self):
        for rec in self:
            payment = rec.payment_id or rec.payment_reverse_id
            if not payment or payment.state == 'draft':
                rec.residual_reconcile = rec.reconcile_amount

    @api.onchange('checked')
    def onchange_checked(self):
        if self.checked:
            self.reconcile_amount = self.residual
            self.residual_reconcile = self.residual
        else:
            self.reconcile_amount = 0
            self.residual_reconcile = 0

    @api.onchange('reconcile_amount')
    def _onchange_reconcile_amount(self):
        self.residual_reconcile = self.reconcile_amount

    def _get_related_payment(self):
        return (self.payment_id | self.payment_reverse_id)[:1]

    def _payment_excess_payload(self):
        payment = self._get_related_payment()
        return {
            'excess_amount': payment.excess_amount if payment else 0.0,
        }

    def action_get_payment_excess(self):
        """Return current excess after an embedded-list reconcile edit."""
        return self._payment_excess_payload()

    def action_toggle_checked(self):
        """Toggle line selection from the embedded list checkbox."""
        for line in self:
            line.checked = not line.checked
            if line.checked:
                line.reconcile_amount = line.residual
                line.residual_reconcile = line.residual
            else:
                line.reconcile_amount = 0
                line.residual_reconcile = 0
            line._apply_check_sequence()
        payload = self._payment_excess_payload()
        payload['lines'] = [{
            'id': line.id,
            'checked': line.checked,
            'reconcile_amount': line.reconcile_amount,
            'residual_reconcile': line.residual_reconcile,
            'sequence': line.sequence,
        } for line in self]
        return payload


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    invoice_id = fields.Many2one('account.move', string='Invoice', index=True)

    def _aml_values_map_with_custom_amount(self, all_amls):
        """Build the residual map used by `_reconcile_plan_with_sync`.

        When `amount` is in context, cap residuals so a payment can partially
        reconcile several invoices without consuming the full open balance.
        """
        custom_amount = self.env.context.get('amount')
        aml_values_map = {}
        for aml in all_amls:
            aml_residual = aml.amount_residual
            aml_residual_currency = aml.amount_residual_currency

            if custom_amount is not None:
                abs_custom_amount = abs(custom_amount)
                if aml_residual > 0:
                    aml_residual = min(abs_custom_amount, aml_residual)
                elif aml_residual < 0:
                    aml_residual = max(-abs_custom_amount, aml_residual)

                aml_residual = aml.company_currency_id.round(aml_residual)
                company_currency = aml.company_currency_id
                currency = aml.currency_id
                if currency and currency != company_currency:
                    aml_residual_currency = company_currency._convert(
                        aml_residual,
                        currency,
                        aml.company_id,
                        aml.move_id.date,
                    )
                else:
                    aml_residual_currency = aml_residual

            aml_values_map[aml] = {
                'aml': aml,
                'amount_residual': aml_residual,
                'amount_residual_currency': aml_residual_currency,
                'parent_state': aml.parent_state,
            }
        return aml_values_map

    def _reconcile_plan_with_sync(self, plan_list, all_amls):
        """Odoo 19 reconcile plan, plus partial amount and payment_id tracking."""
        custom_amount = self.env.context.get('amount')
        payment_id = self.env.context.get('payment')
        if custom_amount is None and not payment_id:
            return super()._reconcile_plan_with_sync(plan_list, all_amls)

        all_amls.move_id
        all_amls.matched_debit_ids
        all_amls.matched_credit_ids

        pre_hook_data = all_amls._reconcile_pre_hook()
        aml_values_map = self._aml_values_map_with_custom_amount(all_amls)

        partials_values_list = []
        exchange_diff_values_list = []
        all_plan_results = []
        for plan in plan_list:
            plan_results = self.with_context(
                no_exchange_difference=self.env.context.get('no_exchange_difference'),
                no_exchange_difference_no_recursive=self.env.context.get('no_exchange_difference_no_recursive', False),
            )._prepare_reconciliation_plan(plan, aml_values_map)
            all_plan_results.append(plan_results)
            for results in plan_results:
                partials_values_list.append(results['partial_values'])
                if results.get('exchange_values') and results['exchange_values']['move_values']['line_ids']:
                    exchange_diff_values_list.append(results['exchange_values'])

        partials = self.env['account.partial.reconcile'].create(partials_values_list)
        if payment_id:
            partials.write({'payment_id': payment_id})
        if self.env.context.get('add_caba_vals'):
            partials._set_draft_caba_move_vals()
        start_range = 0
        for plan_results, plan in zip(all_plan_results, plan_list):
            size = len(plan_results)
            plan['partials'] = partials[start_range:start_range + size]
            start_range += size

        exchange_moves = self._create_exchange_difference_moves(exchange_diff_values_list)
        used_exchange_moves = set()
        used_partials = set()

        for partial in partials:
            for exchange_move in exchange_moves:
                linked_move_lines = exchange_move.line_ids.reconciled_lines_ids
                if (
                    any(line == partial.debit_move_id or line == partial.credit_move_id for line in linked_move_lines)
                    and exchange_move not in used_exchange_moves
                    and partial not in used_partials
                ):
                    partial.exchange_move_id = exchange_move
                    used_exchange_moves.add(exchange_move)
                    used_partials.add(partial)

        def is_cash_basis_needed(amls):
            return any(amls.company_id.mapped('tax_exigibility')) \
                and amls.account_id.account_type in ('asset_receivable', 'liability_payable')

        if not self.env.context.get('move_reverse_cancel') and not self.env.context.get('no_cash_basis'):
            for plan in plan_list:
                if is_cash_basis_needed(plan['amls']):
                    plan['partials'].with_context(no_exchange_difference_no_recursive=False)._create_tax_cash_basis_moves()
                    plan['partials']._set_draft_caba_move_vals()

        def is_line_reconciled(aml, has_multiple_currencies):
            if aml.reconciled:
                return True
            if not aml.matched_debit_ids and not aml.matched_credit_ids:
                return False
            if has_multiple_currencies:
                return aml.company_currency_id.is_zero(aml.amount_residual)
            return aml.currency_id.is_zero(aml.amount_residual_currency)

        full_batches = []
        all_aml_ids = set()
        number2lines = all_amls._reconciled_by_number()
        for plan in plan_list:
            for aml in plan['amls']:
                if 'full_batch_index' in aml_values_map[aml]:
                    continue

                involved_amls = plan['amls']._filter_reconciled_by_number(number2lines)
                all_aml_ids.update(involved_amls.ids)
                full_batch_index = len(full_batches)
                has_multiple_currencies = len(involved_amls.currency_id) > 1
                is_fully_reconciled = all(
                    is_line_reconciled(involved_aml, has_multiple_currencies)
                    for involved_aml in involved_amls
                )
                full_batches.append({
                    'amls': involved_amls,
                    'is_fully_reconciled': is_fully_reconciled,
                })
                for involved_aml in involved_amls:
                    if aml_values_map.get(involved_aml):
                        aml_values_map[involved_aml]['full_batch_index'] = full_batch_index

        all_amls = self.browse(list(all_aml_ids))
        all_amls.move_id
        all_amls.matched_debit_ids
        all_amls.matched_credit_ids

        full_reconcile_values_list = []
        for full_batch in full_batches:
            amls = full_batch['amls']
            involved_partials = amls.matched_debit_ids + amls.matched_credit_ids
            if full_batch['is_fully_reconciled']:
                full_reconcile_values_list.append({
                    'partial_reconcile_ids': [Command.link(partial.id) for partial in involved_partials],
                    'reconciled_line_ids': [Command.link(aml.id) for aml in amls],
                })

        self.env['account.full.reconcile'].create(full_reconcile_values_list)

        for full_batch in full_batches:
            if not full_batch.get('caba_lines_to_reconcile'):
                continue

            caba_lines_to_reconcile = full_batch['caba_lines_to_reconcile']
            exchange_move = full_batch['exchange_move']
            for (_dummy, account, repartition_line), amls_to_reconcile in caba_lines_to_reconcile.items():
                if not account.reconcile:
                    continue

                exchange_line = exchange_move.line_ids.filtered(
                    lambda l: l.account_id == account and l.tax_repartition_line_id == repartition_line
                )
                (exchange_line + amls_to_reconcile).filtered(lambda l: not l.reconciled).reconcile()

        all_amls._reconcile_post_hook(pre_hook_data)


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    payment_invoice_ids = fields.One2many(
        'account.payment.invoice', 'payment_id', string="Customer Invoices", copy=False)
    payment_reversal_ids = fields.One2many(
        'account.payment.invoice', 'payment_reverse_id', string="Customer Credits", copy=False)
    excess_amount = fields.Monetary(
        string="Excess Amount",
        compute="_compute_excess_amount",
        store=False,
        help="Payment amount minus the sum of invoice/bill reconcile amounts "
             "(credits/refunds reduce the reconciled total).",
    )

    @api.depends(
        'amount',
        'currency_id',
        'payment_invoice_ids.reconcile_amount',
        'payment_reversal_ids.reconcile_amount',
        'payment_invoice_ids.checked',
        'payment_reversal_ids.checked',
    )
    def _compute_excess_amount(self):
        for payment in self:
            reconciled_amount = (
                sum(payment.payment_invoice_ids.mapped('reconcile_amount'))
                - sum(payment.payment_reversal_ids.mapped('reconcile_amount'))
            )
            excess = (payment.amount or 0.0) - reconciled_amount
            payment.excess_amount = (
                payment.currency_id.round(excess) if payment.currency_id else excess
            )

    def _get_open_moves_for_payment(self):
        self.ensure_one()
        invoice_type, reversal_type = self.get_move_types()
        base_domain = [
            ('partner_id', 'child_of', self.partner_id.id),
            ('state', '=', 'posted'),
            ('payment_state', 'not in', ('paid', 'reversed', 'blocked', 'invoicing_legacy')),
            ('currency_id', '=', self.currency_id.id),
            ('amount_residual', '>', 0),
            ('company_id', '=', self.company_id.id),
        ]
        invoice_recs = self.env['account.move'].search(base_domain + [('move_type', '=', invoice_type)])
        credit_recs = self.env['account.move'].search(base_domain + [('move_type', '=', reversal_type)])
        return invoice_recs, credit_recs

    def _build_payment_line_commands(self, moves):
        line_model = self.env['account.payment.invoice']
        seq_step = line_model.CHECKED_SEQ_STEP
        unchecked_base = line_model.UNCHECKED_SEQ_BASE
        commands = []
        for seq, move in enumerate(moves, start=1):
            commands.append(Command.create({
                'invoice_id': move.id,
                'sequence': unchecked_base + seq * seq_step,
            }))
        return commands

    def _sync_payment_lines_on_server(self, invoice_recs, credit_recs):
        """Persist lines on saved payments so embedded list views can load them."""
        self.ensure_one()
        line_model = self.env['account.payment.invoice']
        seq_step = line_model.CHECKED_SEQ_STEP
        unchecked_base = line_model.UNCHECKED_SEQ_BASE

        self.payment_invoice_ids.unlink()
        self.payment_reversal_ids.unlink()

        for seq, move in enumerate(invoice_recs, start=1):
            line_model.create({
                'payment_id': self.id,
                'invoice_id': move.id,
                'sequence': unchecked_base + seq * seq_step,
            })
        for seq, move in enumerate(credit_recs, start=1):
            line_model.create({
                'payment_reverse_id': self.id,
                'invoice_id': move.id,
                'sequence': unchecked_base + seq * seq_step,
            })

        self.payment_invoice_ids = [Command.set(self.payment_invoice_ids.ids)]
        self.payment_reversal_ids = [Command.set(self.payment_reversal_ids.ids)]

    @api.onchange('payment_type', 'partner_type', 'partner_id', 'currency_id')
    def _onchange_to_get_vendor_invoices(self):
        if not (self.payment_type and self.partner_type and self.partner_id and self.currency_id):
            return

        invoice_recs, credit_recs = self._get_open_moves_for_payment()

        if self.id:
            self._sync_payment_lines_on_server(invoice_recs, credit_recs)
        else:
            self.payment_invoice_ids = [Command.clear()] + self._build_payment_line_commands(invoice_recs)
            self.payment_reversal_ids = [Command.clear()] + self._build_payment_line_commands(credit_recs)

    def write(self, vals):
        res = super().write(vals)
        sync_fields = {'payment_type', 'partner_type', 'partner_id', 'currency_id'}
        if sync_fields & set(vals.keys()) and not {'payment_invoice_ids', 'payment_reversal_ids'} & set(vals):
            for payment in self.filtered(
                lambda p: p.partner_id and p.currency_id and p.payment_type and p.partner_type
            ):
                invoice_recs, credit_recs = payment._get_open_moves_for_payment()
                payment._sync_payment_lines_on_server(invoice_recs, credit_recs)
        return res

    def get_move_types(self):
        mapping = {
            ('customer', 'inbound'): ('out_invoice', 'out_refund'),
            ('customer', 'outbound'): ('out_refund', 'out_invoice'),
            ('supplier', 'outbound'): ('in_invoice', 'in_refund'),
            ('supplier', 'inbound'): ('in_refund', 'in_invoice'),
        }
        return mapping.get((self.partner_type, self.payment_type), (None, None))

    def _get_payment_lines(self):
        if self.payment_type == 'inbound':
            return self.move_id.line_ids.filtered(
                lambda l: l.credit > 0 and l.account_id.reconcile
            )
        return self.move_id.line_ids.filtered(
            lambda l: l.debit > 0 and l.account_id.reconcile
        )

    def _ensure_payment_move(self):
        """Odoo 19 may confirm a payment without a journal entry.

        Multi-invoice reconciliation needs posted counterpart lines, so create
        and post the move when it is missing.
        """
        self.ensure_one()
        if not self.move_id:
            if not self.outstanding_account_id:
                self.outstanding_account_id = self._get_outstanding_account(self.payment_type)
            self._generate_journal_entry()
        if self.move_id and self.move_id.state == 'draft':
            self.move_id.action_post()

    def action_post(self):
        super().action_post()

        for payment in self:
            payment._ensure_payment_move()

            invoice_type, reversal_type = payment.get_move_types()

            invoices = payment.payment_invoice_ids.filtered(lambda l: l.reconcile_amount > 0)
            credit_notes = payment.payment_reversal_ids.filtered(lambda l: l.reconcile_amount > 0)
            linked_moves = (invoices | credit_notes).mapped('invoice_id')
            if linked_moves:
                payment.invoice_ids = [Command.set(linked_moves.ids)]

            invoice_total = sum(invoices.mapped('reconcile_amount') or [0.0])
            credit_total = sum(credit_notes.mapped('reconcile_amount') or [0.0])
            net_required_payment = max(invoice_total - credit_total, 0)
            if not payment.currency_id.is_zero(payment.excess_amount):
                raise UserError(_("Payment Amount Is More Than The Reconciled Amount"))
            if payment.amount + 0.00001 < net_required_payment:
                raise UserError(_(
                    "Payment amount is insufficient.\n\n"
                    "Invoice Total: %(inv)s\n"
                    "Credit Notes Total: %(cr)s\n"
                    "Net Required: %(net)s\n"
                    "Payment Amount: %(pay)s"
                ) % {
                    'inv': invoice_total,
                    'cr': credit_total,
                    'net': net_required_payment,
                    'pay': payment.amount,
                })

            for cn_line in credit_notes.sorted('sequence'):
                if not cn_line.reconcile_amount or cn_line.residual_reconcile <= 0:
                    continue

                cn = cn_line.invoice_id
                remaining_cn = cn_line.residual_reconcile
                cn_lines = cn.line_ids.filtered(
                    lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable')
                    and not l.reconciled
                )
                if not cn_lines:
                    continue

                for inv_line in invoices.filtered(
                    lambda x: x.reconcile_amount > 0 and x.residual_reconcile > 0
                ).sorted('sequence'):
                    if remaining_cn <= 0:
                        break
                    if inv_line.residual_reconcile <= 0:
                        continue

                    inv = inv_line.invoice_id
                    if inv.move_type != invoice_type:
                        continue

                    inv_lines = inv.line_ids.filtered(
                        lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable')
                        and not l.reconciled
                    )
                    if not inv_lines:
                        continue

                    settle_amount = min(inv_line.residual_reconcile, remaining_cn)
                    if cn_lines.filtered(lambda l: not l.reconciled):
                        (cn_lines + inv_lines).with_context(
                            amount=-settle_amount,
                            payment=payment.id,
                        ).reconcile()
                        remaining_cn -= settle_amount
                        inv_line.residual_reconcile -= settle_amount
                        cn_line.residual_reconcile -= settle_amount

            payment_lines = payment._get_payment_lines()
            if not payment_lines:
                continue

            for line in invoices.filtered(
                lambda x: x.reconcile_amount > 0 and x.residual_reconcile > 0
            ).sorted('sequence'):
                if not line.reconcile_amount or line.residual_reconcile <= 0:
                    continue

                invoice = line.invoice_id
                if invoice.move_type == reversal_type:
                    continue

                invoice_lines = invoice.line_ids.filtered(
                    lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable') and not l.reconciled
                )
                if not invoice_lines:
                    continue

                open_payment = sum(payment_lines.mapped('amount_residual'))
                amount = min(line.residual_reconcile, abs(open_payment))
                if payment.currency_id.is_zero(amount):
                    break

                if payment.payment_type == 'inbound':
                    amount = -amount

                (payment_lines + invoice_lines).with_context(
                    amount=amount,
                    payment=payment.id,
                ).reconcile()
                line.residual_reconcile -= abs(amount)
        return True

    def action_draft(self):
        partials = self.env['account.partial.reconcile'].sudo().search(
            [('payment_id', 'in', self.ids)]
        )
        partials.unlink()
        res = super().action_draft()
        # invoice_ids is a stored m2m set on post. reconciled_invoice_ids
        # still includes it after unreconcile, so the payment stays linked
        # on the form, chatter, and invoice until this relation is cleared.
        self.invoice_ids = [Command.clear()]
        return res
