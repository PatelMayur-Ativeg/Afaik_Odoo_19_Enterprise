# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MaterialPurchaseRequisition(models.Model):
    _name = 'material.purchase.requisition'
    _description = 'Purchase Requisition'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='Number',
        index=True,
        readonly=True,
        copy=False,
        default='New',
    )
    state = fields.Selection([
        ('draft', 'New'),
        ('confirmed', 'Confirmed'),
        # Disabled department approval / reject — uncomment to restore:
        # ('dept_confirm', 'Waiting Department Approval'),
        # ('approve', 'Approved'),
        ('stock', 'Purchase Order Created'),
        ('receive', 'Received'),
        ('cancel', 'Cancelled'),
        # ('reject', 'Rejected'),
    ],
        default='draft',
        tracking=True,
        copy=False,
    )
    request_date = fields.Date(
        string='Requisition Date',
        default=fields.Date.context_today,
        required=True,
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        required=True,
        copy=True,
        tracking=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        default=lambda self: self.env.user.employee_id,
        required=True,
        copy=True,
        tracking=True,
    )
    approve_manager_id = fields.Many2one(
        'hr.employee',
        string='Department Manager',
        readonly=True,
        copy=False,
    )
    reject_manager_id = fields.Many2one(
        'hr.employee',
        string='Department Manager Reject',
        readonly=True,
        copy=False,
    )
    approve_employee_id = fields.Many2one(
        'hr.employee',
        string='Approved by',
        readonly=True,
        copy=False,
    )
    reject_employee_id = fields.Many2one(
        'hr.employee',
        string='Rejected by',
        readonly=True,
        copy=False,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
        copy=True,
    )
    location_id = fields.Many2one(
        'stock.location',
        string='Source Location',
        copy=True,
    )
    requisition_line_ids = fields.One2many(
        'material.purchase.requisition.line',
        'requisition_id',
        string='Purchase Requisitions Line',
        copy=True,
    )
    date_end = fields.Date(
        string='Requisition Deadline',
        help='Last date for the product to be needed',
        copy=True,
    )
    date_done = fields.Date(
        string='Date Done',
        readonly=True,
        copy=False,
        help='Date of Completion of Purchase Requisition',
    )
    managerapp_date = fields.Date(
        string='Department Approval Date',
        readonly=True,
        copy=False,
    )
    manareject_date = fields.Date(
        string='Department Manager Reject Date',
        readonly=True,
        copy=False,
    )
    userreject_date = fields.Date(
        string='Rejected Date',
        readonly=True,
        copy=False,
    )
    userrapp_date = fields.Date(
        string='Approved Date',
        readonly=True,
        copy=False,
    )
    receive_date = fields.Date(
        string='Received Date',
        readonly=True,
        copy=False,
    )
    reason = fields.Text(
        string='Reason for Requisitions',
        required=False,
        copy=True,
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        copy=True,
    )
    dest_location_id = fields.Many2one(
        'stock.location',
        string='Destination Location',
        required=False,
        copy=True,
    )
    delivery_picking_id = fields.Many2one(
        'stock.picking',
        string='Internal Picking',
        readonly=True,
        copy=False,
    )
    requisiton_responsible_id = fields.Many2one(
        'hr.employee',
        string='Requisition Responsible',
        copy=True,
    )
    employee_confirm_id = fields.Many2one(
        'hr.employee',
        string='Confirmed by',
        readonly=True,
        copy=False,
    )
    confirm_date = fields.Date(
        string='Confirmed Date',
        readonly=True,
        copy=False,
    )
    purchase_order_ids = fields.One2many(
        'purchase.order',
        'custom_requisition_id',
        string='Purchase Orders',
        copy=False,
    )
    purchase_order_count = fields.Integer(
        string='Purchase Order Count',
        compute='_compute_purchase_order_count',
    )
    custom_picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='Picking Type',
        copy=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('purchase.requisition.seq') or _('New')
        return super().create(vals_list)

    def init(self):
        # Dropped Waiting IR Approval: move leftover records to Approved.
        # self.env.cr.execute("""
        #     UPDATE material_purchase_requisition
        #        SET state = 'approve'
        #      WHERE state = 'ir_approve'
        # """)
        # Dropped department approval / reject: leftover records go to draft / cancel.
        self.env.cr.execute("""
            UPDATE material_purchase_requisition
               SET state = 'draft'
             WHERE state IN ('ir_approve', 'dept_confirm', 'approve')
        """)
        self.env.cr.execute("""
            UPDATE material_purchase_requisition
               SET state = 'cancel'
             WHERE state = 'reject'
        """)

    def unlink(self):
        if self.filtered(lambda rec: rec.state != 'draft'):
            raise UserError(_('You can only delete draft purchase requisitions.'))
        return super().unlink()

    def _get_linked_purchase_orders(self):
        self.ensure_one()
        orders = self.purchase_order_ids
        return orders | orders.mapped('alternative_po_ids')

    def _sync_linked_purchase_orders(self):
        self.ensure_one()
        extras = self.purchase_order_ids.mapped('alternative_po_ids') - self.purchase_order_ids
        if extras:
            extras.write({
                'custom_requisition_id': self.id,
                'employee_id': self.employee_id.id,
                'department_id': self.department_id.id,
            })
            extras.filtered(lambda po: not po.origin).write({'origin': self.name})
        return self._get_linked_purchase_orders()

    @api.depends('purchase_order_ids', 'purchase_order_ids.alternative_po_ids')
    def _compute_purchase_order_count(self):
        for rec in self:
            rec.purchase_order_count = len(rec._get_linked_purchase_orders())

    def action_view_purchase_order(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('purchase.purchase_rfq')
        orders = self._sync_linked_purchase_orders()
        if len(orders) > 1:
            action['domain'] = [('id', 'in', orders.ids)]
        elif orders:
            action['views'] = [(self.env.ref('purchase.purchase_order_form').id, 'form')]
            action['res_id'] = orders.id
        else:
            action['domain'] = [('id', '=', False)]
        action['context'] = {
            'default_custom_requisition_id': self.id,
            'default_origin': self.name,
            'default_employee_id': self.employee_id.id,
            'default_department_id': self.department_id.id,
        }
        return action

    def _get_employee(self):
        return self.env.user.employee_id

    def _check_requisition_lines(self):
        self.ensure_one()
        if not self.requisition_line_ids:
            raise UserError(_('Please add at least one requisition line.'))

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            self.department_id = self.employee_id.department_id
            self.requisiton_responsible_id = self.employee_id.parent_id
        else:
            self.department_id = False
            self.requisiton_responsible_id = False

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if not self.custom_picking_type_id and self.company_id:
            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'internal'),
                ('warehouse_id.company_id', '=', self.company_id.id),
            ], limit=1)
            self.custom_picking_type_id = picking_type

    # Disabled department approval / reject — uncomment to restore:
    def requisition_confirm(self):
        for rec in self:
            rec._check_requisition_lines()
            rec.write({
                'state': 'confirmed',
                'employee_confirm_id': rec._get_employee().id,
                'confirm_date': fields.Date.context_today(rec),
            })
        return True

    # def manager_approve(self):
    #     for rec in self:
    #         employee = rec._get_employee()
    #         rec.write({
    #             'state': 'approve',
    #             'approve_manager_id': employee.id,
    #             'managerapp_date': fields.Date.context_today(rec),
    #             'approve_employee_id': employee.id,
    #             'userrapp_date': fields.Date.context_today(rec),
    #         })
    #     return True
    #
    # def requisition_reject(self):
    #     for rec in self:
    #         employee = rec._get_employee()
    #         vals = {'state': 'reject'}
    #         if rec.state == 'dept_confirm':
    #             vals.update({
    #                 'reject_manager_id': employee.id,
    #                 'manareject_date': fields.Date.context_today(rec),
    #             })
    #         else:
    #             vals.update({
    #                 'reject_employee_id': employee.id,
    #                 'userreject_date': fields.Date.context_today(rec),
    #             })
    #         rec.write(vals)
    #     return True

    def action_cancel(self):
        self.write({'state': 'cancel'})
        return True

    def reset_draft(self):
        self.write({
            'state': 'draft',
            'employee_confirm_id': False,
            'confirm_date': False,
            'approve_manager_id': False,
            'managerapp_date': False,
            'approve_employee_id': False,
            'userrapp_date': False,
            'reject_manager_id': False,
            'manareject_date': False,
            'reject_employee_id': False,
            'userreject_date': False,
            'receive_date': False,
            'date_done': False,
        })
        return True

    def action_received(self):
        today = fields.Date.context_today(self)
        self.write({
            'state': 'receive',
            'receive_date': today,
            'date_done': today,
        })
        return True

    def _get_dummy_vendor(self):
        return self.env.ref('purchase_extension.partner_aafaq_dummy_vendor', raise_if_not_found=False)

    def _get_line_vendors(self, line):
        return line.partner_id or self._get_dummy_vendor()

    def _prepare_po_line_vals(self, line, order):
        self.ensure_one()
        analytic_distribution = {}
        if line.account_analytic_id:
            analytic_distribution = {str(line.account_analytic_id.id): 100}
        return {
            'order_id': order.id,
            'product_id': line.product_id.id,
            'name': line.description or line.product_id.display_name,
            'product_qty': line.qty,
            'product_uom_id': line.uom.id,
            'date_planned': self.date_end or fields.Datetime.now(),
            'price_unit': line.cost or line.product_id.standard_price,
            'analytic_account_id': line.account_analytic_id.id,
            'analytic_distribution': analytic_distribution,
        }

    def _create_purchase_orders(self):
        self.ensure_one()
        purchase_lines = self.requisition_line_ids.filtered(lambda line: line.requisition_type == 'purchase')
        if not purchase_lines:
            return self.env['purchase.order']

        po_by_vendor = {}
        po_line_obj = self.env['purchase.order.line']
        for line in purchase_lines:
            vendors = self._get_line_vendors(line)
            if not vendors:
                vendors = self._get_dummy_vendor()
            if not vendors:
                raise UserError(_(
                    'Aafaq Dummy Vendor contact is missing. Please upgrade the Purchase Requisition Custom module.'
                ))
            for vendor in vendors:
                order = po_by_vendor.get(vendor)
                if not order:
                    order = self.env['purchase.order'].create({
                        'partner_id': vendor.id,
                        'company_id': self.company_id.id,
                        'origin': self.name,
                        'custom_requisition_id': self.id,
                        'date_order': fields.Datetime.now(),
                    })
                    po_by_vendor[vendor] = order
                po_line_obj.create(self._prepare_po_line_vals(line, order))
        return self.env['purchase.order'].concat(*po_by_vendor.values()) if po_by_vendor else self.env['purchase.order']

    def _create_internal_picking(self):
        self.ensure_one()
        internal_lines = self.requisition_line_ids.filtered(lambda line: line.requisition_type == 'internal')
        if not internal_lines:
            return self.env['stock.picking']
        if not self.location_id:
            raise UserError(_('Please select a Source Location under Picking Details.'))
        if not self.dest_location_id:
            raise UserError(_('Please select a Destination Location under Picking Details.'))
        if not self.custom_picking_type_id:
            raise UserError(_('Please select a Picking Type under Picking Details.'))

        move_vals = []
        for line in internal_lines:
            analytic_distribution = {}
            if line.account_analytic_id:
                analytic_distribution = {str(line.account_analytic_id.id): 100}
            move_vals.append((0, 0, {
                'name': line.description or line.product_id.display_name,
                'product_id': line.product_id.id,
                'product_uom_qty': line.qty,
                'product_uom': line.uom.id,
                'location_id': self.location_id.id,
                'location_dest_id': self.dest_location_id.id,
                'company_id': self.company_id.id,
                'analytic_distribution': analytic_distribution,
            }))
        picking_vals = {
            'picking_type_id': self.custom_picking_type_id.id,
            'location_id': self.location_id.id,
            'location_dest_id': self.dest_location_id.id,
            'origin': self.name,
            'company_id': self.company_id.id,
            'move_ids': move_vals,
        }
        if self.employee_id.work_contact_id:
            picking_vals['partner_id'] = self.employee_id.work_contact_id.id
        picking = self.env['stock.picking'].create(picking_vals)
        self.delivery_picking_id = picking.id
        return picking

    def request_stock(self):
        for rec in self:
            rec._check_requisition_lines()
            if not rec.delivery_picking_id:
                rec._create_internal_picking()
            if not rec.purchase_order_ids:
                rec._create_purchase_orders()
            rec.state = 'stock'
        return True

    def action_view_picking(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('stock.action_picking_tree_all')
        picking = self.delivery_picking_id
        if picking:
            action['views'] = [(self.env.ref('stock.view_picking_form').id, 'form')]
            action['res_id'] = picking.id
        else:
            action['domain'] = [('id', '=', False)]
        action['context'] = {}
        return action

