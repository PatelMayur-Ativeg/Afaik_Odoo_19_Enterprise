# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http, fields, exceptions,_
from odoo.http import request
from odoo.addons.website.controllers.form import WebsiteForm
import base64
from odoo.addons.web.controllers.home import ensure_db, Home, SIGN_UP_REQUEST_PARAMS

import logging

_logger = logging.getLogger(__name__)


# class WebsiteFormInherit(WebsiteForm):

class AuthSignupHome(Home):

    @http.route(['/vendor/register'], type='http', auth="public", website=True)
    def vendor_registration_form(self, **kwargs):

        countries = request.env['res.country'].sudo().search([])
        activities = request.env['company.activity'].sudo().search([])
        currencies = request.env['res.currency'].sudo().search([])
        _logger.info(activities)
        return request.render("vendor_registration.vendor_registration",{'countries':countries,'activities':activities, 'currencies':currencies})

    @http.route(['/vendor/registration/submit'], type='http', auth="public", website=True)
    def vendor_registration_insert(self, **kwargs):
        result = {}
        _logger.info(kwargs)
        if kwargs:
            values = self.prepare_values(kwargs)
            try:
                order = request.env['vendor.registration'].sudo().create(values)
            except Exception as e:
                _logger.exception("Vendor registration submit failed")
                error_message = self.prepare_error_msg(e)
                countries = request.env['res.country'].sudo().search([])
                activities = request.env['company.activity'].sudo().search([])
                currencies = request.env['res.currency'].sudo().search([])
                return request.render(
                    "vendor_registration.vendor_registration",
                    {
                        'error_message': error_message,
                        'countries': countries,
                        'activities': activities,
                        'currencies': currencies,
                    },
                )
        countries = request.env['res.country'].sudo().search([])
        activities = request.env['company.activity'].sudo().search([])
        return "OK"

    def prepare_values(self,kwargs):
        Q = []
        if request.httprequest.form.getlist('company_activities'):
            for elem in request.httprequest.form.getlist('company_activities'):
                Q.append(int(elem))
        values = {
            'company_name': kwargs.get('company_name'),
            'company_email': kwargs.get('company_email'),
            'company_website': kwargs.get('company_website'),
            'license_number': kwargs.get('license_number'),
            'license_issue_date': kwargs.get('license_issue_date'),
            'license_expiry_date': kwargs.get('license_expiry_date'),
            'country_id': int(kwargs.get('country_of_incorporation')),
            'mobile_phone': kwargs.get('phone_number'),
            'company_address': kwargs.get('address_in_country'),
            'company_city': kwargs.get('city'),
            # 'company_activity': Q,
            'vat': kwargs.get('vat'),
            'company_zip': kwargs.get('po_box'),
            'first_name': kwargs.get('first_name'),
            'last_name': kwargs.get('last_name'),
            'email': kwargs.get('manager_email'),
            'mobile': kwargs.get('manager_mobile'),
            'job_position': kwargs.get('manager_title'),
            # 'birth_date': kwargs.get('date_of_birth'),
            # 'manager_country_id': int(kwargs.get('country_of_birth')),
            # 'prev_nationality_id': int(kwargs.get('previous_nationality')),
            # 'passport_type': kwargs.get('passport_type'),
            # 'passport_no': kwargs.get('passport_number'),
            # 'passport_issued_country_id': int(kwargs.get('passport_issue_country')),
            # 'passport_issue_date': kwargs.get('passport_issue_date'),
            # 'passport_exp_date': kwargs.get('passport_expiry_date'),
            # 'manager_address': kwargs.get('manager_international_address'),
            'bank_name': kwargs.get('bank_name'),
            'acc_holder_name': kwargs.get('bank_account_name'),
            'iban': kwargs.get('iban_code'),
            'bank_address': kwargs.get('bank_address'),
            'acc_number': kwargs.get('acc_number'),
            'swift_code': kwargs.get('swift_code'),
            'currency_id':int(kwargs.get('currency_id')),
            'country_radio':kwargs.get('is_country_radio'),

        }
        if kwargs.get('trade_license_doc', False):
            name = kwargs.get('trade_license_doc').filename
            file = kwargs.get('trade_license_doc')
            attachment = file.read()
            trade_license_doc = base64.b64encode(attachment)
            values.update({'trade_license_scan':trade_license_doc,'trade_license_scan_name':name})
        if kwargs.get('emirates_id_doc', False):
            name = kwargs.get('emirates_id_doc').filename
            file = kwargs.get('emirates_id_doc')
            attachment = file.read()
            emirates_id_doc = base64.b64encode(attachment)
            values.update({'emirates_id_scan':emirates_id_doc,'emirates_id_scan_name':name})

        if kwargs.get('passport_doc', False):
            name = kwargs.get('passport_doc').filename
            file = kwargs.get('passport_doc')
            attachment = file.read()
            passport_doc = base64.b64encode(attachment)
            values.update({'passport_scan_1st_page':passport_doc,'passport_scan_1st_page_name':name})

        if kwargs.get('visa_doc', False):
            name = kwargs.get('visa_doc').filename
            file = kwargs.get('visa_doc')
            attachment = file.read()
            visa_doc = base64.b64encode(attachment)
            values.update({'visa_scan':visa_doc,'visa_scan_name':name})

        if kwargs.get('company_portfolio_doc', False):
            name = kwargs.get('company_portfolio_doc').filename
            file = kwargs.get('company_portfolio_doc')
            attachment = file.read()
            company_portfolio_doc = base64.b64encode(attachment)
            values.update({'company_protfolio':company_portfolio_doc,'company_protfolio_name':name})

        if kwargs.get('chamber_commerce_doc', False):
            name = kwargs.get('chamber_commerce_doc').filename
            file = kwargs.get('chamber_commerce_doc')
            attachment = file.read()
            chamber_commerce_doc = base64.b64encode(attachment)
            values.update({'coc_membership_cert':chamber_commerce_doc,'coc_membership_cert_name':name})

        if kwargs.get('vat_registration_copy', False):
            name = kwargs.get('vat_registration_copy').filename
            file = kwargs.get('vat_registration_copy')
            attachment = file.read()
            chamber_commerce_doc = base64.b64encode(attachment)
            values.update({'vat_registration_copy':chamber_commerce_doc,'vat_registration_copy_name':name})

        if kwargs.get('other_documents_copy', False):
            name = kwargs.get('other_documents_copy').filename
            file = kwargs.get('other_documents_copy')
            attachment = file.read()
            chamber_commerce_doc = base64.b64encode(attachment)
            values.update({'other_documents_copy':chamber_commerce_doc,'other_documents_copy_name':name})

        bank_file = kwargs.get('bank_details_doc', False)
        if isinstance(bank_file, (list, tuple)):
            bank_file = next((f for f in bank_file if getattr(f, 'filename', None)), False)
        if bank_file and getattr(bank_file, 'filename', None):
            values.update({
                'bank_details_scan': base64.b64encode(bank_file.read()),
                'bank_details_scan_name': bank_file.filename,
            })

        return values

    def prepare_error_msg(self, exception):
        """Return a list of strings; the form template iterates error_message."""
        message = getattr(exception, 'name', None) or str(exception)
        if isinstance(message, (list, tuple)):
            return [str(item) for item in message]
        return [str(message)]

