from odoo import models, fields, api

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    acc_number = fields.Char(string="Account Number")
    affaq_queue_id = fields.Many2one('aafaq.import.queue', related='move_id.affaq_queue_id')
    transaction_date = fields.Datetime(string="Transaction Date")
    code_rpt = fields.Char(string="RPT Code")
    ref_num = fields.Char(string="Ref. Number")
    free_text = fields.Text("Free Text")

class AccountMove(models.Model):
    _inherit = "account.move"

    affaq_queue_id = fields.Many2one('aafaq.import.queue', ondelete='set null', string='Import Queue')
    internal_id = fields.Char(string="Internal ID", help="Reference ID from Internal system Aafaq", index=True, copy=False)
    entry_user = fields.Char(string="Entry User")
    entry_date = fields.Datetime(string="Entry Date")
    transaction_date = fields.Datetime(string="Transaction Date")
