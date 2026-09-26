from odoo import _, api, fields, models
from odoo.exceptions import UserError
import json
import logging
# from lxml import etree

_STATES = [
    ("draft", "Draft"),
    ("approved", "Approved"),
]


class AssetMovement(models.Model):
    _name = "asset.movement"
    _description = "Asset Movement"
    _inherit = ["mail.thread", "mail.activity.mixin", "analytic.mixin"]
    _order = "id desc"

    name = fields.Char(required=True,default=lambda self: _("New"),
        string="Number",tracking=True,)
    asset_name_id = fields.Many2one('asset.tracking', string="Asset Name")

    state = fields.Selection(selection=_STATES,string="Status",index=True,
        tracking=True,required=True,copy=False,default="draft",)
    date = fields.Date(string="Date",required=True,default=fields.Date.context_today)
    description = fields.Text()
    is_confirm = fields.Boolean()
    
    curr_location_id = fields.Many2one('asset.location', string="Location",)
    curr_employee_id = fields.Many2one('hr.employee', string="Employee")
    curr_department_id = fields.Many2one('hr.department', string="department")

    # curr_location_id = fields.Many2one('asset.location', string="Location",related="asset_name_id.asset_location_id")
    # curr_employee_id = fields.Many2one('hr.employee', string="Employee",related="asset_name_id.employee_id")
    # curr_department_id = fields.Many2one('hr.department', string="department",related="asset_name_id.department_id")

    move_location_id = fields.Many2one('asset.location', string="Location")
    move_employee_id = fields.Many2one('hr.employee', string="Employee")
    move_department_id = fields.Many2one('hr.department', string="department")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name'] = (
                self.env['ir.sequence'].next_by_code('asset_movement_seq_code')
                or _("New")
            )
        return super().create(vals_list)

    def action_confirm(self):
        for rec in self:
            if not rec.asset_name_id:
                continue
            rec.asset_name_id.write({
                "asset_location_id": rec.move_location_id.id,
                "employee_id": rec.move_employee_id.id,
                "department_id": rec.move_department_id.id,
            })
            rec.write({'state': 'approved'})

    @api.onchange("asset_name_id")
    def onchange_asset_name_id(self):
        if self.asset_name_id:
            self.curr_location_id = self.asset_name_id.asset_location_id
            self.curr_employee_id = self.asset_name_id.employee_id
            self.curr_department_id = self.asset_name_id.department_id