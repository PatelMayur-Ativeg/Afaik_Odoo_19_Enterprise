from odoo import models, fields, api, _
from markupsafe import Markup

from ..models.aafaq_import_constants import (
    RECORD_TYPE_JOURNAL_MAP,
    RECORD_TYPE_SELECTION,
)


class AafaqImportWizard(models.TransientModel):
    _name = "aafaq.import.wizard"
    _description = "Aafaq Import Wizard"

    record_type = fields.Selection(RECORD_TYPE_SELECTION, required=True)
    journal_id = fields.Many2one("account.journal", string="Journal")
    company_id = fields.Many2one("res.company", string="Company", required=True, default=lambda self: self.env.company)
    user_id = fields.Many2one("res.users", string="Salesperson", required=False,
                              domain=lambda self: [("share", "=", False)])
    file = fields.Binary("Upload File", required=True, help="Upload XLS, XLSX or CSV file")
    filename = fields.Char("File Name")

    @api.onchange('record_type')
    def onchange_record_type(self):
        if self.record_type in RECORD_TYPE_JOURNAL_MAP:
            self.journal_id = self.env['account.journal'].search([('name', '=', RECORD_TYPE_JOURNAL_MAP[self.record_type])], limit=1).id
        else:
            self.journal_id = False

    def action_aafaq_import_records(self):
        self.ensure_one()
        Queue = self.env["aafaq.import.queue"]
        queue = Queue.create({
            "name": Queue._next_queue_name(self.record_type),
            "file": self.file,
            "filename": self.filename,
            "record_type": self.record_type,
            "company_id": self.company_id.id,
            "user_id": self.user_id.id if self.user_id else False,
            "journal_id": self.journal_id.id if self.journal_id else False,
            "import_source": "manual",
        })
        queue._message_log(body=Markup("<p>%s</p>") % _(
            "Import created from internal upload by %(user)s%(file)s.",
            user=self.env.user.display_name,
            file=_(" (file %s)", self.filename) if self.filename else "",
        ))
        queue.action_process_queue()
        return {
            "type": "ir.actions.act_window",
            "name": "Aafaq Import Queue",
            "res_model": "aafaq.import.queue",
            "view_mode": "form",
            "res_id": queue.id,
            "target": "current",
        }
