from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    vendor_prod_line = fields.One2many('vendor.product', 'partner_prod_id', string="Product")

    state = fields.Selection(
        selection=[
            ('draft', 'Waiting for Approval'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('portal_registered', 'Portal Registered'),
        ],
        string="Status",
        default='draft',
        copy=False,
        tracking=True,
        index=True,
    )

    def _is_vendor_draft_state(self):
        self.ensure_one()
        return self.state in ('draft', 'portal_registered', False)

    def action_approve_vendor(self):
        for partner in self:
            if not partner._is_vendor_draft_state():
                raise UserError(_("Only draft or portal registered contacts can be approved."))
            partner.state = 'approved'

    def action_reject_vendor(self):
        for partner in self:
            if not partner._is_vendor_draft_state():
                raise UserError(_("Only draft or portal registered contacts can be rejected."))
            partner.state = 'rejected'

    def action_reset_vendor_to_draft(self):
        for partner in self:
            if partner.state not in ('approved', 'rejected'):
                raise UserError(_("Only approved or rejected contacts can be reset to draft."))
            partner.state = 'draft'

    # Vendor Classification
    vendor_seq = fields.Char(
        string="Vendor ID",
        copy=False,
        readonly=True,
        index=True,
    )
    vendor_category_id = fields.Many2one(
        'aafa.vendor.option',
        string="Vendor Category",
        domain="[('option_type', '=', 'vendor_category')]",
        context={'default_option_type': 'vendor_category'},
    )
    vendor_criticality_id = fields.Many2one(
        'aafa.vendor.option',
        string="Vendor Criticality",
        domain="[('option_type', '=', 'vendor_criticality')]",
        context={'default_option_type': 'vendor_criticality'},
    )
    vendor_status_id = fields.Many2one(
        'aafa.vendor.option',
        string="Vendor Status",
        domain="[('option_type', '=', 'vendor_status')]",
        context={'default_option_type': 'vendor_status'},
    )
    business_owner_id = fields.Many2one('hr.employee', string="Business Owner")
    business_owner_department_id = fields.Many2one(
        related='business_owner_id.department_id',
        string="Department",
        readonly=True,
        store=True,
    )
    vendor_manager_id = fields.Many2one('res.users', string="Vendor Manager")

    # Contract Information
    contract_number = fields.Char(string="Contract Number")
    contract_start_date = fields.Date(string="Contract Start Date")
    contract_expiry_date = fields.Date(string="Contract Expiry Date")
    renewal_required = fields.Boolean(string="Renewal Required")
    renewal_status_id = fields.Many2one(
        'aafa.vendor.option',
        string="Renewal Status",
        domain="[('option_type', '=', 'renewal_status')]",
        context={'default_option_type': 'renewal_status'},
    )

    # Annual Assessment
    last_assessment_date = fields.Date(string="Last Assessment Date")
    next_assessment_date = fields.Date(string="Next Assessment Date")
    assessment_status_id = fields.Many2one(
        'aafa.vendor.option',
        string="Assessment Status",
        domain="[('option_type', '=', 'assessment_status')]",
        context={'default_option_type': 'assessment_status'},
    )
    business_assessment_id = fields.Many2one(
        'aafa.vendor.option',
        string="Business Assessment",
        domain="[('option_type', '=', 'business_assessment')]",
        context={'default_option_type': 'business_assessment'},
    )

    # Compliance & Risk
    risk_assessment_status_id = fields.Many2one(
        'aafa.vendor.option',
        string="Risk Assessment Status",
        domain="[('option_type', '=', 'risk_assessment_status')]",
        context={'default_option_type': 'risk_assessment_status'},
    )
    risk_rating_id = fields.Many2one(
        'aafa.vendor.option',
        string="Risk Rating",
        domain="[('option_type', '=', 'risk_rating')]",
        context={'default_option_type': 'risk_rating'},
    )
    compliance_risk_id = fields.Many2one(
        'aafa.vendor.option',
        string="Compliance Risk",
        domain="[('option_type', '=', 'compliance_risk')]",
        context={'default_option_type': 'compliance_risk'},
    )
    total_risk_rating_id = fields.Many2one(
        'aafa.vendor.option',
        string="Total Risk Rating",
        domain="[('option_type', '=', 'total_risk_rating')]",
        context={'default_option_type': 'total_risk_rating'},
    )
    risk_assessment_date = fields.Date(string="Assessment Date")
    assessed_by_id = fields.Many2one('res.users', string="Assessed By")
    risk_mitigation = fields.Text(string="Risk Mitigation")
    next_risk_review = fields.Date(string="Next Risk Review")

    # Document Control
    # Single file: Binary / Attachment -> Many2one ir.attachment
    # Multiple files: Other Documents -> Many2many ir.attachment
    _SINGLE_DOCUMENT_FIELDS = {
        'trade_license': {
            'attachment': 'trade_license_id',
            'filename': 'trade_license_filename',
            'label': 'Trade License',
        },
        'insurance_document': {
            'attachment': 'insurance_document_id',
            'filename': 'insurance_document_filename',
            'label': 'Insurance',
        },
        'contract_document': {
            'attachment': 'contract_document_id',
            'filename': 'contract_document_filename',
            'label': 'Contract',
        },
        'nda_document': {
            'attachment': 'nda_document_id',
            'filename': 'nda_document_filename',
            'label': 'NDA',
        },
        'sla_document': {
            'attachment': 'sla_document_id',
            'filename': 'sla_document_filename',
            'label': 'SLA',
        },
    }

    trade_license_id = fields.Many2one('ir.attachment', string="Trade License", copy=False, ondelete='set null')
    trade_license = fields.Binary(
        string="Trade License",
        compute='_compute_document_binaries',
        inverse='_inverse_trade_license',
    )
    trade_license_filename = fields.Char(
        compute='_compute_document_binaries',
        inverse='_inverse_trade_license_filename',
    )
    license_expiry = fields.Date(string="License Expiry")
    insurance_document_id = fields.Many2one('ir.attachment', string="Insurance", copy=False, ondelete='set null')
    insurance_document = fields.Binary(
        string="Insurance",
        compute='_compute_document_binaries',
        inverse='_inverse_insurance_document',
    )
    insurance_document_filename = fields.Char(
        compute='_compute_document_binaries',
        inverse='_inverse_insurance_document_filename',
    )
    insurance_expiry = fields.Date(string="Insurance Expiry")
    contract_document_id = fields.Many2one('ir.attachment', string="Contract", copy=False, ondelete='set null')
    contract_document = fields.Binary(
        string="Contract",
        compute='_compute_document_binaries',
        inverse='_inverse_contract_document',
    )
    contract_document_filename = fields.Char(
        compute='_compute_document_binaries',
        inverse='_inverse_contract_document_filename',
    )
    nda_document_id = fields.Many2one('ir.attachment', string="NDA", copy=False, ondelete='set null')
    nda_document = fields.Binary(
        string="NDA",
        compute='_compute_document_binaries',
        inverse='_inverse_nda_document',
    )
    nda_document_filename = fields.Char(
        compute='_compute_document_binaries',
        inverse='_inverse_nda_document_filename',
    )
    sla_document_id = fields.Many2one('ir.attachment', string="SLA", copy=False, ondelete='set null')
    sla_document = fields.Binary(
        string="SLA",
        compute='_compute_document_binaries',
        inverse='_inverse_sla_document',
    )
    sla_document_filename = fields.Char(
        compute='_compute_document_binaries',
        inverse='_inverse_sla_document_filename',
    )
    other_document_ids = fields.Many2many(
        'ir.attachment',
        'res_partner_other_document_rel',
        'partner_id',
        'attachment_id',
        string="Other Documents",
    )

    # Review / Approval
    business_review_id = fields.Many2one(
        'aafa.vendor.option',
        string="Business Review",
        domain="[('option_type', '=', 'business_review')]",
        context={'default_option_type': 'business_review'},
    )
    vendor_management_review_id = fields.Many2one(
        'aafa.vendor.option',
        string="Vendor Management",
        domain="[('option_type', '=', 'vendor_management_review')]",
        context={'default_option_type': 'vendor_management_review'},
    )
    compliance_risk_review_id = fields.Many2one(
        'aafa.vendor.option',
        string="Compliance & Risk",
        domain="[('option_type', '=', 'compliance_risk_review')]",
        context={'default_option_type': 'compliance_risk_review'},
    )
    management_approval_id = fields.Many2one(
        'aafa.vendor.option',
        string="Management Approval",
        domain="[('option_type', '=', 'management_approval')]",
        context={'default_option_type': 'management_approval'},
    )
    overall_vendor_status_id = fields.Many2one(
        'aafa.vendor.option',
        string="Overall Vendor Status",
        domain="[('option_type', '=', 'overall_vendor_status')]",
        context={'default_option_type': 'overall_vendor_status'},
    )

    def _upsert_document_attachment(self, attachment_field, datas, filename, default_name):
        self.ensure_one()
        attachment = self[attachment_field]
        if not datas:
            if attachment:
                attachment.unlink()
            self[attachment_field] = False
            return
        values = {
            'name': filename or default_name,
            'datas': datas,
            'res_model': self._name,
            'res_id': self.id,
            'type': 'binary',
        }
        if attachment:
            attachment.write(values)
        else:
            self[attachment_field] = self.env['ir.attachment'].create(values)

    def _inverse_single_document(self, binary_field):
        meta = self._SINGLE_DOCUMENT_FIELDS[binary_field]
        for rec in self:
            rec._upsert_document_attachment(
                meta['attachment'],
                rec[binary_field],
                rec[meta['filename']],
                meta['label'],
            )

    def _inverse_single_document_filename(self, binary_field):
        meta = self._SINGLE_DOCUMENT_FIELDS[binary_field]
        for rec in self:
            filename = rec[meta['filename']]
            if rec[meta['attachment']] and filename:
                rec[meta['attachment']].name = filename

    @api.depends(
        'trade_license_id', 'trade_license_id.datas', 'trade_license_id.name',
        'insurance_document_id', 'insurance_document_id.datas', 'insurance_document_id.name',
        'contract_document_id', 'contract_document_id.datas', 'contract_document_id.name',
        'nda_document_id', 'nda_document_id.datas', 'nda_document_id.name',
        'sla_document_id', 'sla_document_id.datas', 'sla_document_id.name',
    )
    def _compute_document_binaries(self):
        for rec in self:
            for binary_field, meta in rec._SINGLE_DOCUMENT_FIELDS.items():
                attachment = rec[meta['attachment']]
                rec[binary_field] = attachment.datas if attachment else False
                rec[meta['filename']] = attachment.name if attachment else False

    def _inverse_trade_license(self):
        self._inverse_single_document('trade_license')

    def _inverse_trade_license_filename(self):
        self._inverse_single_document_filename('trade_license')

    def _inverse_insurance_document(self):
        self._inverse_single_document('insurance_document')

    def _inverse_insurance_document_filename(self):
        self._inverse_single_document_filename('insurance_document')

    def _inverse_contract_document(self):
        self._inverse_single_document('contract_document')

    def _inverse_contract_document_filename(self):
        self._inverse_single_document_filename('contract_document')

    def _inverse_nda_document(self):
        self._inverse_single_document('nda_document')

    def _inverse_nda_document_filename(self):
        self._inverse_single_document_filename('nda_document')

    def _inverse_sla_document(self):
        self._inverse_single_document('sla_document')

    def _inverse_sla_document_filename(self):
        self._inverse_single_document_filename('sla_document')

    def _link_other_documents(self):
        for rec in self:
            if rec.other_document_ids:
                rec.other_document_ids.write({
                    'res_model': rec._name,
                    'res_id': rec.id,
                })

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('vendor_seq') and not vals.get('parent_id'):
                vals['vendor_seq'] = self.env['ir.sequence'].next_by_code('res.partner.vendor') or _('New')
        records = super().create(vals_list)
        records._link_other_documents()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'other_document_ids' in vals:
            self._link_other_documents()
        return res


class VendorProduct(models.Model):
    _name = 'vendor.product'

    partner_prod_id=fields.Many2one('res.partner',string="Product",)
    partner_supplier_id=fields.Many2one('product.supplierinfo',string="Product supplier Info",)
    product_id=fields.Many2one('product.template',string="Product Template",)
    minimum_qty=fields.Float(string="Minimal Quantity")
    price=fields.Float(string="Price")
    delivery_lead_time=fields.Float(string="Delivery Lead Time")