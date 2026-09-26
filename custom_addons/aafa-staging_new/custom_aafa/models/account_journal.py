from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    reversal_journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Reversal Journal",
        check_company=True,
        domain="[('type', '=', type), ('company_id', '=', company_id)]",
        help="If set, this journal is suggested by default in the Reverse wizard "
             "when reversing entries posted in this journal. If empty, standard "
             "Odoo behaviour applies (same journal as the entry).",
    )
