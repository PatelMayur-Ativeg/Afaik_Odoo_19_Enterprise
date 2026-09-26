# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.fields import Command
import logging

_logger = logging.getLogger(__name__)

class CompanyActivity(models.Model):
    _name = 'company.activity'
    name = fields.Char(required=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

class Registration(models.Model):
    _name = 'vendor.registration'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    name = fields.Char(string='Sequence',default="New")
    state = fields.Selection(string="Status",
                                     selection=[
                                         ('draft', 'Draft'),
                                         ('approved', 'Purchase Approved'),
                                         ('account_approved', 'Account Approved'),
                                         ('rejected', 'Rejected'),
                                     ], default='draft', )
    #@ Company Details
    company_name = fields.Char('Company Name')
    company_email = fields.Char('Company Email')
    license_number = fields.Char('License No')
    license_issue_date = fields.Date('Issue Date')
    license_expiry_date = fields.Date('Expiry Date')
    country_id = fields.Many2one('res.country',string='Country of Incorporation')
    company_activity = fields.Many2many('company.activity',string='Company Activity')
    vat = fields.Char("VAT")
    company_website = fields.Char("Company Website")

    mobile_phone = fields.Char('Phone/Mobile')
    company_address = fields.Char('Company Addres')
    company_city = fields.Char('City')
    company_zip = fields.Char('PO Box')
    currency_id = fields.Many2one('res.currency', "Supplier Currency")

    #@ Manager Details
    first_name = fields.Char('First Name')
    last_name = fields.Char('Last Name')
    email = fields.Char('Email')
    mobile = fields.Char('Mobile')
    job_position = fields.Char('Job Position')
    birth_date = fields.Date('Birth Date')

    manager_country_id = fields.Many2one('res.country',string='Country Birth')
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
    manager_address = fields.Char('Addres')
    passport_issue_date = fields.Date('Passport Issue Date')
    passport_exp_date = fields.Date('Passport Expiry Date')

    # @ Bank Details
    bank_name = fields.Char('Bank Name')
    acc_holder_name = fields.Char('Account Holder Name')
    iban = fields.Char('IBAN Code')
    ifcs_code = fields.Char('IFCS Code')
    bank_address = fields.Char("Bank Address")
    acc_number = fields.Char('Account Number')
    swift_code = fields.Char('Swift Code')
    bank_details_scan = fields.Binary('Bank Details Attachment')
    bank_details_scan_name = fields.Char()

    #@ Document Details
    trade_license_scan = fields.Binary('Trade License Scan')
    trade_license_scan_name = fields.Char()
    emirates_id_scan = fields.Binary('Emirates ID Scan')
    emirates_id_scan_name = fields.Char()
    passport_scan_1st_page = fields.Binary('Passport Scan - First Page')
    passport_scan_1st_page_name = fields.Char()
    visa_scan = fields.Binary('Visa Scan')
    visa_scan_name = fields.Char()
    company_protfolio = fields.Binary('Company Portfolio')
    company_protfolio_name = fields.Char()
    coc_membership_cert = fields.Binary('Chamber of Commerce Membership Certificate')
    coc_membership_cert_name = fields.Char()
    vat_registration_copy = fields.Binary('Vat Registration Copy')
    vat_registration_copy_name = fields.Char()
    other_documents_copy = fields.Binary('Other Documents')
    other_documents_copy_name = fields.Char()

    reject_reason = fields.Char("Reject Reason")
    partner_ids = fields.One2many('res.partner', 'vendor_registration_id', string='Partners')
    partner_count = fields.Integer(compute='_compute_partner_count', string='Partners')

    @api.depends('partner_ids')
    def _compute_partner_count(self):
        for rec in self:
            rec.partner_count = len(rec.partner_ids)

    china_bool = fields.Boolean("China")
    uae_bool = fields.Boolean("UAE")
    # acc_approve_bool = fields.Boolean("Account Approved")
    country_radio = fields.Selection([('uae','UAE'),('china','China'),('other','Other')],string='Country')

    @api.onchange('country_id')
    def _onchange_country_id(self):
         for rec in self:
            if rec.country_id.code == 'CN':
                rec.china_bool=True
                rec.uae_bool=False
            elif rec.country_id.code == 'UAE':
                rec.uae_bool=True
                rec.china_bool=False
            else:
                rec.china_bool=False
                rec.uae_bool=False

    def action_approve(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("Only draft registrations can be approved."))
        tags = []
        for rec in self.company_activity:
            if rec.name:
                data = self.env['res.partner.category'].search([('name','=',rec.name)], limit=1)
                if data:
                    tags.append(int(data.id))
                else:
                    res = self.env['res.partner.category'].create({
                        'name': rec.name
                    })
                    tags.append(int(res.id))
        values={
            'company_type':'company',
            'name':self.company_name,
            'email':self.company_email,
            'website': self.company_website,
            'phone':self.mobile_phone,
            'street':self.company_address,
            'city':self.company_city,
            'zip':self.company_zip,
            'vat': self.vat,
            'license_number':self.license_number,
            'license_issue_date':self.license_issue_date,
            'license_expiry_date':self.license_expiry_date,
            'country_id':self.country_id.id,
            'inco_country_id':self.manager_country_id.id,
            'category_id':tags,
        }
        if 'state' in self.env['res.partner']._fields:
            values['state'] = 'portal_registered'
        values['vendor_registration_id'] = self.id
        partner_id = self.env['res.partner'].create(values)
        values = {
                    'name':self.bank_name,
                    'acc_holder_name':self.acc_holder_name,
                    'ifcs_code':self.ifcs_code,
                    'swift_code':self.swift_code,
                    'bic':self.iban,
                }
        bank_id = self.env['res.bank'].create(values)
        if self.first_name:
            values = {
                'name': self.first_name + ' ' + self.last_name,
                'type' : 'contact',
                'email': self.email,
                'phone': self.mobile,
                'function': self.job_position,
                'street': self.manager_address,
                'birth_date': self.birth_date,
                'country_id': self.manager_country_id.id,
                'vat': self.vat,
                'prev_nationality_id': self.prev_nationality_id.id,
                'passport_type': self.passport_type,
                'passport_no': self.passport_no,
                'passport_issued_country_id': self.passport_issued_country_id.id,
                'passport_issue_date': self.passport_issue_date,
                'passport_exp_date': self.passport_exp_date,
                'parent_id': partner_id.id,
                'vendor_registration_id': self.id,
                'property_purchase_currency_id': self.currency_id.id,
                'bank_ids': [(4,0,{
                            'bank_id':bank_id.id, 
                            'acc_number': self.acc_number
                            }
                        )]
            }
            contact_id = self.env['res.partner'].create(values)
        values = {
            'bank_id': bank_id.id,
            'acc_number': self.acc_number,
            'partner_id': partner_id.id if partner_id else contact_id.id if contact_id else False,
        }
        bank_id = self.env['res.partner.bank'].create(values)
        self._link_registration_documents_to_partner(partner_id)
        user = self._grant_partner_portal_access(partner_id)

        self.state = 'approved'
        self.send_create_vendor_notify(user)

    def _iter_uploaded_documents(self):
        self.ensure_one()
        document_fields = [
            ('trade_license_scan', 'trade_license_scan_name', _('Trade License Scan')),
            ('emirates_id_scan', 'emirates_id_scan_name', _('Emirates ID Scan')),
            ('passport_scan_1st_page', 'passport_scan_1st_page_name', _('Passport Scan - First Page')),
            ('visa_scan', 'visa_scan_name', _('Visa Scan')),
            ('company_protfolio', 'company_protfolio_name', _('Company Portfolio')),
            ('coc_membership_cert', 'coc_membership_cert_name', _('Chamber of Commerce Membership Certificate')),
            ('vat_registration_copy', 'vat_registration_copy_name', _('VAT Registration Copy')),
            ('bank_details_scan', 'bank_details_scan_name', _('Bank Details Attachment')),
            ('other_documents_copy', 'other_documents_copy_name', _('Other Documents')),
        ]
        for binary_field, name_field, default_name in document_fields:
            datas = self[binary_field]
            if datas:
                yield self[name_field] or default_name, datas

    def _get_or_create_partner_document_folder(self, partner):
        Document = self.env['documents.document'].sudo()
        folder = Document.search([
            ('type', '=', 'folder'),
            ('partner_id', '=', partner.id),
        ], limit=1)
        if folder:
            return folder
        parent = (
            self.env.ref('documents.document_legal_folder', raise_if_not_found=False)
            or self.env.ref('documents.document_inbox_folder', raise_if_not_found=False)
        )
        return Document.create({
            'name': partner.display_name,
            'type': 'folder',
            'partner_id': partner.id,
            'folder_id': parent.id if parent else False,
            'access_internal': 'edit',
            'company_id': partner.company_id.id or self.company_id.id or self.env.company.id,
        })

    def _link_registration_documents_to_partner(self, partner):
        """Put uploaded registration files into the partner Documents folder."""
        self.ensure_one()
        uploaded = list(self._iter_uploaded_documents())
        if not uploaded:
            return self.env['documents.document']
        folder = self._get_or_create_partner_document_folder(partner)
        return self.env['documents.document'].sudo().create([
            {
                'name': name,
                'datas': datas,
                'folder_id': folder.id,
                'partner_id': partner.id,
                'access_internal': 'edit',
                'owner_id': self.env.user.id,
            }
            for name, datas in uploaded
        ])

    def _grant_partner_portal_access(self, partner):
        """Create a portal user for the vendor and send the invitation email."""
        self.ensure_one()
        if not partner.email:
            raise UserError(_(
                "Cannot grant portal access because vendor %(vendor)s has no email.",
                vendor=partner.display_name,
            ))
        wizard = self.env['portal.wizard'].sudo().create({
            'partner_ids': [Command.set(partner.ids)],
        })
        for wizard_user in wizard.user_ids:
            if wizard_user.is_portal or wizard_user.is_internal:
                continue
            wizard_user.sudo().action_grant_access()
        users = self.env['res.users'].search([('partner_id', '=', partner.id)], limit=1)
        if not users:
            raise UserError(_(
                "Portal access could not be granted for vendor %(vendor)s.",
                vendor=partner.display_name,
            ))
        return users

    def action_view_partner(self):
        self.ensure_one()
        partners = self.partner_ids
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Vendor'),
            'res_model': 'res.partner',
            'view_mode': 'list,form',
            'domain': [('vendor_registration_id', '=', self.id)],
            'context': {'default_vendor_registration_id': self.id},
        }
        if len(partners) == 1:
            action['view_mode'] = 'form'
            action['res_id'] = partners.id
        return action

    def action_acc_approve(self):
        print("action_acc_approve")
        self.state='account_approved'

        # self.acc_approve_bool = True

    def action_reject(self):
        self.state = 'rejected'

    def _users_in_group(self, xmlid):
        """Odoo 19: res.groups has no `users`; members live on res.users.group_ids."""
        group = self.env.ref(xmlid, raise_if_not_found=False)
        if not group:
            return self.env['res.users']
        return self.env['res.users'].search([('group_ids', 'in', group.ids)])

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('vendor.rg') or 'New'
        records = super().create(vals_list)
        notify_users = self._users_in_group('vendor_registration.vendor_reg_group')
        if notify_users:
            records.send_create_notify(notify_users)
        return records
    def send_create_notify(self,users):
        for rec in self:
            base_url = self.env['ir.config_parameter'].get_param('web.base.url')
            subject = 'New Vendor Registration'

            body = 'New Vendor Registration # : {} has been created waiting your confirmation'.format(rec.name ) + ' click here to open: <a target=_BLANK href="{}/web?#id='.format(
                base_url) + str(
                rec.id) + '&view_type=form&model=vendor.registration&action=" style="font-weight: bold">' + str(
                rec.name) + '</a>'
            self.env['user.notify'].send_email(body, users,subject)
    def send_create_vendor_notify(self,users):
        for rec in self:
            subject = 'Your Vendor Registration'
            body = 'Your Vendor Registration # : {} has been confirmed'.format(rec.name )
            self.env['user.notify'].send_email(body, users,subject)

    def send_create_vendor_reject_notify(self,users):
        for rec in self:
            subject = 'Your Vendor Registration: Rejected'
            body = 'Your Vendor Registration # : {} has been rejected. Reason {}'.format(rec.name , rec.reject_reason)
            self.env['user.notify'].send_email(body, users,subject)
