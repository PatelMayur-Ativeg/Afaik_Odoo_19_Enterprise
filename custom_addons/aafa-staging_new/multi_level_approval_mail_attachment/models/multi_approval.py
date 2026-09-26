# -*- coding: utf-8 -*-

from odoo import models
from odoo.tools import format_datetime


class MultiApproval(models.Model):
    _inherit = "multi.approval"

    _APPROVAL_LINE_STATE_STYLES = {
        "Approved": ("#166534", "#dcfce7"),
        "Waiting for Approval": ("#9a3412", "#ffedd5"),
        "Refused": ("#991b1b", "#fee2e2"),
        "Cancel": ("#4b5563", "#f3f4f6"),
        "Draft": ("#4b5563", "#f3f4f6"),
    }

    def _get_approval_lines_email_rows(self):
        self.ensure_one()
        state_labels = dict(
            self.env["multi.approval.line"]._fields["state"]._description_selection(self.env)
        )
        rows = []
        for line in self.line_ids.sorted("sequence"):
            color, bg = self._APPROVAL_LINE_STATE_STYLES.get(
                line.state, ("#374151", "#f3f4f6")
            )
            rows.append(
                {
                    "user": line.user_id.display_name or "",
                    "approved_on": (
                        format_datetime(self.env, line.approved_date, dt_format="medium")
                        if line.approved_date
                        else "—"
                    ),
                    "state": state_labels.get(line.state, line.state or ""),
                    "state_style": (
                        "display:inline-block;padding:2px 8px;border-radius:10px;"
                        f"font-size:12px;font-weight:600;color:{color};background-color:{bg};"
                    ),
                }
            )
        return rows

    def _get_approval_lines_email_table(self):
        self.ensure_one()
        rows = self._get_approval_lines_email_rows()
        if not rows:
            return ""
        return self.env["ir.qweb"]._render(
            "multi_level_approval_mail_attachment.mail_approval_lines_table",
            {"lines": rows},
        )

    def _inject_approval_lines_table(self, body):
        table_html = self._get_approval_lines_email_table()
        if not table_html or not body:
            return body
        body = str(body)
        if "approval-lines-email-table" in body:
            return body
        markers = (
            '<table cellspacing="0" cellpadding="0" border="0" style="margin: 16px 0;">',
            '<table cellspacing="0" cellpadding="0" border="0" style="margin:16px 0;">',
        )
        for marker in markers:
            if marker in body:
                return body.replace(marker, f"{table_html}{marker}", 1)
        if "Regards," in body:
            return body.replace("Regards,", f"{table_html}Regards,", 1)
        return body + str(table_html)

    def _build_request_mail_body(self, token, template=None):
        body = super()._build_request_mail_body(token, template=template)
        return self._inject_approval_lines_table(body)

    def _get_request_mail_attachments(self):
        self.ensure_one()
        lines = self.type_id.mail_attachment_line_ids.filtered("active").sorted(
            "sequence"
        )
        if not lines:
            return super()._get_request_mail_attachments()
        attachments = self.env["ir.attachment"]
        seen = set()
        for line in lines.sudo():
            for att in line._collect_attachments(self):
                key = att.checksum or (att.name, att.file_size, att.id)
                if key in seen:
                    continue
                seen.add(key)
                attachments |= att
        return attachments
