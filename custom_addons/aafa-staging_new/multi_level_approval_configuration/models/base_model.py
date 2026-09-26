##############################################################################
#
#    Copyright Domiup (<http://domiup.com>).
#
##############################################################################

from odoo import models
from odoo.exceptions import UserError


class BaseModel(models.AbstractModel):
    _inherit = "base"

    def write(self, vals):
        # NewId is falsy in Odoo 19; skip unsaved onchange records.
        records = self.filtered("id")
        if records:
            self.env["multi.approval.type"].check_rule(records, vals)
        res = super().write(vals)
        return res

    def _compute_field_value(self, field):
        """
        Check computed fields which stored=True
        """
        if field.store and any(self._ids):
            # check constraints of the fields that have been computed
            fake_vals = {f.name: 1 for f in self.pool.field_computed[field]}
            records = self.filtered("id")
            self.env["multi.approval.type"].check_rule(records, fake_vals)
        return super()._compute_field_value(field)

    def _get_pending_approval(self):
        """Return the submitted approval linked to this document (if any)."""
        self.ensure_one()
        if not self.id:
            return self.env["multi.approval"]
        return self.env["multi.approval"].search(
            [
                ("origin_ref", "=", f"{self._name},{self.id}"),
                ("state", "=", "Submitted"),
            ],
            limit=1,
        )

    def action_document_approve(self):
        """Approve from the source document when current user is the PIC/proxy."""
        for rec in self:
            approval = rec._get_pending_approval()
            if not approval:
                raise UserError(
                    self.env._("No pending approval request for this document.")
                )
            if not approval.is_pic:
                raise UserError(
                    self.env._("You are not the current approver for this document.")
                )
            approval.action_approve()
        return True

    def action_document_refuse(self):
        """Open refuse wizard for the pending approval of this document."""
        self.ensure_one()
        approval = self._get_pending_approval()
        if not approval:
            raise UserError(
                self.env._("No pending approval request for this document.")
            )
        if not approval.is_pic:
            raise UserError(
                self.env._("You are not the current approver for this document.")
            )
        # Prefer act_window._for_xml_id so readable fields include view/target/context (Odoo 19).
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "multi_level_approval.refused_reason_action"
        )
        action["context"] = {
            **self.env.context,
            "active_id": approval.id,
            "active_ids": approval.ids,
            "active_model": "multi.approval",
        }
        return action
