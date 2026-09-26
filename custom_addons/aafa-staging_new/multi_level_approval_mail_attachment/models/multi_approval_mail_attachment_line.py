# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval, test_python_expr

_logger = logging.getLogger(__name__)


class MultiApprovalMailAttachmentLine(models.Model):
    _name = "multi.approval.mail.attachment.line"
    _description = "Approval Request Mail Attachment"
    _order = "sequence, id"

    type_id = fields.Many2one(
        "multi.approval.type",
        required=True,
        ondelete="cascade",
        index=True,
    )
    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    source = fields.Selection(
        selection="_selection_source",
        required=True,
        default="origin_report",
        string="Source",
    )
    report_id = fields.Many2one(
        "ir.actions.report",
        string="Report",
        domain="[('report_type', '=', 'qweb-pdf'), ('model', '=', type_id.model_id)]",
        help="PDF report used when the source generates a document. "
        "Only reports of the approval type model are shown.",
    )
    related_path = fields.Char(
        help="Dotted field path from the origin document, e.g. invoice_ids.",
    )
    related_domain = fields.Text(
        default="[]",
        help="Optional domain applied to the related records.",
    )
    python_code = fields.Text(
        help="Python code executed with env, request, origin, type, user. "
        "Set result to an ir.attachment recordset.",
    )

    @api.model
    def _selection_source(self):
        return [
            ("origin_report", "PDF report of origin document"),
            ("origin_chatter", "Chatter attachments of origin document"),
            ("origin_attachments", "Documents linked to origin"),
            ("related_report", "PDF report of related records"),
            ("related_chatter", "Chatter attachments of related records"),
            ("python", "Python code"),
        ]

    @api.constrains("python_code")
    def _check_python_code(self):
        for rec in self.filtered("python_code"):
            try:
                msg = test_python_expr(expr=rec.python_code.strip(), mode="exec")
            except Exception as exc:
                raise ValidationError(self.env._("Invalid python syntax")) from exc
            if msg:
                raise ValidationError(msg)

    @api.constrains(
        "source", "report_id", "related_path", "python_code"
    )
    def _check_source_options(self):
        for rec in self:
            if rec.source in ("origin_report", "related_report") and not rec.report_id:
                raise ValidationError(
                    self.env._(
                        "A report is required on attachment line '%s'."
                    )
                    % (rec.name or rec.source)
                )
            if rec.source in ("related_report", "related_chatter") and not rec.related_path:
                raise ValidationError(
                    self.env._(
                        "A related path is required on attachment line '%s'."
                    )
                    % (rec.name or rec.source)
                )
            if rec.source == "python" and not (rec.python_code or "").strip():
                raise ValidationError(
                    self.env._(
                        "Python code is required on attachment line '%s'."
                    )
                    % (rec.name or rec.source)
                )

    def _get_origin(self, request):
        origin = getattr(request, "origin_ref", False)
        return origin.sudo() if origin else origin

    def _copy_attachments_for_request(self, attachments, request, name_prefix=None):
        copies = self.env["ir.attachment"]
        for att in attachments.sudo():
            if att.type != "url" and not att.checksum and not att.file_size:
                continue
            name = att.name or "attachment"
            if name_prefix:
                name = f"{name_prefix} - {name}"
            copies |= att.copy(
                {
                    "name": name,
                    "res_model": request._name,
                    "res_id": request.id,
                }
            )
        return copies

    def _get_record_direct_attachments(self, records):
        if not records:
            return self.env["ir.attachment"]
        return (
            self.env["ir.attachment"]
            .sudo()
            .search(
                [
                    ("res_model", "=", records._name),
                    ("res_id", "in", records.ids),
                ]
            )
        )

    def _get_record_chatter_attachments(self, records):
        if not records:
            return self.env["ir.attachment"]
        messages = (
            self.env["mail.message"]
            .sudo()
            .search(
                [
                    ("model", "=", records._name),
                    ("res_id", "in", records.ids),
                ]
            )
        )
        return messages.mapped("attachment_ids")

    def _get_record_all_attachments(self, records):
        return self._get_record_direct_attachments(
            records
        ) | self._get_record_chatter_attachments(records)

    def _render_report_attachments(self, records, request, report=None):
        self.ensure_one()
        report = report or self.report_id
        if not records or not report:
            return self.env["ir.attachment"]
        attachments = self.env["ir.attachment"]
        report_sudo = report.sudo()
        for record in records:
            try:
                pdf_content, _unused = (
                    self.env["ir.actions.report"]
                    .sudo()
                    ._render_qweb_pdf(report_sudo, res_ids=[record.id])
                )
            except Exception:
                _logger.exception(
                    "Failed to render report %s on %s,%s for approval %s",
                    report.display_name,
                    record._name,
                    record.id,
                    request.display_name,
                )
                continue
            if not pdf_content:
                continue
            filename = f"{record.display_name} - {report.name}.pdf".replace("/", "_")
            attachments |= (
                self.env["ir.attachment"]
                .sudo()
                .create(
                    {
                        "name": filename,
                        "type": "binary",
                        "raw": pdf_content,
                        "res_model": request._name,
                        "res_id": request.id,
                        "mimetype": "application/pdf",
                    }
                )
            )
        return attachments

    def _get_related_records(self, origin):
        self.ensure_one()
        if not origin or not self.related_path:
            return origin.browse() if origin else self.env["multi.approval"]
        try:
            records = origin.mapped(self.related_path)
        except Exception:
            _logger.exception(
                "Invalid related path '%s' on attachment line %s",
                self.related_path,
                self.display_name,
            )
            return origin.browse()
        domain_expr = (self.related_domain or "").strip()
        if domain_expr and domain_expr != "[]":
            try:
                domain = safe_eval(domain_expr)
                records = records.filtered_domain(domain)
            except Exception:
                _logger.exception(
                    "Invalid related domain '%s' on attachment line %s",
                    self.related_domain,
                    self.display_name,
                )
        return records

    def _collect_attachments(self, request):
        self.ensure_one()
        method = getattr(self, f"_collect_{self.source}", None)
        if not method:
            _logger.warning("Unknown approval mail attachment source %s", self.source)
            return self.env["ir.attachment"]
        try:
            return method(request) or self.env["ir.attachment"]
        except Exception:
            _logger.exception(
                "Failed to collect attachments for line '%s' on request %s",
                self.name,
                request.display_name,
            )
            return self.env["ir.attachment"]

    def _collect_origin_report(self, request):
        origin = self._get_origin(request)
        if not origin:
            return self.env["ir.attachment"]
        return self._render_report_attachments(origin, request)

    def _collect_origin_chatter(self, request):
        origin = self._get_origin(request)
        if not origin:
            return self.env["ir.attachment"]
        return self._copy_attachments_for_request(
            self._get_record_chatter_attachments(origin),
            request,
            name_prefix=origin.display_name,
        )

    def _collect_origin_attachments(self, request):
        origin = self._get_origin(request)
        if not origin:
            return self.env["ir.attachment"]
        return self._copy_attachments_for_request(
            self._get_record_direct_attachments(origin),
            request,
            name_prefix=origin.display_name,
        )

    def _collect_related_report(self, request):
        origin = self._get_origin(request)
        records = self._get_related_records(origin)
        return self._render_report_attachments(records, request)

    def _collect_related_chatter(self, request):
        origin = self._get_origin(request)
        records = self._get_related_records(origin)
        attachments = self.env["ir.attachment"]
        for record in records:
            attachments |= self._copy_attachments_for_request(
                self._get_record_chatter_attachments(record),
                request,
                name_prefix=record.display_name,
            )
        return attachments

    def _collect_python(self, request):
        if not (self.python_code or "").strip():
            return self.env["ir.attachment"]
        origin = self._get_origin(request)
        eval_context = {
            "uid": self.env.uid,
            "user": self.env.user,
            "env": self.env,
            "request": request,
            "origin": origin,
            "type": request.type_id,
            "result": self.env["ir.attachment"],
        }
        safe_eval(
            self.python_code.strip(),
            eval_context,
            mode="exec",
            filename="multi.approval.mail.attachment",
        )
        result = eval_context.get("result") or self.env["ir.attachment"]
        if getattr(result, "_name", None) != "ir.attachment":
            _logger.warning(
                "Python attachment line '%s' did not return ir.attachment records",
                self.name,
            )
            return self.env["ir.attachment"]
        to_copy = result.filtered(
            lambda att: att.res_model != request._name or att.res_id != request.id
        )
        return (result - to_copy) | self._copy_attachments_for_request(
            to_copy, request
        )
