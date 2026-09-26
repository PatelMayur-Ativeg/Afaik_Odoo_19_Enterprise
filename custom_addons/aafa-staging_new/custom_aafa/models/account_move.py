from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from .transaction_type import (
    IMPORTER_TRANSACTION_TYPES,
    MOVE_TYPE_TRANSACTION_TYPES,
    TRANSACTION_TYPE_SELECTION,
)


class AccountMove(models.Model):
    _inherit = "account.move"

    _unique_vendor_bill_ref = models.UniqueIndex(
        "(partner_id, ref, company_id, move_type)"
        " WHERE (move_type IN ('in_invoice', 'in_refund')"
        " AND state != 'cancel'"
        " AND ref IS NOT NULL"
        " AND btrim(ref) != '')",
        "A bill or refund with this Vendor and Bill Reference already exists.",
    )

    transaction_type = fields.Selection(
        selection=TRANSACTION_TYPE_SELECTION,
        string="Transaction Type",
        compute="_compute_transaction_type",
        store=True,
        precompute=True,
        index=True,
        help="Importer queue record type when created from Aafaq Importer; "
             "linked payment type when created from a payment; "
             "otherwise the standard move type.",
    )

    @api.depends(
        "move_type",
        "origin_payment_id",
        "origin_payment_id.transaction_type",
    )
    def _compute_transaction_type(self):
        for move in self:
            move.transaction_type = move._get_transaction_type()

    def _get_import_queue(self):
        """Return linked aafaq import queue when aafaq_importer is installed."""
        self.ensure_one()
        if "affaq_queue_id" not in self._fields:
            return False
        return self.affaq_queue_id

    def _get_transaction_type(self):
        """Resolve transaction type for this move.

        Priority:
        1. Aafaq import queue record type (JV / AE) when importer is installed
           — checked before move_type because imported entries use move_type 'entry'
        2. Linked payment (journal entry created from a payment)
        3. Standard account.move move_type
        """
        self.ensure_one()
        queue = self._get_import_queue()
        if queue and getattr(queue, "record_type", None) in IMPORTER_TRANSACTION_TYPES:
            return queue.record_type
        if self.origin_payment_id and self.origin_payment_id.transaction_type:
            return self.origin_payment_id.transaction_type
        if self.move_type in MOVE_TYPE_TRANSACTION_TYPES:
            return self.move_type
        return "entry"

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        if "affaq_queue_id" not in self._fields:
            return moves
        # Precompute may store generic 'entry'; re-apply importer queue type.
        imported = moves.filtered(
            lambda m: m.affaq_queue_id
            and m.affaq_queue_id.record_type in IMPORTER_TRANSACTION_TYPES
        )
        if imported:
            imported._compute_transaction_type()
        return moves

    @api.model
    def _recompute_imported_transaction_types(self):
        """Fix stored transaction_type on moves linked to JV/AE import queues."""
        if "affaq_queue_id" not in self._fields:
            return True
        moves = self.search([
            ("affaq_queue_id", "!=", False),
            ("affaq_queue_id.record_type", "in", list(IMPORTER_TRANSACTION_TYPES)),
        ])
        if moves:
            moves._compute_transaction_type()
        return True

    @api.constrains("partner_id", "ref", "move_type", "company_id", "state")
    def _check_unique_vendor_bill_ref(self):
        for move in self:
            if (
                move.move_type not in ("in_invoice", "in_refund")
                or not move.partner_id
                or not (move.ref or "").strip()
                or move.state == "cancel"
            ):
                continue
            duplicate = self.search(
                [
                    ("id", "!=", move.id),
                    ("move_type", "=", move.move_type),
                    ("partner_id", "=", move.partner_id.id),
                    ("ref", "=", move.ref),
                    ("company_id", "=", move.company_id.id),
                    ("state", "!=", "cancel"),
                ],
                limit=1,
            )
            if duplicate:
                raise ValidationError(
                    _(
                        "A %(doc_type)s with Vendor '%(vendor)s' and Bill Reference "
                        "'%(ref)s' already exists (%(name)s)."
                    )
                    % {
                        "doc_type": dict(move._fields["move_type"].selection).get(
                            move.move_type, move.move_type
                        ),
                        "vendor": move.partner_id.display_name,
                        "ref": move.ref,
                        "name": duplicate.name if duplicate.name != "/" else duplicate.display_name,
                    }
                )
