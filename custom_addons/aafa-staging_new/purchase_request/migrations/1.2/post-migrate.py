# -*- coding: utf-8 -*-
"""Map old Selection `pr_category` values to Many2one `pr_category_id`."""


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api
    from odoo.addons.purchase_request.tools.pr_category_migrate import (
        map_pr_category_to_id,
    )

    env = api.Environment(cr, SUPERUSER_ID, {})
    map_pr_category_to_id(env, create_missing=True)
