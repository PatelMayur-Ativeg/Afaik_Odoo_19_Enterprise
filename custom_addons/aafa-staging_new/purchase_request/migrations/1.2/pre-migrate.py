# -*- coding: utf-8 -*-
"""Keep old Selection values before ORM drops the unused `pr_category` column."""

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
        if not col_type:
            continue
        # Already backed up
        if _column_type(cr, table, "pr_category_old"):
            continue
        # Keep varchar selection values for post-migrate mapping
        if col_type in ("varchar", "text", "bpchar"):
            cr.execute(
                'ALTER TABLE "%s" RENAME COLUMN pr_category TO pr_category_old'
                % table
            )
        # If somehow already int from a previous attempt, keep as backup name
        elif col_type in ("int2", "int4", "int8"):
            cr.execute(
                'ALTER TABLE "%s" RENAME COLUMN pr_category TO pr_category_old'
                % table
            )
