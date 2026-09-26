##############################################################################
#
#    Copyright Domiup (<http://domiup.com>).
#
##############################################################################

import logging
import uuid
from datetime import timedelta

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command

_logger = logging.getLogger(__name__)

APPROVAL_MAIL_LAYOUT = "mail.mail_notification_layout_with_responsible_signature"


class MultiApproval(models.Model):
    _name = "multi.approval"
    _inherit = ["mail.thread.main.attachment", "mail.activity.mixin"]
    _description = "Approval"

    code = fields.Char(default="New")
    name = fields.Char(string="Title", required=True)
    user_id = fields.Many2one(
        string="Request by",
        comodel_name="res.users",
        required=True,
        default=lambda self: self.env.user,
    )
    priority = fields.Selection(
        [("0", "Normal"), ("1", "Medium"), ("2", "High"), ("3", "Very High")],
        default="0",
    )
    request_date = fields.Datetime(default=fields.Datetime.now, copy=False)
    complete_date = fields.Datetime(copy=False)
    type_id = fields.Many2one(
        string="Type", comodel_name="multi.approval.type", required=True
    )
    image = fields.Binary(related="type_id.image")
    description = fields.Html()
    state = fields.Selection(
        [
            ("Draft", "Draft"),
            ("Submitted", "Submitted"),
            ("Approved", "Approved"),
            ("Refused", "Refused"),
            ("Cancel", "Cancel"),
        ],
        default="Draft",
        tracking=True,
        copy=False,
    )

    document_opt = fields.Selection(
        string="Document opt", readonly=True, related="type_id.document_opt"
    )
    attachment_ids = fields.Many2many("ir.attachment", string="Documents")

    contact_opt = fields.Selection(
        string="Contact opt", readonly=True, related="type_id.contact_opt"
    )
    contact_id = fields.Many2one("res.partner", string="Contact")

    date_opt = fields.Selection(
        string="Date opt", readonly=True, related="type_id.date_opt"
    )
    date = fields.Date()

    period_opt = fields.Selection(
        string="Period opt", readonly=True, related="type_id.period_opt"
    )
    date_start = fields.Date("Start Date")
    date_end = fields.Date("End Date")

    item_opt = fields.Selection(string="Item opt", related="type_id.item_opt")
    item_id = fields.Many2one("product.product", string="Item")

    multi_items_opt = fields.Selection(
        string="Multi Items opt", readonly=True, related="type_id.multi_items_opt"
    )
    item_ids = fields.Many2many("product.product", string="Items")

    quantity_opt = fields.Selection(
        string="Quantity opt", readonly=True, related="type_id.quantity_opt"
    )
    quantity = fields.Float()

    amount_opt = fields.Selection(readonly=True, related="type_id.amount_opt")
    amount = fields.Float()

    payment_opt = fields.Selection(readonly=True, related="type_id.payment_opt")
    payment = fields.Float()

    reference_opt = fields.Selection(readonly=True, related="type_id.reference_opt")
    reference = fields.Char()

    location_opt = fields.Selection(readonly=True, related="type_id.location_opt")
    location = fields.Char()
    line_ids = fields.One2many("multi.approval.line", "approval_id", string="Lines")
    line_id = fields.Many2one("multi.approval.line", string="Line", copy=False)
    deadline = fields.Date(string="Deadline", related="line_id.deadline")
    pic_id = fields.Many2one("res.users", string="Approver", related="line_id.user_id")
    proxy_pic_ids = fields.Many2many(
        "res.users", string="Proxy Approvers", related="line_id.proxy_user_ids"
    )
    is_pic = fields.Boolean(compute="_compute_is_pic")
    follower = fields.Text("Following Users", default="[]", copy=False)
    refused_reason = fields.Text()
    public_uuid = fields.Char(
        string="Public UUID",
        copy=False,
        index=True,
        default=lambda self: str(uuid.uuid4()),
    )
    token_ids = fields.One2many(
        "multi.approval.token", "approval_id", string="Public Tokens"
    )

    # copy the idea of hr_expense
    attachment_number = fields.Integer(
        "Number of Attachments", compute="_compute_attachment_number"
    )

    _public_uuid_uniq = models.Constraint(
        "UNIQUE(public_uuid)",
        "The approval public UUID must be unique!",
    )

    def _auto_init(self):
        # Must run before UNIQUE(public_uuid) is created during schema update.
        self._deduplicate_public_uuids()
        return super()._auto_init()

    @api.model
    def _deduplicate_public_uuids(self):
        """Regenerate duplicate / empty public_uuid values (pre-unique-index)."""
        cr = self.env.cr
        cr.execute(
            """
            SELECT 1
              FROM information_schema.columns
             WHERE table_name = 'multi_approval'
               AND column_name = 'public_uuid'
            """
        )
        if not cr.fetchone():
            return

        cr.execute(
            """
            SELECT id
              FROM multi_approval
             WHERE public_uuid IS NULL OR btrim(public_uuid) = ''
            """
        )
        for (rec_id,) in cr.fetchall():
            cr.execute(
                "UPDATE multi_approval SET public_uuid = %s WHERE id = %s",
                (str(uuid.uuid4()), rec_id),
            )

        cr.execute(
            """
            SELECT id
              FROM (
                    SELECT id,
                           ROW_NUMBER() OVER (
                               PARTITION BY public_uuid ORDER BY id
                           ) AS rn
                      FROM multi_approval
                     WHERE public_uuid IS NOT NULL
                       AND btrim(public_uuid) <> ''
                   ) t
             WHERE rn > 1
            """
        )
        dup_ids = cr.fetchall()
        for (rec_id,) in dup_ids:
            cr.execute(
                "UPDATE multi_approval SET public_uuid = %s WHERE id = %s",
                (str(uuid.uuid4()), rec_id),
            )
        if dup_ids:
            _logger.info(
                "Regenerated public_uuid on %s duplicate multi.approval row(s)",
                len(dup_ids),
            )

    @api.depends("pic_id")
    @api.depends_context("uid")
    def _compute_is_pic(self):
        for r in self:
            r.is_pic = (
                r.pic_id.id == self.env.uid
                or self.env.uid in r.proxy_pic_ids.ids
            )

    def _compute_attachment_number(self):
        attachment_data = self.env["ir.attachment"]._read_group(
            [("res_model", "=", "multi.approval"), ("res_id", "in", self.ids)],
            ["res_id"],
            ["__count"],
        )
        attachment = dict(attachment_data)
        for r in self:
            r.attachment_number = attachment.get(r.id, 0)

    def action_cancel(self):
        recs = self.filtered(lambda x: x.state == "Draft")
        recs._revoke_tokens()
        recs.write({"state": "Cancel"})

    def action_draft(self):
        self.write({"state": "Draft"})

    def action_submit(self):
        recs = self.filtered(lambda x: x.state == "Draft")
        for r in recs:
            # Check if document is required
            if r.document_opt == "Required" and r.attachment_number < 1:
                raise UserError(self.env._("Document is required !"))
            if not r.type_id.line_ids:
                raise UserError(
                    self.env._("There is no approver of the type %s!", r.type_id.name)
                )
            r.state = "Submitted"
        recs._create_approval_lines()
        recs._ensure_tokens_for_current_line()
        recs.send_request_mail()
        recs.send_activity_notification()

    @api.model
    def get_follow_key(self, user_id=None):
        if not user_id:
            user_id = self.env.uid
        k = f"[res.users:{user_id}]"
        return k

    def update_follower(self, user_id):
        self.ensure_one()
        k = self.get_follow_key(user_id)
        follower = self.follower
        if k not in follower:
            self.follower = follower + k

    def _get_current_line_approver_users(self):
        self.ensure_one()
        line = self.line_id
        if not line:
            return self.env["res.users"]
        return line.user_id | line.proxy_user_ids

    def _revoke_tokens(self, lines=None):
        """Revoke active tokens. If lines is set, only those lines."""
        Token = self.env["multi.approval.token"].sudo()
        for rec in self:
            domain = [
                ("approval_id", "=", rec.id),
                ("state", "=", "active"),
            ]
            if lines is not None:
                domain.append(("line_id", "in", lines.ids))
            Token.search(domain).mark_revoked()

    def _ensure_tokens_for_current_line(self):
        """Create active tokens for PIC + proxies on the waiting line."""
        Token = self.env["multi.approval.token"].sudo()
        for rec in self:
            if not rec.public_uuid:
                rec.public_uuid = str(uuid.uuid4())
            line = rec.line_id
            if not line or line.state != "Waiting for Approval":
                continue
            users = rec._get_current_line_approver_users()
            for user in users:
                existing = Token.search(
                    [
                        ("approval_id", "=", rec.id),
                        ("line_id", "=", line.id),
                        ("user_id", "=", user.id),
                        ("state", "=", "active"),
                    ],
                    limit=1,
                )
                if existing:
                    continue
                Token.create(
                    {
                        "approval_id": rec.id,
                        "line_id": line.id,
                        "user_id": user.id,
                    }
                )

    def _rotate_tokens_after_line_decision(self, previous_line):
        """Revoke previous line tokens; create for next waiting line if any."""
        self.ensure_one()
        if previous_line:
            self._revoke_tokens(lines=previous_line)
        if self.state == "Submitted" and self.line_id:
            self._ensure_tokens_for_current_line()
        else:
            self._revoke_tokens()

    def get_origin_email_context(self):
        """Return origin document label/url when configuration is installed."""
        self.ensure_one()
        return {
            "origin_name": False,
            "origin_url": False,
        }

    def _notify_get_action_link(self, link_type, **kwargs):
        """Point the layout View button at the origin document when present."""
        if link_type == "view" and len(self) == 1:
            origin_url = self.get_origin_email_context().get("origin_url")
            if origin_url:
                return origin_url
        return super()._notify_get_action_link(link_type, **kwargs)

    def _notify_get_recipients_groups(self, message, model_description, msg_vals=False):
        groups = super()._notify_get_recipients_groups(
            message, model_description, msg_vals=msg_vals
        )
        if not self:
            return groups
        origin_ctx = self[:1].get_origin_email_context()
        if not origin_ctx.get("origin_url"):
            return groups
        button_access = {
            "url": origin_ctx["origin_url"],
            "title": self.env._(
                "View %s",
                origin_ctx.get("origin_name")
                or model_description
                or self.env._("Document"),
            ),
        }
        for _group_name, _group_func, group_data in groups:
            group_data["has_button_access"] = True
            group_data["button_access"] = button_access
        return groups

    def _get_approval_mail_layout(self, template=None):
        return (template and template.email_layout_xmlid) or APPROVAL_MAIL_LAYOUT

    def _get_approval_mail_notify_kwargs(self, template=None):
        """Extra notification values so the email uses the standard layout."""
        self.ensure_one()
        origin_ctx = self.get_origin_email_context()
        notify_kwargs = {
            "email_layout_xmlid": self._get_approval_mail_layout(template),
            "mail_auto_delete": True,
        }
        if origin_ctx.get("origin_name"):
            notify_kwargs["force_record_name"] = origin_ctx["origin_name"]
            notify_kwargs["subtitles"] = [origin_ctx["origin_name"]]
            notify_kwargs["model_description"] = origin_ctx["origin_name"]
        return notify_kwargs

    def _notify_with_layout(
        self,
        *,
        body,
        subject,
        partner_ids,
        template=None,
        attachment_ids=None,
        email_from=False,
        author_id=False,
    ):
        """Send email and post it on the approval chatter (Odoo 19).

        Uses ``message_post`` so the mail is visible on the document.
        ``message_notify`` would create ``user_notification`` messages that
        chatter filters out. Notify kwargs (layout, force_record_name, …)
        remain valid per ``_get_notify_valid_parameters``.
        """
        self.ensure_one()
        partner_ids = [pid for pid in (partner_ids or []) if pid]
        if not partner_ids:
            return self.env["mail.message"]
        if not isinstance(body, Markup):
            body = Markup(body or "")
        return self.message_post(
            body=body,
            subject=subject,
            partner_ids=partner_ids,
            email_from=email_from or self.user_id.email_formatted,
            author_id=author_id or self.user_id.partner_id.id,
            message_type="notification",
            subtype_xmlid="mail.mt_note",
            attachment_ids=list(attachment_ids or []),
            **self._get_approval_mail_notify_kwargs(template),
        )

    def _send_template_notification(self, template):
        """Render a mail.template and send it through the notification layout."""
        self.ensure_one()
        if not template:
            return self.env["mail.message"]
        values = template._generate_template(
            [self.id],
            render_fields=("body_html", "subject", "partner_to"),
        )[self.id]
        partner_ids = values.get("partner_ids") or self.user_id.partner_id.ids
        return self._notify_with_layout(
            body=values.get("body_html") or "",
            subject=values.get("subject") or self.display_name,
            partner_ids=partner_ids,
            template=template,
        )

    # 13.0.1.1
    def set_approved(self, send_mail=True):
        self.ensure_one()
        self.state = "Approved"
        self.complete_date = fields.Datetime.now()
        self._revoke_tokens()
        if send_mail:
            self.send_approved_mail()

    def set_refused(self, reason="", send_mail=True):
        self.ensure_one()
        self.state = "Refused"
        self.refused_reason = reason
        self.complete_date = fields.Datetime.now()
        self._revoke_tokens()
        if send_mail:
            self.send_refused_mail()

    def action_approve(self):
        ret_act = None
        recs = self.filtered(lambda x: x.state == "Submitted")
        for rec in recs:
            if not rec.is_pic:
                msg = self.env._(
                    "%s do not have the authority to approve this request !",
                    rec.env.user.name,
                )
                rec.sudo().message_post(body=msg)
                return False
            line = rec.line_id
            if not line or line.state != "Waiting for Approval":
                # Something goes wrong!
                rec.message_post(body=self.env._("Something goes wrong!"))
                return False

            # Update follower
            rec.update_follower(self.env.uid)

            # check if this line is required
            other_lines = rec.line_ids.filtered(
                lambda x, _l=line: x.sequence >= _l.sequence and x.state == "Draft"
            )
            line.set_approved()
            if not other_lines:
                ret_act = rec.set_approved()
                rec._revoke_tokens(lines=line)
            else:
                next_line = other_lines.sorted("sequence")[0]
                next_line.write(
                    {
                        "state": "Waiting for Approval",
                    }
                )
                rec.line_id = next_line
                rec._rotate_tokens_after_line_decision(line)
                rec.send_request_mail()
                recs.send_activity_notification()
            msg = self.env._("I approved")
            rec.finalize_activity_or_message("approved", msg)
        if ret_act:
            return ret_act
        return True

    def action_refuse(self, reason=""):
        ret_act = None
        recs = self.filtered(lambda x: x.state == "Submitted")
        for rec in recs:
            if not rec.is_pic:
                msg = self.env._(
                    "%s do not have the authority to approve this request !",
                    rec.env.user.name,
                )
                self.sudo().message_post(body=msg)
                return False
            line = rec.line_id
            if not line or line.state != "Waiting for Approval":
                # Something goes wrong!
                self.message_post(body=self.env._("Something goes wrong!"))
                return False

            # Update follower
            rec.update_follower(self.env.uid)

            # check if this line is required
            if line.require_opt == "Required":
                line.set_refused(reason)
                ret_act = rec.set_refused(reason)
                draft_lines = rec.line_ids.filtered(lambda x: x.state == "Draft")
                if draft_lines:
                    draft_lines.state = "Cancel"
            else:  # optional
                other_lines = rec.line_ids.filtered(
                    lambda x, _l=line: x.sequence >= _l.sequence and x.state == "Draft"
                )
                line.set_refused(reason)
                if not other_lines:
                    ret_act = rec.set_refused(reason)
                else:
                    next_line = other_lines.sorted("sequence")[0]
                    next_line.state = "Waiting for Approval"
                    rec.line_id = next_line
                    rec._rotate_tokens_after_line_decision(line)
                    rec.send_request_mail()
                    rec.send_activity_notification()
            msg = self.env._("I refused due to this reason: %s", reason)
            rec.finalize_activity_or_message("refused", msg)
        if ret_act:
            return ret_act

    def finalize_activity_or_message(self, action, msg):
        requests = self.filtered(lambda r: r.type_id.activity_notification)
        notify_type = self.env.ref("mail.mail_activity_data_todo", False)
        if requests and notify_type:
            activities = requests.mapped("activity_ids").filtered(
                lambda a: a.activity_type_id == notify_type
                and a.user_id == self.env.user
            )
            activities._action_done(msg)

        requests2 = self - requests
        if requests2:
            requests2.message_post(body=msg)

    def _create_approval_lines(self):
        ApprovalLine = self.env["multi.approval.line"]
        for r in self:
            lines = r.type_id.line_ids.sorted("sequence")
            last_seq = 0
            for _l in lines:
                proxy_lines = _l.get_proxy_lines()
                line_seq = _l.sequence
                if not line_seq or line_seq <= last_seq:
                    line_seq = last_seq + 1
                last_seq = line_seq
                vals = {
                    "name": _l.name,
                    "user_id": _l.get_user(),
                    "proxy_user_ids": [Command.set(proxy_lines.get_proxy_users())],
                    "sequence": line_seq,
                    "require_opt": _l.require_opt,
                    "approval_id": r.id,
                }
                if _l == lines[0]:
                    vals.update({"state": "Waiting for Approval"})
                approval = ApprovalLine.create(vals)
                if _l == lines[0]:
                    r.line_id = approval

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            seq_date = vals.get("request_date", fields.Datetime.now())
            vals["code"] = self.env["ir.sequence"].next_by_code(
                "multi.approval", sequence_date=seq_date
            ) or self.env._("New")
            if not vals.get("public_uuid"):
                vals["public_uuid"] = str(uuid.uuid4())
        result = super().create(vals_list)
        return result

    def _get_request_mail_template(self):
        self.ensure_one()
        if self.type_id.mail_template_id:
            return self.type_id.mail_template_id
        return self.env.ref(
            "multi_level_approval.email_template_request_approval",
            raise_if_not_found=False,
        )

    def _get_reminder_mail_template(self):
        self.ensure_one()
        if self.type_id.reminder_mail_template_id:
            return self.type_id.reminder_mail_template_id
        return self.env.ref(
            "multi_level_approval.email_template_reminder_approval",
            raise_if_not_found=False,
        )

    def _send_approver_mails(self, template, default_subject):
        """Email current-line approvers (PIC + proxies) using the given template."""
        self.ensure_one()
        self._ensure_tokens_for_current_line()
        tokens = self.token_ids.filtered(
            lambda t: t.state == "active" and t.line_id == self.line_id
        )
        attachment_ids = self._get_request_mail_attachments().ids
        for token in tokens:
            partner = token.user_id.partner_id
            if not partner:
                continue
            body_html = self._build_request_mail_body(token, template=template)
            subject = default_subject
            if template:
                subject = template._render_field(
                    "subject",
                    [self.id],
                    compute_lang=True,
                )[self.id]
            self._notify_with_layout(
                body=body_html,
                subject=subject,
                partner_ids=partner.ids,
                template=template,
                attachment_ids=attachment_ids,
                email_from=self.user_id.email_formatted,
                author_id=self.user_id.partner_id.id,
            )

    def _build_request_mail_body(self, token, template=None):
        """Build HTML body for one approver, injecting approve/reject URLs."""
        self.ensure_one()
        origin_ctx = self.get_origin_email_context()
        approve_url = token.approve_url or ""
        reject_url = token.reject_url or ""
        company = self.env.company
        btn_bg = company.email_secondary_color or "#875A7B"
        btn_fg = company.email_primary_color or "#FFFFFF"
        buttons_html = Markup(f"""
<table cellspacing="0" cellpadding="0" border="0" style="margin: 16px 0;">
  <tr>
    <td style="padding-right: 10px;">
      <a href="{approve_url}"
         style="display:inline-block;padding:10px 18px;background-color:{btn_bg};
                color:{btn_fg};text-decoration:none;border-radius:3px;font-weight:bold;">
        Approve
      </a>
    </td>
    <td>
      <a href="{reject_url}"
         style="display:inline-block;padding:10px 18px;background-color:#dc3545;
                color:#ffffff;text-decoration:none;border-radius:3px;font-weight:bold;">
        Reject
      </a>
    </td>
  </tr>
</table>
""")
        render_ctx = {
            "approve_url": approve_url,
            "reject_url": reject_url,
            "token_user": token.user_id,
            "origin_name": origin_ctx.get("origin_name") or False,
            "origin_url": origin_ctx.get("origin_url") or False,
        }
        if template:
            try:
                body = template._render_field(
                    "body_html",
                    [self.id],
                    compute_lang=True,
                    add_context=render_ctx,
                )[self.id]
            except Exception:
                _logger.exception(
                    "Failed to render approval mail template %s", template.id
                )
                body = False
            if body:
                if approve_url and "Approve" not in body:
                    body = body + buttons_html
                return body

        origin_block = ""
        if origin_ctx.get("origin_name"):
            origin_link = origin_ctx.get("origin_url") or "#"
            origin_block = (
                f'<p><strong>Document:</strong> '
                f'<a href="{origin_link}">{origin_ctx["origin_name"]}</a></p>'
            )
        description = self.description or ""
        return Markup(f"""
<div style="margin:0;padding:0;font-size:13px;">
  <p>Dear {token.user_id.name or "Approver"},</p>
  <p>Please review the following approval request:</p>
  <ul>
    <li><strong>Request:</strong> {self.display_name}</li>
    <li><strong>Code:</strong> {self.code or ""}</li>
    <li><strong>Requested by:</strong> {self.user_id.name or ""}</li>
    <li><strong>Date:</strong> {self.request_date or ""}</li>
  </ul>
  {origin_block}
  <div>{description}</div>
  {buttons_html}
  <p>Regards,</p>
</div>
""")

    def _get_request_mail_attachments(self):
        """Return ir.attachment records to include on the request email.

        Override in extra modules to attach documents based on the approval
        type configuration. Attachments are collected once per request and
        reused for every approver token.
        """
        self.ensure_one()
        return self.env["ir.attachment"]

    # 12.0.1.3
    def send_request_mail(self):
        requests = self.filtered(
            lambda r: r.type_id.mail_notification
            and r.pic_id
            and r.state == "Submitted"
        )
        for req in requests:
            req._send_approver_mails(
                req._get_request_mail_template(),
                self.env._(
                    "Request the approval for: %(request_name)s",
                    request_name=req.display_name,
                ),
            )

    def send_reminder_mail(self):
        requests = self.filtered(
            lambda r: r.type_id.reminder_notification
            and r.pic_id
            and r.state == "Submitted"
        )
        for req in requests:
            req._send_approver_mails(
                req._get_reminder_mail_template(),
                self.env._(
                    "Reminder: approval still pending for %(request_name)s",
                    request_name=req.display_name,
                ),
            )

    def _is_pending_reminder_due(self, now=None):
        self.ensure_one()
        now = now or fields.Datetime.now()
        line = self.line_id
        if (
            self.state != "Submitted"
            or not self.type_id.reminder_notification
            or not line
            or line.state != "Waiting for Approval"
        ):
            return False
        delay_minutes = self.type_id._get_reminder_delay_minutes()
        if delay_minutes <= 0:
            return False
        started_on = line.last_reminder_date or line.request_date or self.request_date
        if not started_on:
            return False
        return now >= started_on + timedelta(minutes=delay_minutes)

    def _send_pending_reminder_if_due(self, now=None):
        self.ensure_one()
        now = now or fields.Datetime.now()
        if not self._is_pending_reminder_due(now=now):
            return False
        self.send_reminder_mail()
        if self.line_id:
            self.line_id.last_reminder_date = now
        return True

    @api.model
    def _cron_send_pending_reminders(self):
        """Scheduled action: remind pending approvers after the configured delay.

        Cron/server actions set mail_notify_force_send=False (see mail.ir.actions.server),
        which would leave reminder emails as Outgoing until the hourly Mail Queue Manager.
        Force immediate send so reminders behave like submit/approve/refuse notifications.
        """
        requests = self.search(
            [
                ("state", "=", "Submitted"),
                ("type_id.reminder_notification", "=", True),
                ("type_id.reminder_delay", ">", 0),
                ("line_id.state", "=", "Waiting for Approval"),
            ]
        )
        for req in requests:
            try:
                req.with_context(mail_notify_force_send=True)._send_pending_reminder_if_due()
            except Exception:
                _logger.exception(
                    "Failed to send pending approval reminder for %s", req.id
                )

    def send_approved_mail(self):
        requests = self.filtered(
            lambda r: r.type_id.approve_mail_template_id and r.state == "Approved"
        )
        for req in requests:
            req._send_template_notification(req.type_id.approve_mail_template_id)

    def send_refused_mail(self):
        requests = self.filtered(
            lambda r: r.type_id.refuse_mail_template_id and r.state == "Refused"
        )
        for req in requests:
            req._send_template_notification(req.type_id.refuse_mail_template_id)

    def send_activity_notification(self):
        requests = self.filtered(
            lambda r: r.type_id.activity_notification
            and r.pic_id
            and r.state == "Submitted"
        )
        for req in requests:
            summary = self.env._(
                "The request %(code)s need to be reviewed", code=req.code
            )
            req.activity_schedule(
                "mail.mail_activity_data_todo",
                summary=summary,
                user_id=req.pic_id.id,
            )
