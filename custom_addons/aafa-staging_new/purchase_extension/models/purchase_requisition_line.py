# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MaterialPurchaseRequisitionLine(models.Model):
    _name = "material.purchase.requisition.line"
    _description = 'Material Purchase Requisition Lines'

    requisition_id = fields.Many2one(
        'material.purchase.requisition',
        string='Requisitions',
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
    )
    description = fields.Char(
        string='Description',
        required=True,
    )
    qty = fields.Float(
        string='Quantity',
        default=1,
        required=True,
    )
    uom = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        required=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        compute='_compute_partner_id',
        store=True,
        readonly=True,
    )
    account_analytic_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        related='requisition_id.analytic_account_id',
        store=True,
        readonly=False,
    )
    requisition_type = fields.Selection(
        selection=[
            ('internal', 'Internal Picking'),
            ('purchase', 'Purchase Order'),
        ],
        string='Requisition Action',
        default='purchase',
        required=True,
    )
    cost = fields.Float("Cost")

    def _get_dummy_vendor(self):
        return self.env.ref('purchase_extension.partner_aafaq_dummy_vendor', raise_if_not_found=False)

    @api.depends('product_id', 'product_id.seller_ids', 'product_id.seller_ids.partner_id')
    def _compute_partner_id(self):
        dummy = self._get_dummy_vendor()
        for line in self:
            if not line.product_id:
                line.partner_id = False
                continue
            vendor = line.product_id.seller_ids[:1].partner_id
            line.partner_id = vendor or dummy

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.description = self.product_id.display_name
            self.uom = self.product_id.uom_id
            self.cost = self.product_id.standard_price
        else:
            self.description = False
            self.uom = False
            self.cost = 0.0

    @api.constrains('qty')
    def _check_qty(self):
        for line in self:
            if line.qty <= 0:
                raise UserError(_('Quantity must be greater than zero for product %s.') % (
                    line.product_id.display_name or ''
                ))

