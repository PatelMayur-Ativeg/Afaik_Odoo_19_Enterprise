from odoo import fields, models, _
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    state = fields.Selection(
        selection_add=[
            ('under_approval', 'Under Approval'),
            ('approved', 'Approved'),
            ('to approve',),
        ],
        ondelete={
            'under_approval': 'set default',
            'approved': 'set default',
        },
    )
    dept_review_status = fields.Selection(
        [
            ('pending', 'Pending'),
            ('checked', 'Dept. Checked'),
            ('approved', 'Dept. Approved'),
        ],
        string="Department Review",
        default='pending',
        tracking=True,
        copy=False,
    )

    def action_dept_checked(self):
        for order in self:
            if order.state != 'sent':
                raise UserError(_("Department check is only available on sent RFQs."))
            if order.dept_review_status == 'approved':
                raise UserError(_("This RFQ is already department approved."))
            order.dept_review_status = 'checked'
        return True

    def action_dept_approved(self):
        for order in self:
            if order.state != 'sent':
                raise UserError(_("Department approval is only available on sent RFQs."))
            if order.dept_review_status != 'checked':
                raise UserError(_("The department must check this RFQ before it can be approved."))
            order.dept_review_status = 'approved'
        return True

    def action_under_approval(self):
        for order in self:
            if order.state != 'sent':
                raise UserError(_("Only RFQ Sent orders can be moved to Under Approval."))
            order.write({'state': 'under_approval'})
        return True

    def action_approved(self):
        for order in self:
            if order.state != 'under_approval':
                raise UserError(_("Only orders Under Approval can be approved."))
            order.write({'state': 'approved'})
        return True

    def button_confirm(self):
        for order in self:
            if order.state not in ['draft', 'sent', 'approved']:
                continue
            error_msg = order._confirmation_error_message()
            if error_msg:
                raise UserError(error_msg)
            order.order_line._validate_analytic_distribution()
            order._add_supplier_to_product()
            if order._approval_allowed():
                order.button_approve()
            else:
                order.write({'state': 'to approve'})
        return True

    def _confirmation_error_message(self):
        error_msg = super()._confirmation_error_message()
        if error_msg:
            return error_msg
        vendor = self.partner_id.commercial_partner_id
        if vendor and vendor.state != 'approved':
            return _(
                "You cannot confirm this purchase order because the vendor %(vendor)s is not approved.",
                vendor=vendor.display_name,
            )
        return False
