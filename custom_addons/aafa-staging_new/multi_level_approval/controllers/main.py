##############################################################################
#
#    Copyright Domiup (<http://domiup.com>).
#
##############################################################################

from odoo import http
from odoo.http import request
from odoo.tools.translate import _


class MultiApprovalPublicController(http.Controller):

    def _find_token(self, approval_uuid, approver_uuid):
        return (
            request.env["multi.approval.token"]
            .sudo()
            .search(
                [
                    ("token", "=", approver_uuid),
                    ("approval_id.public_uuid", "=", approval_uuid),
                ],
                limit=1,
            )
        )

    def _render_page(self, template, values=None):
        values = values or {}
        return request.render(template, values)

    def _error_page(self):
        return self._render_page(
            "multi_level_approval.public_approval_error",
            {
                "title": _("Action not available"),
                "message": _(
                    "This approval link is invalid, expired, or has already been used."
                ),
            },
        )

    def _token_is_actionable(self, token):
        if not token or token.state != "active":
            return False
        approval = token.approval_id
        if approval.state != "Submitted":
            return False
        if approval.line_id != token.line_id:
            return False
        if token.line_id.state != "Waiting for Approval":
            return False
        return True

    def _approval_summary(self, approval, token):
        origin_ctx = approval.get_origin_email_context()
        return {
            "approval": approval,
            "token": token,
            "approver": token.user_id,
            "origin_name": origin_ctx.get("origin_name"),
            "origin_url": origin_ctx.get("origin_url"),
        }

    @http.route(
        "/multi_approval/<string:approval_uuid>/<string:approver_uuid>/approve",
        type="http",
        auth="public",
        methods=["GET", "POST"],
        csrf=True,
    )
    def public_approve(self, approval_uuid, approver_uuid, **post):
        token = self._find_token(approval_uuid, approver_uuid)
        if not self._token_is_actionable(token):
            return self._error_page()

        approval = token.approval_id
        if request.httprequest.method == "GET":
            return self._render_page(
                "multi_level_approval.public_approval_confirm_approve",
                {
                    **self._approval_summary(approval, token),
                    "csrf_token": request.csrf_token(),
                },
            )

        result = approval.with_user(token.user_id).sudo().action_approve()
        if result is False:
            return self._error_page()

        # Mark all tokens on that line as used (PIC + proxies)
        line_tokens = approval.token_ids.filtered(
            lambda t: t.line_id == token.line_id and t.state == "active"
        )
        # action_approve already rotates/revokes; mark any leftover as used
        if line_tokens:
            line_tokens.mark_used()

        return self._render_page(
            "multi_level_approval.public_approval_success",
            {
                "title": _("Approved"),
                "message": _(
                    "The approval request %(name)s has been approved successfully.",
                    name=approval.display_name,
                ),
            },
        )

    @http.route(
        "/multi_approval/<string:approval_uuid>/<string:approver_uuid>/reject",
        type="http",
        auth="public",
        methods=["GET", "POST"],
        csrf=True,
    )
    def public_reject(self, approval_uuid, approver_uuid, **post):
        token = self._find_token(approval_uuid, approver_uuid)
        if not self._token_is_actionable(token):
            return self._error_page()

        approval = token.approval_id
        if request.httprequest.method == "GET":
            return self._render_page(
                "multi_level_approval.public_approval_confirm_reject",
                {
                    **self._approval_summary(approval, token),
                    "error": False,
                    "csrf_token": request.csrf_token(),
                },
            )

        reason = (post.get("reason") or "").strip()
        if not reason:
            return self._render_page(
                "multi_level_approval.public_approval_confirm_reject",
                {
                    **self._approval_summary(approval, token),
                    "error": _("A refusal reason is required."),
                    "csrf_token": request.csrf_token(),
                },
            )

        result = (
            approval.with_user(token.user_id).sudo().action_refuse(reason=reason)
        )
        if result is False:
            return self._error_page()

        line_tokens = approval.token_ids.filtered(
            lambda t: t.line_id == token.line_id and t.state == "active"
        )
        if line_tokens:
            line_tokens.mark_used()

        return self._render_page(
            "multi_level_approval.public_approval_success",
            {
                "title": _("Refused"),
                "message": _(
                    "The approval request %(name)s has been refused.",
                    name=approval.display_name,
                ),
            },
        )
