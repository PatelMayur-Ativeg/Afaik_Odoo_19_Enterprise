# -*- coding: utf-8 -*-
"""Map old Selection keys to purchase.request.category records (legacy 1.1 path)."""


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api
    from odoo.addons.purchase_request.tools.pr_category_migrate import (
        map_pr_category_to_id,
    )

    env = api.Environment(cr, SUPERUSER_ID, {})
    map_pr_category_to_id(env, create_missing=True)
