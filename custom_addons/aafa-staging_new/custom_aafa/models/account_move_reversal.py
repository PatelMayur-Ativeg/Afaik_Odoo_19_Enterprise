from odoo import _, api, models


class AccountMoveReversal(models.TransientModel):
    _inherit = "account.move.reversal"

    @api.depends("move_ids")
    def _compute_journal_id(self):
        """Prefer the source journal's configured reversal journal."""
        for record in self:
            if record.journal_id:
                record.journal_id = record.journal_id
                continue
            journals = record.move_ids.journal_id.filtered(lambda j: j.active)
            if not journals:
                record.journal_id = False
                continue
            source = journals[0]
            reversal = source.reversal_journal_id
            record.journal_id = (
                reversal if reversal and reversal.active else source
            )

    def _prepare_default_reversal(self, move):
        """Keep the original move's ref on the reversed entry."""
        values = super()._prepare_default_reversal(move)
        values["ref"] = move.ref
        return values

    def reverse_moves(self, is_modify=False):
        """Create reversal moves in draft (never auto-post via cancel=True)."""
        self.ensure_one()
        moves = self.move_ids

        default_values_list = []
        for move in moves:
            default_values_list.append({
                "partner_bank_id": False,
                **self._prepare_default_reversal(move),
            })

        # Always cancel=False so the reversal stays draft (Odoo posts when cancel=True).
        new_moves = moves._reverse_moves(default_values_list, cancel=False)
        new_moves._compute_partner_bank_id()
        moves._message_log_batch(
            bodies={
                move.id: move.env._(
                    "This entry has been %s",
                    reverse._get_html_link(title=move.env._("reversed")),
                )
                for move, reverse in zip(moves, new_moves)
            }
        )

        if is_modify:
            moves_vals_list = []
            for move in moves.with_context(include_business_fields=True):
                data = move.copy_data(self._modify_default_reverse_values(move))[0]
                data["line_ids"] = [
                    line
                    for line in data["line_ids"]
                    if line[2]["display_type"]
                    in ("product", "line_section", "line_subsection", "line_note")
                ]
                moves_vals_list.append(data)
            new_moves = self.env["account.move"].create(moves_vals_list)
            new_moves._compute_partner_bank_id()

        self.new_move_ids = new_moves

        action = {
            "name": _("Reverse Moves"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
        }
        if len(new_moves) == 1:
            action.update({
                "view_mode": "form",
                "res_id": new_moves.id,
                "context": {"default_move_type": new_moves.move_type},
            })
        else:
            action.update({
                "view_mode": "list,form",
                "domain": [("id", "in", new_moves.ids)],
            })
            if len(set(new_moves.mapped("move_type"))) == 1:
                action["context"] = {
                    "default_move_type": new_moves.mapped("move_type").pop()
                }
        return action
