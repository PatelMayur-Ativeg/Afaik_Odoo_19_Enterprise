# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from odoo import fields, models


class CrossoveredBudget(models.Model):
    _inherit = "budget.analytic"

    department_id = fields.Many2one('hr.department', string="Department")

class AnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'


    department_id = fields.Many2one('hr.department', string="Department")
    

