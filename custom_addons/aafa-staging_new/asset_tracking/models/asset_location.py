from odoo import _, api, fields, models
from odoo.exceptions import UserError
import json
import logging
# from lxml import etree

class AssetLocation(models.Model):
    _name = "asset.location"
    _description = "Asset Location"
    _inherit = ["mail.thread", "mail.activity.mixin", "analytic.mixin"]
    _order = "id desc"

    @api.model
    def _company_get(self):
        return self.env.company

    name = fields.Char(string="Name",required=True,tracking=True)
    company_id = fields.Many2one(comodel_name="res.company",required=False,
        default=lambda self: self._company_get(),tracking=True,)
    asset_code = fields.Char(string="Code")
    warehouse_bool = fields.Boolean(string="Warehouse")
    scrap_bool = fields.Boolean(string="Scrap")

    asset_count = fields.Integer(
        string="Assets count", readonly=True,compute="_compute_asset_count",
    )
    
    def _compute_asset_count(self):
        for rec in self:
            order_ids = self.env['asset.tracking'].sudo().search([('asset_location_id','=',rec.id)])
            rec.asset_count = len(order_ids)

    def action_view_asset_tracking(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Assets Tracking',
            'view_mode': 'list,form',
            'res_model': 'asset.tracking',
            'domain': [('asset_location_id', '=', self.id)],
        }