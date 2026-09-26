from odoo import models, fields, api, _
from datetime import datetime, time, date, timedelta


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    @api.model
    def _default_picking_type(self):
        return self._get_picking_type(self.env.context.get('company_id') or self.env.company.id)

    origin = fields.Char('Source Document', copy=False,
        help="Reference of the document that generated this purchase order "
             "request (e.g. a sales order)",tracking=True)
    partner_ref = fields.Char('Vendor Reference', copy=False,
        help="Reference of the sales order or bid sent by the vendor. "
             "It's used to do the matching when you receive the "
             "products as this reference is usually written on the "
             "delivery order sent by your vendor.",tracking=True)
    date_order = fields.Datetime('Order Deadline', required=True, index=True, copy=False, default=fields.Datetime.now,
        help="Depicts the date within which the Quotation should be confirmed and converted into a purchase order.",tracking=True)
    dest_address_id = fields.Many2one('res.partner', compute='_compute_dest_address_id', store=True, readonly=False,tracking=True)
    currency_id = fields.Many2one('res.currency', 'Currency', required=True,
        default=lambda self: self.env.company.currency_id.id,tracking=True)
    
    notes = fields.Html('Terms and Conditions', tracking=True)
    date_planned = fields.Datetime(
        string='Expected Arrival', index=True, copy=False, compute='_compute_date_planned', store=True, readonly=False,
        help="Delivery date promised by vendor. This date is used to determine expected arrival of products.", tracking=True)
    fiscal_position_id = fields.Many2one('account.fiscal.position', string='Fiscal Position', domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]", tracking=True)
    payment_term_id = fields.Many2one('account.payment.term', 'Payment Terms', domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]", tracking=True)
    incoterm_id = fields.Many2one('account.incoterms', 'Incoterm', help="International Commercial Terms are a series of predefined commercial terms used in international transactions.", tracking=True)
    picking_type_id = fields.Many2one('stock.picking.type', 'Deliver To', required=True, default=_default_picking_type, domain="['|', ('warehouse_id', '=', False), ('warehouse_id.company_id', '=', company_id)]",
        help="This will determine operation type of incoming shipment", tracking=True)
 
    is_purchase_requisition = fields.Boolean(string="is_purchase_requisition", default=False, tracking=True)
    po_categ_id = fields.Many2one('purchase.category',string="Purchase Category", tracking=True)
    custom_requisition_id = fields.Many2one(
        'material.purchase.requisition',
        string='Purchase Requisition',
        copy=False,
        index=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        tracking=True,
        index=True,
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        tracking=True,
        index=True,
    )

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            self.department_id = self.employee_id.department_id
        else:
            self.department_id = False

    def _fill_pr_values(self, vals):
        """Copy employee, department and origin from the source purchase requisition."""
        if vals.get('custom_requisition_id'):
            requisition = self.env['material.purchase.requisition'].browse(vals['custom_requisition_id'])
            vals.setdefault('employee_id', requisition.employee_id.id)
            vals.setdefault('department_id', requisition.department_id.id)
            if requisition.name and not vals.get('origin'):
                vals['origin'] = requisition.name
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._fill_pr_values(vals)
        return super().create(vals_list)

    def action_view_purchase_request(self):
        self.ensure_one()
        if self.custom_requisition_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Purchase Requisition'),
                'res_model': 'material.purchase.requisition',
                'view_mode': 'form',
                'res_id': self.custom_requisition_id.id,
            }
        try:
            return super().action_view_purchase_request()
        except AttributeError:
            return True

    def _approval_allowed(self):
        return True

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'
    
    prod_categ_id = fields.Many2one('product.category',string="Product Category",related="product_id.categ_id")
    analytic_remain_amt = fields.Monetary(string="Remaining Amount",compute='_compute_analytic_remain_amt',)
    analytic_account_id = fields.Many2one('account.analytic.account',string="Analytic Account")
    budget_id = fields.Many2one('budget.analytic',string="Budget")
    choose_reason = fields.Text(string="Choose Reason", copy=False)

    def action_choose(self):
        """Open the reason wizard, then apply the standard choose on confirm."""
        self.ensure_one()
        return {
            'name': _('Reason for Choosing this Line'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order.line.choose.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('purchase_extension.purchase_order_line_choose_wizard_form').id,
            'target': 'new',
            'context': {
                'default_line_id': self.id,
                'default_reason': self.choose_reason or False,
            },
        }

    def action_choose_confirm(self, reason):
        """Store the reason and run the standard compare-line choose."""
        self.ensure_one()
        self.choose_reason = reason
        return super().action_choose()

    def action_clear_quantities(self):
        self.filtered('choose_reason').write({'choose_reason': False})
        return super().action_clear_quantities()
    

    @api.depends('analytic_account_id')
    def _compute_analytic_remain_amt(self):
        for line in self:
            line.analytic_remain_amt=line.analytic_account_id.total_real_amount
 
    @api.model
    def default_get(self,fields):
        res = super(PurchaseOrderLine, self).default_get(fields)
        analytic_account_id  = False

        if self.env.user.analytic_account_id:
            analytic_account_id = self.env.user.analytic_account_id.id

        res.update({
            'analytic_account_id' : analytic_account_id,
        })

        return res

