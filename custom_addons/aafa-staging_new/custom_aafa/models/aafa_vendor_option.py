from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AafaVendorOption(models.Model):
    _name = 'aafa.vendor.option'
    _description = 'Vendor Option'
    _order = 'option_type, sequence, name'

    OPTION_TYPES = [
        ('vendor_category', 'Vendor Category'),
        ('vendor_criticality', 'Vendor Criticality'),
        ('vendor_status', 'Vendor Status'),
        ('renewal_status', 'Renewal Status'),
        ('assessment_status', 'Assessment Status'),
        ('business_assessment', 'Business Assessment'),
        ('risk_assessment_status', 'Risk Assessment Status'),
        ('risk_rating', 'Risk Rating'),
        ('compliance_risk', 'Compliance Risk'),
        ('total_risk_rating', 'Total Risk Rating'),
        ('business_review', 'Business Review'),
        ('vendor_management_review', 'Vendor Management'),
        ('compliance_risk_review', 'Compliance & Risk'),
        ('management_approval', 'Management Approval'),
        ('overall_vendor_status', 'Overall Vendor Status'),
    ]

    name = fields.Char(string="Option", required=True, translate=True)
    option_type = fields.Selection(OPTION_TYPES, string="Field", required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            'name_option_type_uniq',
            'unique(name, option_type)',
            'This option already exists for this field.',
        ),
    ]

    @api.model
    def name_create(self, name):
        if not self.env.context.get('default_option_type'):
            raise UserError(_('Please set the field type before creating an option.'))
        return super().name_create(name)
