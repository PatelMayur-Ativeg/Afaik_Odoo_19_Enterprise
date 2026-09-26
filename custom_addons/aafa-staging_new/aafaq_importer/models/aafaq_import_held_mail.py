# -*- coding: utf-8 -*-

import logging

from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from .aafaq_import_constants import RECORD_TYPE_SELECTION

_logger = logging.getLogger(__name__)


class AafaqImportHeldMail(models.Model):
    _name = "aafaq.import.held.mail"
    _description = "Aafaq Held Import Email"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"
    _rec_name = "name"

    name = fields.Char(required=True, default=lambda self: _("Held Import Email"))
    alias_config_id = fields.Many2one(
        "aafaq.import.alias",
        string="Email Alias",
        required=True,
        index=True,
        ondelete="restrict",
    )
    record_type = fields.Selection(
        RECORD_TYPE_SELECTION,
        related="alias_config_id.record_type",
        store=True,
        index=True,
    )
    company_id = fields.Many2one("res.company", required=True, index=True)
    journal_id = fields.Many2one("account.journal", string="Journal")
    user_id = fields.Many2one("res.users", string="Salesperson")
    email_from = fields.Char(string="Email From", copy=False)
    subject = fields.Char(copy=False)
    mail_message_id = fields.Many2one(
        "mail.message",
        string="Incoming Message",
        copy=False,
        index=True,
        ondelete="set null",
    )
    date = fields.Datetime(default=fields.Datetime.now, index=True)
    filename = fields.Char()
    file = fields.Binary("File", attachment=True)
    queue_id = fields.Many2one(
        "aafaq.import.queue",
        string="Import Queue",
        copy=False,
        index=True,
        ondelete="set null",
    )
    state = fields.Selection(
        [
            ("onhold", "On Hold"),
            ("done", "Done"),
        ],
        default="onhold",
        required=True,
        index=True,
        tracking=True,
        copy=False,
    )

    @api.model
    def _mail_get_primary_email_field(self):
        return "email_from"

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        custom_values = dict(custom_values or {})
        custom_values.pop("import_source", None)
        record_type = custom_values.pop("record_type", None)

        if msg_dict.get("email_from") and not custom_values.get("email_from"):
            custom_values["email_from"] = msg_dict["email_from"]
        subject = msg_dict.get("subject") or _("Held Import Email")
        custom_values.setdefault("subject", subject)
        custom_values.setdefault("name", subject)
        if msg_dict.get("date") and not custom_values.get("date"):
            custom_values["date"] = msg_dict["date"]
        if not custom_values.get("company_id"):
            custom_values["company_id"] = self.env.company.id
        if record_type and not custom_values.get("journal_id"):
            fill_vals = dict(custom_values, record_type=record_type)
            self.env["aafaq.import.queue"]._fill_journal_from_record_type(fill_vals)
            if fill_vals.get("journal_id"):
                custom_values["journal_id"] = fill_vals["journal_id"]

        files = self.env["aafaq.import.queue"]._extract_import_attachments(
            msg_dict.get("attachments")
        )
        # No spreadsheet: still hold the email so the missing file is visible.
        if not files:
            files = [(False, False)]

        custom_values.setdefault("state", "onhold")
        base_name = custom_values.get("name") or subject
        first = self.env["aafaq.import.held.mail"]
        for index, (filename, file_b64) in enumerate(files):
            vals = dict(custom_values)
            if filename:
                vals["filename"] = filename
                vals["file"] = file_b64
                if len(files) > 1:
                    vals["name"] = "%s - %s" % (base_name, filename)
            if index == 0:
                record = super().message_new(msg_dict, custom_values=vals)
                first = record
            else:
                record = self.create(vals)
            record._log_held_email()
        return first

    def _log_held_email(self):
        self.ensure_one()
        message = self.message_ids.filtered(lambda m: m.message_type == "email")[:1]
        if message and not self.mail_message_id:
            self.mail_message_id = message.id
        alias_email = (
            self.alias_config_id.alias_email
            or self.alias_config_id.alias_name
            or _("n/a")
        )
        self._message_log(body=Markup("<p>%s</p>") % _(
            "Email to %(alias)s held until end-of-day processing (from %(email_from)s).",
            alias=alias_email,
            email_from=self.email_from or _("unknown sender"),
        ))

    def action_process_held_mails(self):
        """Create import queues from onhold emails and process them."""
        to_process = self.filtered(lambda rec: rec.state == "onhold")
        if not self:
            to_process = self.search([("state", "=", "onhold")])
        processed = self.env["aafaq.import.held.mail"]
        for mail in to_process:
            try:
                with self.env.cr.savepoint():
                    mail._release_to_queue()
                processed |= mail
            except Exception as exc:
                _logger.exception("Failed to process held import mail %s", mail.id)
                mail._message_log(body=Markup("<p>%s</p>") % _(
                    "Could not process held email: %s",
                    str(exc),
                ))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Held Emails"),
                "message": _(
                    "Processed %(done)s of %(total)s held email(s).",
                    done=len(processed),
                    total=len(to_process),
                ),
                "type": "success" if processed else "warning",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    @api.model
    def cron_process_held_mails(self):
        self.search([("state", "=", "onhold")]).action_process_held_mails()

    def _release_to_queue(self):
        self.ensure_one()
        if self.state != "onhold":
            return self.queue_id

        Queue = self.env["aafaq.import.queue"]
        vals = {
            "name": Queue._next_queue_name(self.record_type),
            "record_type": self.record_type,
            "company_id": self.company_id.id,
            "journal_id": self.journal_id.id if self.journal_id else False,
            "user_id": self.user_id.id if self.user_id else False,
            "import_source": "email",
            "alias_config_id": self.alias_config_id.id,
            "email_from": self.email_from,
            "filename": self.filename,
            "file": self.file,
        }
        Queue._fill_journal_from_record_type(vals)
        queue = Queue.create(vals)
        self.write({
            "queue_id": queue.id,
            "state": "done",
        })
        try:
            if not queue.file:
                raise ValidationError(_(
                    "No Excel or CSV attachment found. Attach a .xlsx, .xls or .csv file."
                ))
            queue.action_process_queue()
        except Exception as exc:
            queue._log_email_failure(str(exc), exception=exc)
        return queue
