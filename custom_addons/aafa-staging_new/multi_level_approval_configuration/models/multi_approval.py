##############################################################################
#
#    Copyright Domiup (<http://domiup.com>).
#
##############################################################################

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class MultiApproval(models.Model):
    _inherit = "multi.approval"

    origin_ref = fields.Reference(string="Origin", selection="_selection_target_model")
    company_id = fields.Many2one('res.company', string='Company')

    def action_submit(self):
        recs = self.filtered(lambda x: x.state == "Draft" and x.origin_ref)
        res = super().action_submit()
        for rec in recs:
            rec.type_id.run(rec, rec.origin_ref, "submit")
        return res

    @api.model
    def _selection_target_model(self):
        models = self.env["ir.model"].search([])
        return [(model.model, model.name) for model in models]

    def update_source_obj(self, obj, result="approved", log_msg=""):
        if not obj:
            return False
        obj.write(
            {
                "x_review_result": result,
            }
        )
        if log_msg and hasattr(obj, "message_post"):
            obj.message_post(body=log_msg)

    def _log_approval_on_origin(self):
        """Post an approval note on the source document for this approver."""
        self.ensure_one()
        if not self.origin_ref or not hasattr(self.origin_ref, "message_post"):
            return
        log_msg = self.env._(
            "%(name)s has approved this document !", name=self.env.user.name
        )
        self.origin_ref.message_post(body=log_msg)

    def finalize_related_document(self):
        # Mark the source as fully approved. Per-approver chatter notes are
        # posted from action_approve so every level is logged, not only the last.
        self.update_source_obj(self.origin_ref)

    def action_approve(self):
        pending_line_ids = {
            rec.id: rec.line_id.id
            for rec in self.filtered(lambda x: x.state == "Submitted" and x.line_id)
        }
        result = super().action_approve()
        Line = self.env["multi.approval.line"]
        for approval_id, line_id in pending_line_ids.items():
            line = Line.browse(line_id)
            if line.exists() and line.state == "Approved":
                self.browse(approval_id)._log_approval_on_origin()
        return result

    def get_next_move(self):
        if not self.type_id.model_id or not self.type_id.next_move_ids:
            return None
        types = self.env["multi.approval.type"]._get_types(self.type_id.model_id)
        if not types:
            return None
        types = types & self.type_id.next_move_ids
        approval_type = self.env["multi.approval.type"].filter_type(
            types, self.type_id.model_id, self.origin_ref.id
        )
        return approval_type

    def set_approved(self, send_mail=True):
        # customized code
        # 1. Write a log on the source document
        # 2. Call the callback action when approved
        # Note: always update the x_has_approved first !
        if not self.origin_ref:
            return super().set_approved(send_mail)
        next_move = self.get_next_move()
        if next_move and next_move.line_ids and self.type_id.next_move_policy:
            send_mail = False
            if self.type_id.next_move_policy == "auto":
                new_approval = self.sudo().copy({"type_id": next_move.id})
                new_approval.action_submit()
            elif self.type_id.next_move_policy == "manu":
                # update x_has_request_approval
                self.env["multi.approval.type"].update_x_field(
                    self.origin_ref, "x_has_request_approval", False
                )
                # update x_potential_type_id
                self.env["multi.approval.type"].update_x_field(
                    self.origin_ref,
                    "x_potential_type_id",
                    next_move.id,
                    raise_if_not_exist=False,
                )
        else:
            self.finalize_related_document()
        super().set_approved(send_mail)
        res = self.type_id.run(self, self.origin_ref)
        if res:
            return res

    def set_refused(self, reason="", send_mail=True):
        super().set_refused(reason, send_mail)

        # customized code
        # 1. Write a log on the source document
        # 2. Call the callback action when refused
        # Note: always update the x_has_approved first !
        if not self.origin_ref:
            return False
        log_msg = self.env._(
            "%(name)s has refused this document due to this reason: %(reason)s",
            name=self.env.user.name,
            reason=reason,
        )
        self.update_source_obj(self.origin_ref, "refused", log_msg)
        res = self.type_id.run(self, self.origin_ref, "refuse")
        if res:
            return res

    @api.model
    def open_request(self):
        ctx = self._context
        model_name = ctx.get("active_model")
        res_id = ctx.get("active_id")
        origin_ref = f"{model_name},{res_id}"
        return {
            "name": "My Requests",
            "type": "ir.actions.act_window",
            "res_model": "multi.approval",
            "view_mode": "list,form",
            "target": "current",
            "domain": [("origin_ref", "=", origin_ref)],
        }

    def _add_followers(self, record):
        self.ensure_one()
        partner_ids = []
        approval_type = self.type_id
        if approval_type.auto_request_partner_ids:
            partner_ids += approval_type.auto_request_partner_ids.ids
        if approval_type.auto_request_follower_python_code:
            eval_context = approval_type._get_eval_context(self, record)
            res = approval_type.exec_func(
                approval_type.auto_request_follower_python_code,
                eval_context,
                return_val=True,
            )
            if isinstance(res, models.BaseModel) and res._name == "res.partner":
                partner_ids += res.ids
            elif isinstance(res, int):
                partner_ids.append(res)
        if partner_ids:
            partner_ids = list(set(partner_ids))
        self.message_subscribe(partner_ids)

    def get_origin_email_context(self):
        self.ensure_one()
        origin = self.origin_ref
        if not origin:
            return super().get_origin_email_context()
        if hasattr(origin, "_notify_get_action_link"):
            origin_url = origin._notify_get_action_link("view")
        else:
            base_url = (
                self.env["ir.config_parameter"].sudo().get_param("web.base.url") or ""
            ).rstrip("/")
            origin_url = (
                f"{base_url}/web#id={origin.id}&model={origin._name}&view_type=form"
            )
        return {
            "origin_name": origin.display_name,
            "origin_url": origin_url,
        }
