# -*- coding: utf-8 -*-

from odoo import fields, models
from odoo.tools.image import image_data_uri


class ResUsers(models.Model):
    _inherit = "res.users"

    approval_signature = fields.Binary(
        string="Report Signature",
        attachment=True,
        help="Handwritten signature printed on configured approval reports.",
    )

    def _get_approval_report_signature(self):
        self.ensure_one()
        image = self.approval_signature
        if not image and "sign_signature" in self._fields:
            image = self.sign_signature
        return image or False

    def _get_approval_report_signature_src(self):
        self.ensure_one()
        image = self._get_approval_report_signature()
        if not image:
            return False
        if isinstance(image, str):
            image = image.encode()
        return image_data_uri(image)
