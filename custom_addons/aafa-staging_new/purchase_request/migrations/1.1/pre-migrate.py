# -*- coding: utf-8 -*-
"""Legacy 1.1: preserve old Selection column before field rename."""

TABLES = (
    "purchase_request",
    "product_category",
    "sh_purchase_approval_config",
)


def migrate(cr, version):
    from odoo.addons.purchase_request.tools.pr_category_migrate import (
        _column_type,
    )

    for table in TABLES:
        col_type = _column_type(cr, table, "pr_category")
        if not col_type or _column_type(cr, table, "pr_category_old"):
            continue
        if col_type in ("varchar", "text", "bpchar", "int2", "int4", "int8"):
            cr.execute(
                'ALTER TABLE "%s" RENAME COLUMN pr_category TO pr_category_old'
                % table
            )
