# -*- coding: utf-8 -*-


def post_init_hook(env_or_cr, registry=None):
    """Map old selection values after install."""
    from odoo import SUPERUSER_ID, api
    from odoo.addons.purchase_request.tools.pr_category_migrate import (
        map_pr_category_to_id,
    )

    if registry is not None:
        env = api.Environment(env_or_cr, SUPERUSER_ID, {})
    else:
        env = env_or_cr
    map_pr_category_to_id(env, create_missing=True)
