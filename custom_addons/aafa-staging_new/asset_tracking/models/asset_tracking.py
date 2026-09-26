from odoo import _, api, fields, models
from odoo.exceptions import UserError
import json
import logging
# from lxml import etree

# _STATES = [
#     ("new", "NEW"),
#     ("active", "ACTIVE"),
#     ("inactive", "INACTIVE"),
#     ('scrap', 'SCRAP'),
#     ("sold", "SOLD"),
# ]


class AssetTracking(models.Model):
    _name = "asset.tracking"
    _description = "Asset Tracking"
    _inherit = ["mail.thread", "mail.activity.mixin", "analytic.mixin"]
    _order = "id desc"

    @api.model
    def _company_get(self):
        return self.env["res.company"].browse(self.env.company.id)

    name = fields.Char(string="Asset Name",required=True,tracking=True,)
    company_id = fields.Many2one(comodel_name="res.company",required=False,
        default=_company_get,tracking=True,)
    # state = fields.Selection(selection=_STATES,string="Status",index=True,
    #     tracking=True,required=True,copy=False,default="new",)
    state_id = fields.Many2one('asset.state.config', string="Status",
        tracking=True,index=True,)

    category_id = fields.Many2one('product.category', string="Category")
    product_id = fields.Many2one('product.template', string="Product")
    vendor_id = fields.Many2one('res.partner', string="Vendor")
    reference = fields.Char(string="Reference")
    date = fields.Date(string="Date",required=True,default=fields.Date.context_today)
    image_asset = fields.Binary(string="Image",store=True)

    asset_location_id = fields.Many2one('asset.location', string="Location")
    employee_id = fields.Many2one('hr.employee', string="Employee")
    department_id = fields.Many2one('hr.department', string="department")

    movement_count = fields.Integer(
        string="Movement count", readonly=True,compute="_compute_movement_count",
    )

    # @api.onchange("product_id")
    # def onchange_product_id(self):
    #     if self.product_id:
    #         self.image_asset = self.product_id.image_1920
    #         # res['value'].update({'image_small': product_obj.image_small or False})


    def _compute_movement_count(self):
        for rec in self:
            order_ids = self.env['asset.movement'].sudo().search([
                ('asset_name_id', '=', rec.id),
            ])
            rec.movement_count = len(order_ids)

    def action_view_asset_movement(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Assets Movement',
            'view_mode': 'list,form',
            'res_model': 'asset.movement',
            'domain': [('asset_name_id', '=', self.id)],
        }