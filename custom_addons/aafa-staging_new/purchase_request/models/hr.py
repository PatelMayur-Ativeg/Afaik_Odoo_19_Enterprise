# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from odoo import fields, models


class HrDepartment(models.Model):
    _inherit = "hr.department"

    analytic_account_id = fields.Many2one(
        comodel_name='account.analytic.account',
        string="Analytic Account",
        copy=False,  # Unrequired company
       )
    picking_type_id = fields.Many2one('stock.picking.type', domain="[('code', '=', 'internal')]", string="Operation Type")
    src_location_id = fields.Many2one('stock.location', "Source Location")
    dest_location_id = fields.Many2one('stock.location', "Destination Location")