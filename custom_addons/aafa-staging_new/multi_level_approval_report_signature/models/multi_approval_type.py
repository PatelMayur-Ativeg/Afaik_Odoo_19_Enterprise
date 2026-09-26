# -*- coding: utf-8 -*-

from odoo import fields, models
from odoo.tools.misc import format_date


class MultiApprovalType(models.Model):
    _inherit = "multi.approval.type"

    print_signature = fields.Boolean(
        string="Print Signatures on Report",
        help="When enabled, selected reports print signatures from this approval type.",
    )
    print_creator_signature = fields.Boolean(
        string="Print Creator Signature",
        help="Print the user who created the document as the first signature. "
        "This is not printed unless enabled.",
    )
    creator_signature_label = fields.Char(
        string="Creator Signature Label",
        default="Prepared By",
        translate=True,
    )
    signature_report_ids = fields.Many2many(
        "ir.actions.report",
        "multi_approval_type_signature_report_rel",
        "type_id",
        "report_id",
        string="Linked Reports",
        help="Reports that should include these signatures when printed.",
    )

    def _get_signature_report_types(self, report):
        if not report:
            return self.browse()
        return self.sudo().search(
            [
                ("print_signature", "=", True),
                ("is_configured", "=", True),
                ("model_id", "=", report.model),
                ("signature_report_ids", "in", report.id),
            ]
        )

    def _get_origin_approval_requests(self, model_name, res_id):
        origin = f"{model_name},{res_id}"
        return (
            self.env["multi.approval"]
            .sudo()
            .search(
                [
                    ("origin_ref", "=", origin),
                    ("type_id", "in", self.ids),
                    ("state", "in", ("Submitted", "Approved")),
                ],
                order="id",
            )
        )

    def _get_line_signature_role(self, request, line):
        type_lines = request.type_id.line_ids
        match = type_lines.filtered(lambda l: l.name == line.name)[:1]
        if not match:
            match = type_lines.filtered(lambda l: l.sequence == line.sequence)[:1]
        if match and match.signature_label:
            return match.signature_label
        return self.env._("Approved By")

    def _build_signature_block(self, role, user, date_value):
        if not user:
            return False
        return {
            "role": role or "",
            "name": user.display_name or user.name or "",
            "date": format_date(self.env, date_value) if date_value else "",
            "image_src": user._get_approval_report_signature_src(),
        }

    def _get_report_signature_blocks(self, model_name, res_id, report):
        types = self._get_signature_report_types(report)
        if not types:
            return []
        record = self.env[model_name].browse(res_id)
        if not record.exists():
            return []

        blocks = []
        creator_type = types.filtered("print_creator_signature")[:1]
        if creator_type and record.create_uid:
            creator_block = self._build_signature_block(
                creator_type.creator_signature_label or self.env._("Prepared By"),
                record.create_uid,
                record.create_date,
            )
            if creator_block:
                blocks.append(creator_block)

        seen_line_ids = set()
        requests = types._get_origin_approval_requests(model_name, res_id)
        for request in requests:
            approved_lines = request.line_ids.filtered(
                lambda line: line.state == "Approved"
            ).sorted("sequence")
            for line in approved_lines:
                if line.id in seen_line_ids:
                    continue
                seen_line_ids.add(line.id)
                block = self._build_signature_block(
                    self._get_line_signature_role(request, line),
                    line.user_id,
                    line.approved_date,
                )
                if block:
                    blocks.append(block)
        return blocks

    def _chunk_signature_blocks(self, blocks, size=3):
        rows = []
        for index in range(0, len(blocks), size):
            row = blocks[index : index + size]
            width = int(100 / len(row)) if row else 100
            for block in row:
                block["cell_style"] = (
                    f"width:{width}%; text-align:center; vertical-align:bottom; "
                    "padding: 0 10px 12px 10px; border: none;"
                )
            rows.append(row)
        return rows
