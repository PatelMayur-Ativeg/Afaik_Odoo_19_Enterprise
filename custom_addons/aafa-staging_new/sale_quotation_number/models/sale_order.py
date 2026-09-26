from odoo import api, fields, models
class SaleOrder(models.Model):
    _inherit = "sale.order"
    version_ids = fields.One2many('sale.order','quotation_id')
    quotation_id = fields.Many2one('sale.order',string='Quotation No.',copy=False)
    version_ids_count = fields.Integer(string='Versions',compute='compute_version_count')
    def action_view_versions(self):
        return {
            "name": 'Versions',
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "context":{'create':0,'edit':0},
            "domain":[('state','=','snapshot'),('quotation_id','=',self.id)],
            "view_mode": "list,form",
            "view_id": self.env.ref('sale.view_quotation_tree_with_onboarding').id,
            'views': [(self.env.ref('sale.view_quotation_tree_with_onboarding').id, 'list'),(self.env.ref('sale.view_order_form').id, 'form')],
            "target": "current",
        }
    @api.depends('version_ids')
    def compute_version_count(self):
        for rec in self:
            rec.version_ids_count = len(rec.version_ids)

    state = fields.Selection(
        selection_add=[("snapshot", "SnapShot")], ondelete={"snapshot": "set default"}
    )
    version = fields.Char(default='1.0',readonly=True,copy=False)
    def take_snap(self):
        res = self.with_context(version=1).copy()
        version = self.version.split('.')
        version[1] = str(int(version[1])+1)
        new_version = '.'.join(version)
        self.version =new_version

    def copy(self, default=None):
        self.ensure_one()
        if default is None:
            default = {}
        if self.env.context.get('version'):
            default["version"] = self.version
            default["name"] = self.name + '-'+str(self.version)
            default["quotation_id"] = self.id
            default["version"] = self.version
            default["state"] = 'snapshot'
        return super(SaleOrder, self).copy(default)


