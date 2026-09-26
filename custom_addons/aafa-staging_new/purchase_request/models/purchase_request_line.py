# Copyright 2018-2019 ForgeFlow, S.L.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError, UserError
from collections import defaultdict
import json
import logging


_logger = logging.getLogger(__name__)



_STATES = [
    ("draft", "Draft"),
    ("to_approve", "To be approved"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
    ("done", "Done"),
]


class PurchaseRequestLine(models.Model):

    _name = "purchase.request.line"
    _description = "Purchase Request Line"
    _inherit = ["mail.thread", "mail.activity.mixin", "analytic.mixin"]
    _order = "id desc"

    name = fields.Char(string="Description", tracking=True)
    # product_uom_category_id = fields.Many2one(
    #     'uom.category',
    #     string="UoM Category",
    #     # related="product_id.uom_id.category_id",
    #     store=True,
    #     readonly=True
    # )
    product_uom_id = fields.Many2one(
        'uom.uom',
        string="UoM",
        tracking=True,
        # domain="[('category_id', '=', product_uom_category_id)]",
    )
    product_qty = fields.Float(
        string="Quantity", tracking=True, digits="Product Unit of Measure"
    )
    requisition_action = fields.Selection([('internal_transfer', 'Internal Picking'),('purchase_order', 'Purchase Order'),('partial', 'Partial')], string="Requisition Action",copy=False)
    request_id = fields.Many2one(
        comodel_name="purchase.request",
        string="Purchase Request",
        ondelete="cascade",
        readonly=True,
        index=True,
        auto_join=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        related="request_id.company_id",
        string="Company",
        store=True,
    )
    requested_by = fields.Many2one(
        comodel_name="res.users",
        related="request_id.requested_by",
        string="Requested by",
        store=True,
    )
    employee_id = fields.Many2one(
        comodel_name="hr.employee",
        related="request_id.employee_id",
        string="Employee",
        store=True,
    )    
    assigned_to = fields.Many2one(
        comodel_name="res.users",
        related="request_id.assigned_to",
        string="Assigned to",
        store=True,
    )
    assigned_manager_id = fields.Many2one(
        comodel_name="hr.employee",
        related="request_id.assigned_manager_id",
        string="Assigned Manager",
        store=True,
    )
    vendor_id = fields.Many2many('res.partner', 'purchase_request_line_vendor_ids', string='Vendors', help="Vendor Ids")
    # vendor_id = fields.Many2one(comodel_name='res.partner', string="Vendor",copy=False)
    date_start = fields.Date(related="request_id.date_start", store=True)

    description = fields.Text(
        related="request_id.description",
        string="PR Description",
        store=True,
        readonly=False,
    )
    origin = fields.Char(
        related="request_id.origin", string="Source Document", store=True
    )
    date_required = fields.Date(
        string="Request Date",
        required=True,
        tracking=True,
        default=fields.Date.context_today,
    )
    is_editable = fields.Boolean(compute="_compute_is_editable", readonly=True)

    specifications = fields.Text()
    request_state = fields.Selection(
        string="Request state",
        related="request_id.state",
        store=True,
    )
    supplier_id = fields.Many2one(
        comodel_name="res.partner",
        string="Preferred supplier",
        compute="_compute_supplier_id",
        compute_sudo=True,
        store=True,
    )
    cancelled = fields.Boolean(readonly=True, default=False, copy=False)

    purchased_qty = fields.Float(
        string="RFQ/PO Qty",
        digits="Product Unit of Measure",
        compute="_compute_purchased_qty",
    )
    purchase_lines = fields.Many2many(
        comodel_name="purchase.order.line",
        relation="purchase_request_purchase_order_line_rel",
        column1="purchase_request_line_id",
        column2="purchase_order_line_id",
        string="Purchase Order Lines",
        readonly=True,
        copy=False,
    )
    move_dest_ids = fields.One2many(
        comodel_name="stock.move",
        inverse_name="purchase_request_line_id",
        string="Downstream Moves",
    )

    qty_in_progress = fields.Float(
        digits="Product Unit of Measure",
        readonly=True,
        compute="_compute_qty",
        store=True,
        help="Quantity in progress.",
    )
    qty_done = fields.Float(
        digits="Product Unit of Measure",
        readonly=True,
        compute="_compute_qty",
        store=True,
        help="Quantity completed",
    )
    qty_cancelled = fields.Float(
        digits="Product Unit of Measure",
        readonly=True,
        compute="_compute_qty_cancelled",
        store=True,
        help="Quantity cancelled",
    )
    qty_to_buy = fields.Float(
        compute="_compute_qty_to_buy",inverse="_inverse_qty_to_buy",
        string="Qty to Buy",
        store=True,
        copy=False,
    )
    pending_qty_to_receive = fields.Float(
        compute="_compute_qty_to_buy",inverse="_inverse_qty_to_buy",
        digits="Product Unit of Measure",
        copy=False,
        string="Qty to Receive",
        store=True,
    )
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Product",
        domain=[("purchase_ok", "=", True)],
        tracking=True,
    )
    cost_price = fields.Float("Cost Price", compute="compute_cost_price", inverse="_inverse_cost_price", store=True, copy=False)
    free_qty_today = fields.Float(compute='_compute_qty_at_date', digits='Product Unit of Measure')
    analytic_account_id = fields.Many2one(
        comodel_name='account.analytic.account',
        string="Analytic Account", related="request_id.analytic_account_id",
        copy=False,  # Unrequired company
       )
    remarks = fields.Char("Remarks")
    pr_category_id = fields.Many2one(
        "purchase.request.category",
        string="Category",
        related="request_id.pr_category_id",
    )
    able_to_modify_costprice = fields.Boolean(compute='set_access_for_costprice', string='Is user able to modify Cost Price?')
    chosen_vendor_id = fields.Many2one('res.partner', compute="_compute_chosen_vendor", string='Chosen Vendor')
            
    
    # @api.depends('product_id')
    def _compute_chosen_vendor(self):
        self.chosen_vendor_id=False

        for rec in self:
            if rec.product_id:
                order_ids = self.env['purchase.order'].sudo().search([
                    ('request_id', '=', rec.request_id.id),
                    ('order_line.product_id', '=', rec.product_id.id),
                    ('state', '=', 'done'),
                ], limit=1)
                if order_ids:
                    rec.chosen_vendor_id=order_ids.partner_id
                    
            #     else:
            # #         self.chosen_vendor_id=False
            #     print("chosen_vendor_id------------------",rec.chosen_vendor_id.name)

            # else:
            #     self.chosen_vendor_id=False


    def set_access_for_costprice(self):
        if self.env.user.has_group('purchase_request.group_purchase_request_gnadmin') or self.env.user.has_group('purchase_request.group_purchase_request_itadmin'):
            self.able_to_modify_costprice = True
        else:
            self.able_to_modify_costprice = False

    @api.depends('product_id')
    def compute_cost_price(self):
        for rec in self:
            if rec.product_id:
                rec.cost_price = rec.product_id.standard_price
            else:
                rec.cost_price = 0.00

    def _inverse_qty_to_buy(self):
        pass

    def _inverse_cost_price(self):
        pass

    @api.depends(
        'move_dest_ids.state',
        'move_dest_ids.product_uom_qty',
        'move_dest_ids.product_uom',
        'product_uom_id',
        'product_qty',
        'purchase_lines.state',
        'purchase_lines.product_qty',
        'purchase_lines.product_uom_id',
    )
    def _compute_qty(self):
        for rec in self:
            qty_in_progress = qty_done = 0.0
            for move in rec.move_dest_ids:
                move_qty = move.product_uom_qty
                if rec.product_uom_id and move.product_uom != rec.product_uom_id:
                    move_qty = move.product_uom._compute_quantity(
                        move_qty, rec.product_uom_id
                    )
                if move.state == 'done':
                    qty_done += move_qty
                elif move.state not in ('cancel', 'draft'):
                    qty_in_progress += move_qty
            rec.qty_in_progress = qty_in_progress
            rec.qty_done = qty_done

    @api.depends('cancelled', 'product_qty')
    def _compute_qty_cancelled(self):
        for rec in self:
            rec.qty_cancelled = rec.product_qty if rec.cancelled else 0.0

    @api.depends('product_id', 'product_qty', 'product_uom_id','free_qty_today','requisition_action')
    def _compute_qty_to_buy(self):
        for rec in self:
            if rec.product_id and rec.free_qty_today > 0 and rec.requisition_action == 'partial':
                rec.qty_to_buy =  rec.free_qty_today - rec.product_qty
                rec.pending_qty_to_receive = rec.free_qty_today
            elif rec.product_id and rec.free_qty_today > 0 and rec.requisition_action == 'purchase_order':
                rec.qty_to_buy = rec.product_qty
                rec.pending_qty_to_receive = 0
            elif rec.product_id and rec.free_qty_today > 0 and rec.requisition_action == 'internal_transfer':
                rec.pending_qty_to_receive = rec.product_qty
            else:
                rec.qty_to_buy = 0
                rec.pending_qty_to_receive = 0

    @api.onchange('qty_to_buy', 'pending_qty_to_receive')
    def set_qty_in_lines(self):
        for rec in self:
            if rec.qty_to_buy>0:
                rec.pending_qty_to_receive = rec.product_qty - rec.qty_to_buy
            elif rec.pending_qty_to_receive>0:
                rec.qty_to_buy = rec.product_qty - rec.pending_qty_to_receive

    @api.depends('product_id')
    def _compute_qty_at_date(self):
        quant_obj = self.env['stock.quant'].sudo()
        location_data = self.env['stock.location'].sudo().search([('show_pr_qty','=',True)])
        
        for rec in self:
            available_qty=0
            if rec.product_id and location_data:
                for location in location_data:
                    available_qty += rec.product_id.with_context({'location' : location.id}).qty_available
                if available_qty:
                    rec.free_qty_today = float(available_qty)
                else:
                    rec.free_qty_today = 0
            else:
                rec.free_qty_today = 0

    # @api.depends(
    #     'product_id', 'product_qty', 'product_uom_id', 'request_id.date_start',)
    # def _compute_qty_at_date(self):
    #     for rec in self:
    #         treated = rec.browse()
    #         qty_processed_per_product = defaultdict(lambda: 0)
    #         grouped_lines = defaultdict(lambda: rec.env['purchase.request.line'])
    #         if rec.product_id:
    #             warehouse_id = rec.request_id.picking_type_id.warehouse_id
    #             scheduled_date = rec.request_id.date_start
    #             for line in rec:
    #                 grouped_lines[(warehouse_id, line.request_id.date_start)] |= line
    #             for (warehouse, scheduled_date), lines in grouped_lines.items():
    #                 product_qties = lines.mapped('product_id').with_context(to_date=False, warehouse=warehouse).read([
    #                     'qty_available',
    #                     'free_qty',
    #                     'virtual_available',
    #                 ])
    #                 qties_per_product = {
    #                     product['id']: (product['qty_available'], product['free_qty'], product['virtual_available'])
    #                     for product in product_qties
    #                 }
    #                 for line in lines:
    #                     qty_available_today, free_qty_today, virtual_available_at_date = qties_per_product[line.product_id.id]
    #                     line.free_qty_today = free_qty_today - qty_processed_per_product[line.product_id.id]
    #                     product_qty = line.product_qty
    #                     if line.product_uom_id and line.product_id.uom_id and line.product_uom_id != line.product_id.uom_id:
    #                         line.free_qty_today = line.product_id.uom_id._compute_quantity(line.free_qty_today, line.product_uom_id)
    #                         product_qty = line.product_uom_id._compute_quantity(product_qty, line.product_id.uom_id)
    #                     qty_processed_per_product[line.product_id.id] += product_qty
    #                 treated |= lines
    #         else:
    #             remaining = (rec - treated)
    #             remaining.free_qty_today = False

    @api.onchange('requisition_action')
    def onchange_requisition_action(self):
        for rec in self:
            if rec.requisition_action == 'internal_transfer':
                rec.write({
                    'vendor_id': False
                })
            elif rec.requisition_action == 'purchase_order':
                sellers = rec.product_id.seller_ids.filtered(
                lambda si, rec=rec: not si.company_id or si.company_id == rec.company_id
            )
                if not sellers:
                    raise ValidationError("No Supplier available for this product")

    @api.depends(
        "purchase_lines",
        "request_id.state",
    )
    def _compute_is_editable(self):
        for rec in self:
            if rec.request_id.state in (
                "waiting_for_approval",
                "in_progress",
                "reject",
                "done",
            ):
                rec.is_editable = False
            else:
                rec.is_editable = True
        for rec in self.filtered(lambda p: p.purchase_lines):
            rec.is_editable = False

    @api.depends("product_id", "product_id.seller_ids")
    def _compute_supplier_id(self):
        for rec in self:
            sellers = rec.product_id.seller_ids.filtered(
                lambda si, rec=rec: not si.company_id or si.company_id == rec.company_id
            )
            rec.supplier_id = sellers[0].partner_id if sellers else False

    @api.onchange("product_id")
    def onchange_product_id(self):
        if self.product_id:
            name = self.product_id.name
            if self.product_id.code:
                name = "[{}] {}".format(self.product_id.code, name)
            if self.product_id.description_purchase:
                name += "\n" + self.product_id.description_purchase
            self.product_uom_id = self.product_id.uom_id.id
            self.product_qty = 1
            self.name = name

    def do_cancel(self):
        """Actions to perform when cancelling a purchase request line."""
        self.write({"cancelled": True})

    def do_uncancel(self):
        """Actions to perform when uncancelling a purchase request line."""
        self.write({"cancelled": False})

    def write(self, vals):
        res = super(PurchaseRequestLine, self).write(vals)
        if vals.get("cancelled"):
            requests = self.mapped("request_id")
            requests.check_auto_reject()
        return res

    def _compute_purchased_qty(self):
        for rec in self:
            rec.purchased_qty = 0.0
            for line in rec.purchase_lines.filtered(lambda x: x.state != "cancel"):
                if rec.product_uom_id and line.product_uom != rec.product_uom_id:
                    rec.purchased_qty += line.product_uom._compute_quantity(
                        line.product_qty, rec.product_uom_id
                    )
                else:
                    rec.purchased_qty += line.product_qty

    def _can_be_deleted(self):
        self.ensure_one()
        return self.request_state == "draft"

    def unlink(self):
        if self.mapped("purchase_lines"):
            raise UserError(
                _("You cannot delete a record that refers to purchase lines!")
            )
        for line in self:
            if not line._can_be_deleted():
                raise UserError(
                    _(
                        "You can only delete a purchase request line "
                        "if the purchase request is in draft state."
                    )
                )
        return super(PurchaseRequestLine, self).unlink()


class RequestNewLine(models.Model):

    _name = "request.new.line"
    _description = "Request New Line"
    _inherit = ["mail.thread", "mail.activity.mixin", "analytic.mixin"]
    _order = "id desc"

    desc = fields.Char(string="Description", tracking=True)
    request_qty =  fields.Float("Qty")
    cost_price = fields.Float("Cost price")
    is_editable = fields.Boolean(compute="_compute_is_editable", readonly=True)
    cancelled = fields.Boolean(readonly=True, default=False, copy=False)
    request_id = fields.Many2one(
        comodel_name="purchase.request",
        string="Purchase Request",
        ondelete="cascade",
        readonly=True,
        index=True,
        auto_join=True,
    )
    request_state = fields.Selection(
        string="Request state",
        related="request_id.state",
        store=True,
    )

    @api.depends(
        "request_id.state",
    )
    def _compute_is_editable(self):
        for rec in self:
            if rec.request_id.state in (
                "waiting_for_approval",
                "in_progress",
                "reject",
                "done",
            ):
                rec.is_editable = False
            else:
                rec.is_editable = True