from odoo import api, fields, tools, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
import json
import logging
from lxml import etree

_logger = logging.getLogger(__name__)

# from lxml import etree
import simplejson


class PurchaseRequest(models.Model):
    _inherit = 'purchase.request'

    approval_level_id = fields.Many2one(
        'sh.purchase.approval.config', string="Approval Level", compute="compute_approval_level")
    state = fields.Selection(
        selection_add=[('waiting_for_approval', 'Waiting for Approval'), ('done',)])
    level = fields.Integer(string="Next Approval Level", readonly=True)
    user_ids = fields.Many2many('res.users', string="Users")
    # , readonly=True
    group_ids = fields.Many2many('res.groups', string="Groups", readonly=True)
    is_boolean = fields.Boolean(
        string="Boolean", compute="compute_is_boolean", search='_search_is_boolean',store=True)
    approval_info_line = fields.One2many(
        'sh.approval.info', 'purchase_request_id', readonly=True)
    rejection_date = fields.Datetime(string="Reject Date", readonly=True)
    reject_by = fields.Many2one('res.users', string="Reject By", readonly=True)
    reject_reason = fields.Char(string="Reject Reason", readonly=True)
    hide_admin_fields = fields.Boolean(default=True, compute="_compute_view_po_fields")
    manager_approval = fields.Boolean(compute="_compute_approval_access")
    create_rfq_access = fields.Boolean(compute="_compute_create_rfq_access")
    create_rfq_access_extra = fields.Boolean(compute="_compute_create_rfq_access_extra")
    rfq_added = fields.Boolean("RFQ Created")

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        result = super(PurchaseRequest, self).get_view(view_id, view_type, **options)
        doc = etree.XML(result['arch'])
        if self.env.user.has_group('purchase_request.group_purchase_request_gnadmin') or self.env.user.has_group(
                'purchase_request.group_purchase_request_itadmin'):
            if view_type == 'form':
                if doc.xpath("//field"):
                    for node in doc.xpath("//field"):
                        if node.get('name') in ['user_ids', 'analytic_account_id']:
                            modifiers = simplejson.loads(node.get("modifiers", '{}'))
                            modifiers.update({'readonly': False})
                            node.set("modifiers", simplejson.dumps(modifiers))
        result['arch'] = etree.tostring(doc)
        return result

    @api.depends("state")
    def _compute_create_rfq_access(self):
        for rec in self:
            approval_lines = rec.approval_level_id.purchase_approval_line.filtered(
                lambda x: x.create_rfq_access).sorted(key=lambda r: r.id, reverse=True)
            if approval_lines:
                approval_lines = max(approval_lines)
                show_level = approval_lines.level
                if rec.level == show_level and self.env.user.has_group(
                        'purchase_request.group_purchase_request_gnadmin') or self.env.user.has_group(
                    'purchase_request.group_purchase_request_itadmin'):
                    rec.create_rfq_access = True
                else:
                    rec.create_rfq_access = False
            else:
                rec.create_rfq_access = False

    @api.depends("state")
    def _compute_create_rfq_access_extra(self):
        for rec in self:
            if self.env.user.has_group('purchase_request.group_purchase_request_gnadmin') or self.env.user.has_group(
                    'purchase_request.group_purchase_request_itadmin'):
                rec.create_rfq_access_extra = True
            else:
                rec.create_rfq_access_extra = False

    @api.depends("state")
    def _compute_is_editable(self):
        res = super(PurchaseRequest, self)._compute_is_editable()
        for rec in self:
            approval_lines = rec.approval_level_id.purchase_approval_line.filtered(
                lambda x: x.is_admin_approval).sorted(key=lambda r: r.id, reverse=True)
            if approval_lines:
                approval_lines = max(approval_lines)
                restrict_level = approval_lines.level
                if rec.level > restrict_level or rec.state not in ("draft", "waiting_for_approval"):
                    rec.is_editable = False
                else:
                    rec.is_editable = True
            else:
                rec.is_editable = True

    def update_analytic_vals(self):
        for rec in self:
            if rec.state == 'waiting_for_approval':
                for line in rec.line_ids:
                    line.analytic_account_id = rec.analytic_account_id.id
        return True

    @api.depends('approval_level_id', 'state')
    def _compute_approval_access(self):
        for rec in self:
            if rec.state == 'waiting_for_review':
                if rec.approval_level_id.primary_approval == 'line_manager':
                    if self.env.user.employee_id == rec.assigned_manager_id:
                        rec.manager_approval = True
                    else:
                        rec.manager_approval = False
                else:
                    if self.env.user.employee_id == rec.employee_id:
                        rec.manager_approval = True
                    else:
                        rec.manager_approval = False
            else:
                rec.manager_approval = False

    @api.depends('state', 'level')
    def _compute_view_po_fields(self):
        for rec in self:
            if rec.state in ('waiting_for_approval', 'in_progress'):
                user_access = False
                approval_id = rec.approval_level_id
                approval_lines = approval_id.purchase_approval_line.filtered(
                    lambda x: x.is_admin_approval and x.level == rec.level)
                if approval_lines:
                    user_access = True
                if user_access and (
                        self.env.user.has_group('purchase_request.group_purchase_request_itadmin') or self.env.user.has_group(
                    'purchase_request.group_purchase_request_gnadmin')):
                    rec.hide_admin_fields = False
                else:
                    rec.hide_admin_fields = True
            else:
                rec.hide_admin_fields = True

    def compute_is_boolean(self):
        if self.env.user.id in self.user_ids.ids or any(
                item in self.env.user.groups_id.ids for item in self.group_ids.ids):
            self.is_boolean = True
        else:
            self.is_boolean = False

    def _search_is_boolean(self, operator, value):
        results = []

        if value:
            po_ids = self.env['purchase.request'].search([])
            if po_ids:
                for po in po_ids:
                    if self.env.user.id in po.user_ids.ids or any(
                            item in self.env.user.groups_id.ids for item in po.group_ids.ids):
                        results.append(po.id)
        return [('id', 'in', results)]

    def action_create_rfq(self):
        po_obj = self.env['purchase.order'].sudo()
        for rec in self:
            po_lines = rec.line_ids.filtered(lambda line: line.requisition_action == "purchase_order")
            vendor_list = po_lines.mapped('vendor_id').sorted(key=lambda r: r.id)

            po_lines = po_lines.sorted(key=lambda r: r.vendor_id.ids)
            if po_lines:
                for vendor in vendor_list:
                    po_vals = {
                        'partner_id': vendor.id,
                        'state': 'draft',
                        'request_id': rec.id,
                        "origin": rec.name,
                        "user_id": rec.approval_level_id.buyer.id if rec.approval_level_id.buyer else False
                    }
                    line_ids = []
                    for line in po_lines:
                        if vendor.id in line.vendor_id.ids:
                            line_vals = {
                                "product_id": line.product_id.id,
                                "name": line.product_id.display_name,
                                "product_qty": line.product_qty,
                                "product_uom_id": line.product_uom_id.id,
                                "request_line_id": line.id,
                            }
                            if line.analytic_account_id:
                                line_vals['analytic_distribution'] = {str(line.analytic_account_id.id): 100}
                            line_ids.append((0, 0, line_vals))
                    po_vals['order_line'] = line_ids
                    rfq = po_obj.create(po_vals)
                    if rfq:
                        rec.rfq_added = True

    def action_create_rfq_extra(self):
        po_obj = self.env['purchase.order'].sudo()
        for rec in self:
            po_lines = rec.line_ids.filtered(lambda line: line.requisition_action == "purchase_order")
            po_lines = po_lines.sorted(key=lambda r: r.vendor_id.ids)
            if po_lines:
                po_vals = {
                    'partner_id': self.env.user.company_id.id,
                    'request_id': rec.id,
                    "origin": rec.name,
                    "user_id": rec.approval_level_id.buyer.id if rec.approval_level_id.buyer else False
                }
                line_ids = []
                for line in po_lines:
                    line_vals = {
                        "product_id": line.product_id.id,
                        "name": line.product_id.display_name,
                        "product_qty": line.product_qty,
                        "product_uom_id": line.product_uom_id.id,
                        "request_line_id": line.id,
                    }
                    if line.analytic_account_id:
                        line_vals['analytic_distribution'] = {str(line.analytic_account_id.id): 100}
                    line_ids.append((0, 0, line_vals))
                    po_vals['order_line'] = line_ids
                rfq = po_obj.create(po_vals)

    def button_confirm(self):
        po_obj = self.env['purchase.order'].sudo()
        picking_obj = self.env['stock.picking'].sudo()
        for rec in self:
            transfer_lines = rec.line_ids.filtered(lambda line: line.requisition_action == "internal_transfer")
            po_lines = rec.line_ids.filtered(lambda line: line.requisition_action == "purchase_order")
            partial_lines = rec.line_ids.filtered(lambda line: line.requisition_action == "partial")
            partial_vendor_list = partial_lines.mapped('vendor_id').sorted(key=lambda r: r.id)
            vendor_list = po_lines.mapped('vendor_id').sorted(key=lambda r: r.id)

            po_lines = po_lines.sorted(key=lambda r: r.vendor_id.ids)

            if partial_lines:
                move_vals = []
                for line in partial_lines:
                    move_line_vals = {
                        "product_id": line.product_id.id,
                        "name": line.product_id.display_name,
                        "product_uom_qty": line.pending_qty_to_receive,
                        "product_uom_id": line.product_uom_id.id,
                        "purchase_request_line_id": line.id,
                        "location_id": rec.src_location_id.id if rec.src_location_id else rec.picking_type_id.default_location_src_id.id,
                        "location_dest_id": rec.dest_location_id.id if rec.dest_location_id else rec.picking_type_id.default_location_dest_id.id,
                    }
                    if line.analytic_account_id:
                        move_line_vals['analytic_distribution'] = {str(line.analytic_account_id.id): 100}
                    move_vals.append((0, 0, move_line_vals))

            if transfer_lines:
                move_vals = []
                vals = {
                    "picking_type_id": rec.picking_type_id.id,
                    "location_id": rec.src_location_id.id if rec.src_location_id else rec.picking_type_id.default_location_src_id.id,
                    "location_dest_id": rec.dest_location_id.id if rec.dest_location_id else rec.picking_type_id.default_location_dest_id.id,
                    "origin": rec.name,
                    "request_id": rec.id
                }
                for line in transfer_lines:
                    move_line_vals = {
                        "product_id": line.product_id.id,
                        "name": line.product_id.display_name,
                        "product_uom_qty": line.product_qty,
                        "product_uom_id": line.product_uom_id.id,
                        "purchase_request_line_id": line.id,
                        "location_id": rec.src_location_id.id if rec.src_location_id else rec.picking_type_id.default_location_src_id.id,
                        "location_dest_id": rec.dest_location_id.id if rec.dest_location_id else rec.picking_type_id.default_location_dest_id.id,
                    }
                    if line.analytic_account_id:
                        move_line_vals['analytic_distribution'] = {str(line.analytic_account_id.id): 100}
                    move_vals.append((0, 0, move_line_vals))
                vals['move_ids_without_package'] = move_vals
                picking_obj.create(vals)
            if po_lines:
                for vendor in vendor_list:
                    for pl in partial_lines:
                        if len(pl.vendor_id) > 1:
                            for v_id in pl.vendor_id:
                                if v_id == vendor:
                                    po_partial_lines = pl
                        else:
                            po_partial_lines = partial_lines.filtered(lambda line: line.vendor_id == vendor)
                    po_partial_lines = partial_lines.filtered(lambda line: line.vendor_id == vendor.id)
                    if po_partial_lines:
                        for line in po_partial_lines:
                            partial_line_vals = {
                                "product_id": line.product_id.id,
                                "name": line.product_id.display_name,
                                "product_qty": line.qty_to_buy,
                                "product_uom_id": line.product_uom_id.id,
                                "request_line_id": line.id,
                            }
                            if line.analytic_account_id:
                                partial_line_vals['analytic_distribution'] = {str(line.analytic_account_id.id): 100}
                            line_ids.append((0, 0, partial_line_vals))
                    po_vals = {
                        'partner_id': vendor.id,
                        'request_id': rec.id,
                        "origin": rec.name,
                        "user_id": rec.approval_level_id.buyer.id if rec.approval_level_id.buyer else False
                    }
                    line_ids = []
                    for line in po_lines:
                        if vendor.id in line.vendor_id.ids:
                            po_line_vals = {
                                "product_id": line.product_id.id,
                                "name": line.product_id.display_name,
                                "product_qty": line.product_qty,
                                "product_uom_id": line.product_uom_id.id,
                                "request_line_id": line.id,
                            }
                            if line.analytic_account_id:
                                po_line_vals['analytic_distribution'] = {str(line.analytic_account_id.id): 100}
                            line_ids.append((0, 0, po_line_vals))
                    po_vals['order_line'] = line_ids
                    if not rec.rfq_added:
                        rfq = po_obj.create(po_vals)
                        rfq.button_confirm()
            if not transfer_lines and partial_lines:
                vals = {
                    "picking_type_id": rec.picking_type_id.id,
                    "location_id": rec.src_location_id.id if rec.src_location_id else rec.picking_type_id.default_location_src_id.id,
                    "location_dest_id": rec.dest_location_id.id if rec.dest_location_id else rec.picking_type_id.default_location_dest_id.id,
                    "origin": rec.name,
                    "request_id": rec.id
                }
                vals['move_ids_without_package'] = move_vals
                picking_obj.create(vals)
            if not po_lines and partial_lines:
                for vendor in partial_vendor_list:
                    for pl in partial_lines:
                        if len(pl.vendor_id) > 1:
                            for v_id in pl.vendor_id:
                                if v_id == vendor:
                                    po_partial_lines = pl
                        else:
                            po_partial_lines = partial_lines.filtered(lambda line: line.vendor_id == vendor)

                    if po_partial_lines:
                        line_ids = []
                        for line in po_partial_lines:
                            partial_line_vals = {
                                "product_id": line.product_id.id,
                                "name": line.product_id.display_name,
                                "product_qty": line.qty_to_buy,
                                "product_uom_id": line.product_uom_id.id,
                                "request_line_id": line.id,
                            }
                            if line.analytic_account_id:
                                partial_line_vals['analytic_distribution'] = {str(line.analytic_account_id.id): 100}
                            line_ids.append((0, 0, partial_line_vals))
                        po_vals = {
                            'partner_id': vendor.id,
                            'request_id': rec.id,
                            "origin": rec.name,
                            "user_id": rec.approval_level_id.buyer.id if rec.approval_level_id.buyer else False
                        }
                        po_vals['order_line'] = line_ids
                        po = po_obj.create(po_vals)
                        po.button_confirm()

            self.write({
                'state': 'in_progress',
            })
            # po_ids = self.env['purchase.order'].search([('request_id','=',self.id)])
            # if po_ids:
            #     for po in po_ids:
            #         po.button_done()

    def button_to_approve(self):
        template_id = self.env.ref(
            "sh_purchase_dynamic_approval.email_template_for_approve_purchase_request")

        if self.approval_level_id.purchase_approval_line:
            self.write({
                'state': 'waiting_for_approval'
            })
            lines = self.approval_level_id.purchase_approval_line

            self.approval_info_line = False
            for line in lines:
                dictt = []
                if line.approve_by == 'group':
                    dictt.append((0, 0, {
                        'level': line.level,
                        'user_ids': False,
                        'group_ids': [(6, 0, line.group_ids.ids)],
                        'label_type': line.label_type,
                        'purchase_approval_line_id': line.id
                    }))

                if line.approve_by == 'user':
                    dictt.append((0, 0, {
                        'level': line.level,
                        'user_ids': [(6, 0, line.user_ids.ids)],
                        'group_ids': False,
                        'label_type': line.label_type,
                        'purchase_approval_line_id': line.id
                    }))

                self.update({
                    'approval_info_line': dictt
                })

            if lines[0].approve_by == 'group':
                self.write({
                    'level': lines[0].level,
                    'group_ids': [(6, 0, lines[0].group_ids.ids)],
                    'user_ids': False,
                    'purchase_approval_line_id': line[0].id
                })

                users = self.env['res.users'].search(
                    [('groups_id', 'in', lines[0].group_ids.ids)])

                if template_id and users:
                    user_email = self.env.user.email
                    # 'email_from': self.env.user.email
                    for user in users:
                        template_id.sudo().send_mail(self.id, force_send=True, email_values={
                            'email_from': user_email, 'email_to': user.email})

                if users:
                    for user in users:
                        self.env['bus.bus']._sendone(user.partner_id, 'simple_notification', {
                            'title': _('Notitification'),
                            'message': 'You have approval notification for PR %s' % (self.name),
                            'sticky': True,
                            'warning': True,
                        })

            if lines[0].approve_by == 'user':
                self.write({
                    'level': lines[0].level,
                    'user_ids': [(6, 0, lines[0].user_ids.ids)],
                    'group_ids': False,
                })

                if template_id and lines[0].user_ids:
                    for user in lines[0].user_ids:
                        user_email = self.env.user.email
                        # 'email_from': self.env.user.email
                        template_id.sudo().send_mail(self.id, force_send=True, email_values={
                            'email_from': user_email, 'email_to': user.email})

                if lines[0].user_ids:
                    for user in lines[0].user_ids:
                        self.env['bus.bus']._sendone(user.partner_id, 'simple_notification', {
                            'title': _('Notitification'),
                            'message': 'You have approval notification for PR %s' % (self.name),
                            'sticky': True,
                            'warning': True,
                        })

        else:
            self.button_confirm()

    @api.depends('pr_category_id')
    def compute_approval_level(self):
        for rec in self:
            if rec.company_id.approval_based_on == 'pr_category' and rec.pr_category_id:
                purchase_approvals = self.env['sh.purchase.approval.config'].search(
                    [
                        ('pr_category_ids', 'in', [rec.pr_category_id.id]),
                        ('company_ids', 'in', [self.env.company.id]),
                    ],
                    limit=1,
                )
                rec.approval_level_id = purchase_approvals.id if purchase_approvals else False
            else:
                rec.approval_level_id = False

    def action_approve_order(self):

        template_id = self.env.ref(
            "sh_purchase_dynamic_approval.email_template_for_approve_purchase_request")
        picking_obj = self.env['stock.picking'].sudo()
        info = self.approval_info_line.filtered(
            lambda x: x.level == self.level)
        picking_only = False
        if info:
            info.status = True
            info.approval_date = datetime.now()
            info.approved_by = self.env.user

        line_id = self.env['sh.purchase.approval.line'].search(
            [('purchase_approval_config_id', '=', self.approval_level_id.id), ('level', '=', self.level)])

        next_line = self.env['sh.purchase.approval.line'].search(
            [('purchase_approval_config_id', '=', self.approval_level_id.id), ('id', '>', line_id.id)], limit=1)
        approval_id = self.approval_level_id

        approval_level = approval_id.purchase_approval_line.filtered(
            lambda x: x.is_admin_approval and x.level == self.level)
        if approval_level and not self.new_product_request:
            approve_lines = any(record.requisition_action == False for record in self.line_ids)
            if approve_lines:
                raise ValidationError("Please pick Requisition Action before approving !")
            approval_lines = any(record.requisition_action != 'internal_transfer' for record in self.line_ids)
            if not approval_lines:
                picking_only = True
                transfer_lines = self.line_ids.filtered(lambda line: line.requisition_action == "internal_transfer")
                if transfer_lines:
                    move_vals = []
                    vals = {
                        "picking_type_id": self.picking_type_id.id,
                        "location_id": self.picking_type_id.default_location_src_id.id,
                        "location_dest_id": self.picking_type_id.default_location_dest_id.id,
                        "origin": self.name,
                        "request_id": self.id
                    }
                    for line in transfer_lines:
                        move_line_vals = {
                            "product_id": line.product_id.id,
                            "name": line.product_id.display_name,
                            "product_uom_qty": line.product_qty,
                            "product_uom_id": line.product_uom_id.id,
                            "purchase_request_line_id": line.id,
                            "location_id": self.picking_type_id.default_location_src_id.id,
                            "location_dest_id": self.picking_type_id.default_location_dest_id.id,
                        }
                        if line.analytic_account_id:
                            move_line_vals['analytic_distribution'] = {str(line.analytic_account_id.id): 100}
                        move_vals.append((0, 0, move_line_vals))
                    vals['move_ids_without_package'] = move_vals
                    picking_obj.create(vals)
                self.write({
                    'state': 'in_progress',
                })
        if next_line and not picking_only:
            if next_line.approve_by == 'group':
                self.write({
                    'level': next_line.level,
                    'group_ids': [(6, 0, next_line.group_ids.ids)],
                    'user_ids': False
                })
                users = self.env['res.users'].search(
                    [('groups_id', 'in', next_line.group_ids.ids)])

                if template_id and users and self.approval_level_id.is_boolean:
                    for user in users:
                        user_email = self.env.user.email
                        # 'email_from': self.env.user.email
                        template_id.sudo().send_mail(self.id, force_send=True, email_values={
                            'email_from': user_email, 'email_to': user.email})

                if template_id and users and not self.approval_level_id.is_boolean:
                    for user in users:
                        user_email = self.env.user.email
                        # 'email_from': self.env.user.email
                        template_id.sudo().send_mail(self.id, force_send=True, email_values={
                            'email_from': user_email, 'email_to': user.email})

                if users:
                    for user in users:
                        self.env['bus.bus']._sendone(user.partner_id, 'simple_notification', {
                            'title': _('Notitification'),
                            'message': 'You have approval notification for PR %s' % (self.name),
                            'sticky': True,
                            'warning': True,
                        })

            if next_line.approve_by == 'user':
                self.write({
                    'level': next_line.level,
                    'user_ids': [(6, 0, next_line.user_ids.ids)],
                    'group_ids': False
                })
                if template_id and next_line.user_ids and self.approval_level_id.is_boolean:
                    for user in next_line.user_ids:
                        user_email = self.env.user.email
                        # 'email_from': self.env.user.email
                        template_id.sudo().send_mail(self.id, force_send=True, email_values={
                            'email_from': user_email, 'email_to': user.email})

                if template_id and next_line.user_ids and not self.approval_level_id.is_boolean:
                    for user in next_line.user_ids:
                        user_email = self.env.user.email
                        # 'email_from': self.env.user.email
                        template_id.sudo().send_mail(self.id, force_send=True, email_values={
                            'email_from': user_email, 'email_to': user.email})

                if next_line.user_ids:
                    for user in next_line.user_ids:
                        self.env['bus.bus']._sendone(user.partner_id, 'simple_notification', {
                            'title': _('Notitification'),
                            'message': 'You have approval notification for PR %s' % (self.name),
                            'sticky': True,
                            'warning': True,
                        })

        else:
            template_id = self.env.ref(
                "sh_purchase_dynamic_approval.email_template_for_confirm_purchase_request")

            if template_id:
                user_email = self.env.user.email
                # 'email_from': self.env.user.email
                template_id.sudo().send_mail(self.id, force_send=True, email_values={
                    'email_from': user_email, 'email_to': self.employee_id.user_id.email})

            if self.employee_id.user_id:
                self.env['bus.bus']._sendone(self.employee_id.user_id.partner_id, 'simple_notification', {
                    'title': _('Notitification'),
                    'message': 'Dear User!! your PR %s is confirmed' % (self.name),
                    'sticky': True,
                    'warning': True,
                })

            if not picking_only:
                self.write({
                    'level': False,
                    'group_ids': False,
                    'user_ids': False,
                    'state': 'in_progress',
                })
                self.button_confirm()

    def action_reset_to_draft(self):
        self.write({
            'state': 'draft'
        })
