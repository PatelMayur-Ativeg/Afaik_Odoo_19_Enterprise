# -*- coding: utf-8 -*-
from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        result = super().session_info()
        result["advanced_search_config"] = self.env["advanced.search.config"]._get_session_mapping()
        return result
