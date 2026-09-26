# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class partner(models.Model):
    _inherit = 'res.partner'

    vendor_registration_id = fields.Many2one(
        'vendor.registration',
        string='Vendor Registration',
        ondelete='set null',
        index='btree_not_null',
        copy=False,
    )
    license_number = fields.Char('License No')
    license_issue_date = fields.Date('Issue Date')
    license_expiry_date = fields.Date('Expiry Date')
    inco_country_id = fields.Many2one('res.country',string='Country of Incorporation')
    company_activity = fields.Many2many('company.activity',string='Company Activity')

    #@ Manager Details

    birth_date = fields.Date('Birth Date')
    prev_nationality_id = fields.Many2one('res.country',string='Previous Nationality')
    passport_type = fields.Selection(string="Passport Type",
                                     selection=[
                                         ('business', 'Business'),
                                         ('diplomat', 'Diplomat'),
                                         ('service', 'Service'),
                                         ('student', 'Student'),
                                         ('special', 'Special'),
                                                ], required=False, )
    passport_no = fields.Char('Passport Number')
    passport_issued_country_id = fields.Many2one('res.country',string='Issue Country')
    passport_issue_date = fields.Date('Passport Issue Date')
    passport_exp_date = fields.Date('Passport Expiry Date')
    #@ Document Details
    # trade_license_scan = fields.Binary('Trade License Scan')
    # trade_license_scan_name = fields.Char()
    # emirates_id_scan = fields.Binary('Emirates ID Scan')
    # emirates_id_scan_name = fields.Char()
    # passport_scan_1st_page = fields.Binary('Passport Scan - First Page')
    # passport_scan_1st_page_name = fields.Char()
    # visa_scan = fields.Binary('Visa Scan')
    # visa_scan_name = fields.Char()
    # company_protfolio = fields.Binary('Company Portfolio')
    # company_protfolio_name = fields.Char()
    # coc_membership_cert = fields.Binary('Chamber of Commerce Membership Certificate')
    # coc_membership_cert_name = fields.Char()
