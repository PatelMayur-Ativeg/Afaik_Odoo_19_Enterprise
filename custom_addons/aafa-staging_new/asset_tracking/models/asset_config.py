from odoo import _, api, fields, models

class AssetStateConfig(models.Model):
    _name = "asset.state.config"
    _description = "Asset Status Config"
    _order = "id asc"

    name = fields.Char(string="Status",required=True,)
    # code = fields.Integer(string="Code",required=True,)
