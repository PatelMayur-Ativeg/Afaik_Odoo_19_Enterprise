# -*- coding: utf-8 -*-

from odoo import models


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _get_rendering_context(self, report, docids, data):
        data = super()._get_rendering_context(report, docids, data)
        rows_map = {}
        if docids and report:
            ApprovalType = self.env["multi.approval.type"]
            for doc_id in docids:
                blocks = ApprovalType._get_report_signature_blocks(
                    report.model, doc_id, report
                )
                rows_map[doc_id] = ApprovalType._chunk_signature_blocks(blocks)
        data["approval_signature_rows_map"] = rows_map
        return data
