from odoo import fields, models


class AafaqImportLog(models.Model):
    _name = "aafaq.import.log"
    _description = "Aafaq Import Log"
    _order = "id desc"

    queue_id = fields.Many2one(
        "aafaq.import.queue",
        string="Import Queue",
        required=True,
        ondelete="cascade",
    )
    level = fields.Selection(
        [
            ("info", "Info"),
            ("warning", "Warning"),
            ("error", "Error"),
        ],
        default="info",
        required=True,
    )
    error_type = fields.Selection(
        [
            ("validation", "Validation Error"),
            ("user", "User Error"),
            ("access", "Access Error"),
            ("missing", "Missing Record"),
            ("system", "System Error"),
        ],
        string="Error Type",
    )
    message = fields.Text("Message", required=True)
    row_number = fields.Integer("Row Number")
    record_key = fields.Char("Record Key")
    model = fields.Char("Target Model")
    data = fields.Json("Raw Data")
    import_source = fields.Selection(
        related="queue_id.import_source",
        store=True,
        string="Source",
    )
    alias_config_id = fields.Many2one(
        related="queue_id.alias_config_id",
        store=True,
        string="Email Alias",
    )
    alias_email = fields.Char(
        related="queue_id.alias_config_id.alias_email",
        string="Alias Email",
    )
    email_from = fields.Char(
        related="queue_id.email_from",
        string="Email From",
    )
    processed_at = fields.Datetime(default=fields.Datetime.now)
