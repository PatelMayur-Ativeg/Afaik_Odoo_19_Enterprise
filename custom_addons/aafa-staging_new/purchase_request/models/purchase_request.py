# Copyright 2018-2019 ForgeFlow, S.L.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from odoo import _, api, fields, models
from odoo.exceptions import UserError
import json
import logging
# from lxml import etree


_logger = logging.getLogger(__name__)



_STATES = [
    ("draft", "Draft"),
    ("waiting_for_approval", "Waiting for Approval"),
    ("in_progress", "In Progress"),
    ("reject", "Rejected"),
    ("done", "Done"),
]


class PurchaseRequest(models.Model):

    _name = "purchase.request"
    _description = "Purchase Request"
    _inherit = ["mail.thread", "mail.activity.mixin", "analytic.mixin"]
    _order = "id desc"

    @api.model
    def _company_get(self):
        return self.env["res.company"].browse(self.env.company.id)

    @api.model
    def _get_default_requested_by(self):
        return self.env["res.users"].browse(self.env.uid)

    @api.model
    def _get_default_employee(self):
        employee = self.env.user.employee_id
        return employee.id if employee else False

    @api.model
    def _get_default_name(self):
        return self.env["ir.sequence"].next_by_code("purchase.request")

    @api.model
    def _default_picking_type(self):
        type_obj = self.env["stock.picking.type"]
        company_id = self.env.context.get("company_id") or self.env.company.id
        types = type_obj.search(
            [("code", "=", "incoming"), ("warehouse_id.company_id", "=", company_id)]
        )
        if not types:
            types = type_obj.search(
                [("code", "=", "internal"), ("warehouse_id", "=", False)]
            )
        return types[:1]

    @api.depends("state")
    def _compute_is_editable(self):
        for rec in self:
            if rec.state not in ("draft", "waiting_for_approval"):
                rec.is_editable = False
            else:
                rec.is_editable = True

    name = fields.Char(
        string="Request Reference",
        required=True,
        default=lambda self: _("New"),
        tracking=True,
    )

    origin = fields.Char(string="Source Document")

    date_start = fields.Date(
        string="Requisition date",
        help="Date when the user initiated the request.",
        default=fields.Date.context_today,
        tracking=True,
    )
    recieved_date = fields.Date(
        string="Recieved date",
        help="Date when the request is recieved",
    )
    requisition_deadline = fields.Date(
        string="Requisition Deadline",
        help="Deadline",
    )

    analytic_account_id = fields.Many2one(
        comodel_name='account.analytic.account',
        string="Analytic Account",
        copy=False,  # Unrequired company
       )
    # , check_company=True
    domain="['|', ('company_id', '=', False), ('company_id', '=', self.env.company.id)]"
    employee_id = fields.Many2one(comodel_name="hr.employee",
        required=True,
        copy=False,
        tracking=True,
        default=_get_default_employee,
        index=True,)

    requested_by = fields.Many2one(
        comodel_name="res.users",
        required=True,
        copy=False,
        tracking=True,
        default=_get_default_requested_by,
        index=True,
    )
    assigned_manager_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Requisition Responsible",
        tracking=True,
        index=True,
    )

    assigned_to = fields.Many2one(
        comodel_name="res.users",
        string="Approver",
        tracking=True,
        domain=lambda self: [
            (
                "groups_id",
                "in",
                self.env.ref("purchase_request.group_purchase_request_manager").id,
            )
        ],
        index=True,
    )
    description = fields.Text()

    company_id = fields.Many2one(
        comodel_name="res.company",
        required=False,
        default=_company_get,
        tracking=True,
    )
    line_ids = fields.One2many(
        comodel_name="purchase.request.line",
        inverse_name="request_id",
        string="Products to Purchase",
        readonly=False,
        copy=True,
        tracking=True,
    )
    new_line_ids = fields.One2many(comodel_name='request.new.line', inverse_name="request_id",
        string="New Product Lines",
        readonly=False,
        copy=True,
        tracking=True)
    product_id = fields.Many2one(
        comodel_name="product.product",
        related="line_ids.product_id",
        string="Product",
        readonly=True,
    )
    state = fields.Selection(
        selection=_STATES,
        string="Status",
        index=True,
        tracking=True,
        required=True,
        copy=False,
        default="draft",
    )
    is_editable = fields.Boolean(compute="_compute_is_editable", readonly=True)
    to_approve_allowed = fields.Boolean(compute="_compute_to_approve_allowed")
    picking_type_id = fields.Many2one(
        comodel_name="stock.picking.type",
        string="Picking Type",
        required=True,
        default=_default_picking_type,
    )
    # group_id = fields.Many2one(
    #     comodel_name="procurement.group",
    #     string="Procurement Group",
    #     copy=False,
    #     index=True,
    # )
    purchase_count = fields.Integer(
        string="Purchases count", compute="_compute_purchase_count", readonly=True
    )
    picking_count = fields.Integer(
        string="Picking count", compute="_compute_picking_count", readonly=True
    )
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    pr_category_id = fields.Many2one(
        "purchase.request.category", string="Category"
    )
    new_product_request = fields.Boolean("New Product Request", default=False)
    show_rfq_btn = fields.Boolean(compute='show_rfq_btn_fn')
    department_id = fields.Many2one('hr.department', string="Department")
    budget_id = fields.Many2one('budget.analytic', string="Budget")
    budget_planned_amt = fields.Monetary(compute='compute_planned_amt')
    practical_amt = fields.Monetary(compute='_compute_practical_amount')
    forecast_amt = fields.Monetary(compute='_compute_forecast_amt', string="PR Amount")
    forecast_remaining_amt = fields.Monetary(compute='_compute_forecast_amt', string="Remaining Budget")
    budget_id_domain = fields.Char(
        compute="_compute_budget_id_domain",
        readonly=True,
        store=False,
    )
    check_budget_amt = fields.Boolean(compute="compute_budget_amt", store=True)
    show_budget_fields = fields.Boolean(compute='budget_fields_visibility')
    view_submit_button = fields.Boolean(compute='check_submit_button')
    src_location_id = fields.Many2one('stock.location', "Source Location")
    dest_location_id = fields.Many2one('stock.location', "Destination Location")
    pr_type = fields.Selection([('recurring', 'Recurring'),('new', 'New')], string="PR Type")
    budget_type = fields.Selection([('yes', 'Yes'),('no', 'No')],string="Budget Type")

    @api.depends('state', 'department_id')
    def budget_fields_visibility(self):
        user = self.env.user

        for rec in self:
            if rec.department_id:
                manager_id = rec.department_id.manager_id
                employee_id = user.employee_id

                if manager_id == employee_id:
                    rec.show_budget_fields = True

                elif user.has_group('purchase_request.pr_budget_access_group') or \
                     user.has_group('purchase_request.group_purchase_request_itadmin') or \
                     user.has_group('purchase_request.group_purchase_request_gnadmin'):
                    rec.show_budget_fields = True

                else:
                    rec.show_budget_fields = False
            else:
                rec.show_budget_fields = False


    @api.depends('department_id','line_ids','budget_id')
    def compute_budget_amt(self):
        if self.department_id:
            for rec in self:
                if rec.forecast_remaining_amt < 0:
                    rec.check_budget_amt = True
                    # raise UserError('Budget Amount exceeds. !')
                else:
                    balance = rec.budget_planned_amt -  rec.forecast_remaining_amt
                    if balance < 0:
                        rec.check_budget_amt = True
                    else:
                        rec.check_budget_amt = False

    @api.onchange('analytic_account_id')
    def onchange_analytic(self):
        for rec in self:
            if rec.analytic_account_id:
                budget_lines = self.env['budget.line'].search([
                    ('account_id', '=', rec.analytic_account_id.id),
                    ('date_from', '<=', rec.date_start),
                    ('date_to', '>=', rec.date_start),
                ], limit=1)
                if budget_lines:
                    rec.budget_id = budget_lines.budget_analytic_id.id

    @api.onchange('department_id', 'date_start')
    def _onchange_budget(self):
        for rec in self:
            if rec.department_id:
                rec.picking_type_id = rec.department_id.picking_type_id.id if rec.department_id.picking_type_id else False
                rec.src_location_id = rec.department_id.src_location_id.id if rec.department_id.src_location_id else False
                rec.dest_location_id = rec.department_id.dest_location_id.id if rec.department_id.dest_location_id else False
            if rec.department_id and rec.date_start and rec.analytic_account_id:
                budget_lines = self.env['budget.line'].search([
                    ('account_id', '=', rec.analytic_account_id.id),
                    ('date_from', '<=', rec.date_start),
                    ('date_to', '>=', rec.date_start),
                ], limit=1)
                if budget_lines:
                    rec.budget_id = budget_lines.budget_analytic_id.id

    @api.depends('department_id', 'date_start')
    def _compute_budget_id_domain(self):
        for rec in self:
            # ,('department_id', '=', rec.department_id.id)
            rec.budget_id_domain = json.dumps(
                [('state','=','done'), ('date_from', '<=', str(rec.date_start)),('date_to', '>=', str(rec.date_start))]
            )

    def _sum_analytic_line_amount(self, analytic_account, date_from, date_to):
        """Sum analytic line amounts (Odoo 19: use _read_group, not read_group amount_sum)."""
        if not analytic_account or not date_from or not date_to:
            return 0.0
        domain = [
            ('account_id', '=', analytic_account.id),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
        ]
        groups = self.env['account.analytic.line']._read_group(
            domain=domain,
            groupby=[],
            aggregates=['amount:sum'],
        )
        return groups[0][0] if groups else 0.0

    @api.depends(
        'budget_id',
        'analytic_account_id',
        'line_ids.product_id',
        'line_ids.product_qty',
        'line_ids.cost_price',
        'new_line_ids.cost_price',
        'new_line_ids.request_qty'
    )
    def _compute_forecast_amt(self):
        for line in self:
            subtotal = 0.0
            for rec in line.line_ids:
                subtotal += rec.cost_price * rec.product_qty
            for rec in line.new_line_ids:
                subtotal += rec.cost_price * rec.request_qty
            line.forecast_amt = -1 * subtotal
            line.forecast_remaining_amt = (
                line.budget_planned_amt + (line.practical_amt + line.forecast_amt)
            )

    @api.depends('budget_id', 'analytic_account_id')
    def _compute_practical_amount(self):
        for line in self:
            if line.analytic_account_id and line.budget_id:
                practical_amt = line._sum_analytic_line_amount(
                    line.analytic_account_id,
                    line.budget_id.date_from,
                    line.budget_id.date_to,
                )
                # line.practical_amt = -1 * practical_amt
                line.practical_amt = practical_amt
            else:
                line.practical_amt = 0.0

    @api.depends('budget_id', 'analytic_account_id')
    def compute_planned_amt(self):
        for record in self:
            if record.budget_id and record.analytic_account_id:
                planned_amt = sum(
                    record.budget_id.budget_line_ids.filtered(
                        lambda line: line.account_id == record.analytic_account_id
                    ).mapped('budget_amount')
                )
                # record.budget_planned_amt = -1 * planned_amt
                record.budget_planned_amt = planned_amt
            else:
                record.budget_planned_amt = 0
                
    @api.onchange('line_ids')
    def onchangelineids(self):
        if self.check_budget_amt and self.budget_id:
            return {

                'warning': {

                    'title': 'Warning!',

                    'message': 'Budget Amount Exceeds. !'}

            }
    @api.depends('state', 'new_line_ids', 'line_ids')
    def show_rfq_btn_fn(self):
        for rec in self:
            new_product_only = (
                rec.new_product_request
                and rec.new_line_ids
                and not rec.line_ids
            )
            rec.show_rfq_btn = (
                rec.state == 'waiting_for_approval'
                and new_product_only
            )

    @api.onchange('employee_id')
    def _onchange_employee(self):
        for rec in self:
            if rec.employee_id:
                rec.assigned_manager_id = rec.employee_id.parent_id.id
                rec.department_id = rec.employee_id.department_id.id
                rec.analytic_account_id = rec.employee_id.department_id.analytic_account_id.id
            else:
                rec.assigned_manager_id = False
                rec.department_id = False
                rec.analytic_account_id = False

    @api.depends("line_ids")
    def _compute_purchase_count(self):
        for rec in self:
            order_ids = self.env["purchase.order"].sudo().search(
                [("request_id", "=", rec.id)]
            )
            rec.purchase_count = len(order_ids)

    def action_view_purchase_order(self):
        action = self.env["ir.actions.actions"]._for_xml_id("purchase.purchase_rfq")
        order_ids = self.env["purchase.order"].sudo().search(
            [("request_id", "=", self.id)]
        )
        if len(order_ids) > 1:
            action["domain"] = [("id", "in", order_ids.ids)]
        elif order_ids:
            action["views"] = [
                (self.env.ref("purchase.purchase_order_form").id, "form")
            ]
            action["res_id"] = order_ids.id
        action["context"] = {
            "default_request_id": self.id,
            "default_origin": self.name,
        }
        return action

    @api.depends("line_ids")
    def _compute_picking_count(self):
        for rec in self:
            picking_ids = self.env["stock.picking"].sudo().search(
                [("request_id", "=", rec.id)]
            )
            rec.picking_count = len(picking_ids)

    def action_view_stock_picking(self):
        action = self.env["ir.actions.actions"]._for_xml_id(
            "stock.action_picking_tree_all"
        )
        picking_ids = self.env['stock.picking'].sudo().search([('request_id','=',self.id)])
        if len(picking_ids)>1:
            action["domain"] = [("id", "in", picking_ids.ids)]
        elif picking_ids:
            action["views"] = [(self.env.ref("stock.view_picking_form").id, "form")]
            action["res_id"] = picking_ids.id
        # remove default filters
        action["context"] = {}
        return action


    @api.depends('name', 'state', 'create_uid')
    def check_submit_button(self):
        for rec in self:
            rec.view_submit_button = rec.create_uid.id == self.env.uid
    # @api.onchange("line_ids",'analytic_account_id')
    # def _compute_analytic_account(self):
    #     for rec in self:
    #         if rec.analytic_account_id:
    #             for line in rec.line_ids:
    #                 line.analytic_distribution = rec.analytic_account_id.id

    @api.depends("line_ids")
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.mapped("line_ids"))

    def action_view_purchase_request_line(self):
        action = (
            self.env.ref("purchase_request.purchase_request_line_form_action")
            .sudo()
            .read()[0]
        )
        lines = self.mapped("line_ids")
        if len(lines) > 1:
            action["domain"] = [("id", "in", lines.ids)]
        elif lines:
            action["views"] = [
                (self.env.ref("purchase_request.purchase_request_line_form").id, "form")
            ]
            action["res_id"] = lines.ids[0]
        return action

    @api.depends("state", "line_ids.product_qty", "line_ids.cancelled")
    def _compute_to_approve_allowed(self):
        for rec in self:
            rec.to_approve_allowed = rec.state == "draft" and any(
                not line.cancelled and line.product_qty for line in rec.line_ids
            )

    def copy(self, default=None):
        default = dict(default or {})
        self.ensure_one()
        default.update({"state": "draft", "name": self._get_default_name()})
        return super(PurchaseRequest, self).copy(default)

    @api.model
    def _get_partner_id(self, request):
        user_id = request.assigned_to or self.env.user
        return user_id.partner_id.id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self._get_default_name()
        requests = super(PurchaseRequest, self).create(vals_list)
        for vals, request in zip(vals_list, requests):
            if vals.get("assigned_to"):
                partner_id = self._get_partner_id(request)
                request.message_subscribe(partner_ids=[partner_id])
        return requests

    def write(self, vals):
        res = super(PurchaseRequest, self).write(vals)
        for request in self:
            if vals.get("assigned_to"):
                partner_id = self._get_partner_id(request)
                request.message_subscribe(partner_ids=[partner_id])
        return res

    def _can_be_deleted(self):
        self.ensure_one()
        return self.state == "draft"

    def unlink(self):
        for request in self:
            if not request._can_be_deleted():
                raise UserError(
                    _("You cannot delete a purchase request which is not draft.")
                )
        return super(PurchaseRequest, self).unlink()

    def button_draft(self):
        self.mapped("line_ids").do_uncancel()
        return self.write({"state": "draft"})

    def submit_for_approval(self):
        self.to_approve_allowed_check()
        self.write({
            "recieved_date": fields.Date.context_today(self),
        })
        self.line_ids.write({'requisition_action': 'purchase_order'})
        return self.button_to_approve()


    def button_to_approve(self):
        return self.write({"state": "waiting_for_approval"})

    def button_approved(self):
        """Approve and immediately confirm (create PO/picking → in progress)."""
        return self.button_confirm()

    def button_rejected(self):
        self.mapped("line_ids").do_cancel()
        return self.write({"state": "reject"})

    def button_done(self):
        return self.write({"state": "done"})

    def check_auto_reject(self):
        """When all lines are cancelled the purchase request should be
        auto-rejected."""
        for pr in self:
            if not pr.line_ids.filtered(lambda l: l.cancelled is False):
                pr.write({"state": "reject"})

    def to_approve_allowed_check(self):
        for rec in self:
            if rec.new_product_request:
                return True
            elif not rec.to_approve_allowed:
                raise UserError(
                    _(
                        "You can't request an approval for a purchase request "
                        "which is empty. (%s)"
                    )
                    % rec.name
                )


    def button_confirm(self):
        po_obj = self.env['purchase.order'].sudo()
        picking_obj = self.env['stock.picking'].sudo()
        for rec in self:
            transfer_lines = rec.line_ids.filtered(lambda line: line.requisition_action == "internal_transfer")
            po_lines = rec.line_ids.filtered(lambda line: line.requisition_action == "purchase_order")
            partial_lines = rec.line_ids.filtered(lambda line: line.requisition_action == "partial")
            partial_vendor_list = partial_lines.mapped('vendor_id').sorted(key=lambda r: r.id)
            vendor_list = po_lines.mapped('vendor_id').sorted(key=lambda r: r.id)
            po_lines = po_lines.sorted(key=lambda r: r.vendor_id.id)
            if partial_lines:
                move_vals = []
                for line in partial_lines:
                    move_vals.append((0,0,{
                        "product_id": line.product_id.id,
                        "name": line.product_id.display_name,
                        "product_uom_qty": line.pending_qty_to_receive,
                        "product_uom": line.product_uom_id.id,
                        "purchase_request_line_id":line.id,
                        "location_id": rec.picking_type_id.default_location_src_id.id,
                        "location_dest_id": rec.picking_type_id.default_location_dest_id.id,
                        'analytic_distribution': {
                                str(line.analytic_account_id.id):100
                                }
                    }))

            if transfer_lines:
                move_vals = []
                vals = {
                    "picking_type_id": rec.picking_type_id.id,
                    "location_id": rec.picking_type_id.default_location_src_id.id,
                    "location_dest_id": rec.picking_type_id.default_location_dest_id.id,
                    "origin": rec.name,
                    "request_id":rec.id
                }
                for line in transfer_lines:
                    move_lines = (0,0,{
                        "product_id": line.product_id.id,
                        "name": line.product_id.display_name,
                        "product_uom_qty": line.product_qty,
                        "product_uom": line.product_uom_id.id,
                        "purchase_request_line_id":line.id,
                        "location_id": rec.picking_type_id.default_location_src_id.id,
                        "location_dest_id": rec.picking_type_id.default_location_dest_id.id,
                        'analytic_distribution': {
                                str(line.analytic_account_id.id):100
                                }
                    })
                    move_vals.append(move_lines)
                vals['move_ids'] = move_vals
                picking_obj.create(vals)
            if po_lines:
                for vendor in vendor_list:
                    po_vals = {
                        'partner_id': vendor.id,
                        'request_id': rec.id,
                        "origin": rec.name,
                    }
                    line_ids = []
                    po_partial_lines = partial_lines.filtered(
                        lambda line, vendor=vendor: vendor in line.vendor_id
                    )
                    for line in po_partial_lines:
                        line_ids.append((0, 0, {
                            "product_id": line.product_id.id,
                            "name": line.product_id.display_name,
                            "product_qty": line.qty_to_buy,
                            "product_uom_id": line.product_uom_id.id,
                            "request_line_id": line.id,
                            'analytic_distribution': {
                                str(line.analytic_account_id.id): 100
                            }
                        }))
                    for line in po_lines:
                        if line.vendor_id.id == vendor.id:
                            lines = (0, 0, {
                                "product_id": line.product_id.id,
                                "name": line.product_id.display_name,
                                "product_qty": line.product_qty,
                                "product_uom_id": line.product_uom_id.id,
                                "request_line_id": line.id,
                                'analytic_distribution': {
                                    str(line.analytic_account_id.id): 100
                                }
                            })
                            line_ids.append(lines)
                    if line_ids:
                        po_vals['order_line'] = line_ids
                        po_obj.create(po_vals)
            if not transfer_lines and partial_lines:
                vals = {
                    "picking_type_id": rec.picking_type_id.id,
                    "location_id": rec.picking_type_id.default_location_src_id.id,
                    "location_dest_id": rec.picking_type_id.default_location_dest_id.id,
                    "origin": rec.name,
                    "request_id":rec.id
                }
                vals['move_ids'] = move_vals
                picking_obj.create(vals)
            if not po_lines and partial_lines:
                for vendor in partial_vendor_list:
                    po_partial_lines = partial_lines.filtered(
                        lambda line, vendor=vendor: vendor in line.vendor_id
                    )
                    if po_partial_lines:
                        line_ids = []
                        for line in po_partial_lines:
                            line_ids.append((0, 0, {
                                "product_id": line.product_id.id,
                                "name": line.product_id.display_name,
                                "product_qty": line.qty_to_buy,
                                "product_uom_id": line.product_uom_id.id,
                                "request_line_id": line.id,
                                'analytic_distribution': {
                                    str(line.analytic_account_id.id): 100
                                }
                            }))
                        po_vals = {
                            'partner_id': vendor.id,
                            'request_id': rec.id,
                            "origin": rec.name,
                            # "user_id":8
                        }
                        po_vals['order_line'] = line_ids
                        po_obj.create(po_vals)
            self.write({
                'state': 'in_progress',
            })

    def create_rfq(self):
        ctx = dict(**self.env.context, default_origin_pr_id=self.id)
        return {
            'name': _('Create RFQ'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'purchase.request.quotation',
            'view_id': self.env.ref('purchase_request.purchase_request_create_rfq_form').id,
            'target': 'new',
            'context': ctx,
        }
