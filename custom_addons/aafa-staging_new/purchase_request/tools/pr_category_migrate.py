# -*- coding: utf-8 -*-
"""Migrate old Selection column `pr_category` to Many2one `pr_category_id`."""

TABLES = (
    "purchase_request",
    "product_category",
    "sh_purchase_approval_config",
)


def _column_type(cr, table, column):
    cr.execute(
        """
        SELECT t.typname
          FROM pg_attribute a
          JOIN pg_class c ON c.oid = a.attrelid
          JOIN pg_namespace n ON n.oid = c.relnamespace
          JOIN pg_type t ON t.oid = a.atttypid
         WHERE c.relname = %s
           AND a.attname = %s
           AND n.nspname = current_schema()
           AND NOT a.attisdropped
           AND a.attnum > 0
        """,
        (table, column),
    )
    row = cr.fetchone()
    return row[0] if row else None


def _get_category_mapping(env, create_missing=False):
    if "purchase.request.category" not in env:
        return {}
    cr = env.cr
    cr.execute(
        """
        SELECT 1
          FROM information_schema.tables
         WHERE table_schema = current_schema()
           AND table_name = 'purchase_request_category'
        """
    )
    if not cr.fetchone():
        return {}

    Category = env["purchase.request.category"].sudo()
    general = env.ref(
        "purchase_request.pr_category_general", raise_if_not_found=False
    )
    it_categ = env.ref(
        "purchase_request.pr_category_it", raise_if_not_found=False
    )
    if not general:
        general = Category.search([("code", "=", "general_categ")], limit=1)
    if not it_categ:
        it_categ = Category.search([("code", "=", "it_categ")], limit=1)

    if create_missing:
        if not general:
            general = Category.create(
                {"name": "General Category", "code": "general_categ"}
            )
        if not it_categ:
            it_categ = Category.create(
                {"name": "IT Category", "code": "it_categ"}
            )

    if not general or not it_categ:
        return {}
    return {
        "general_categ": general.id,
        "it_categ": it_categ.id,
    }


def map_pr_category_to_id(env, table=None, create_missing=False):
    """Copy old selection/int values into `pr_category_id`, then drop backup cols."""
    cr = env.cr
    mapping = _get_category_mapping(env, create_missing=create_missing)
    tables = (table,) if table else TABLES

    for tbl in tables:
        if not _column_type(cr, tbl, "pr_category_id"):
            continue

        old_col = None
        old_type = None
        for candidate in ("pr_category_old", "pr_category"):
            col_type = _column_type(cr, tbl, candidate)
            if col_type:
                old_col = candidate
                old_type = col_type
                break

        if not old_col:
            continue

        if old_type in ("int2", "int4", "int8"):
            # Previous failed Many2one attempt stored ids already
            cr.execute(
                'UPDATE "%s" SET pr_category_id = "%s" '
                "WHERE pr_category_id IS NULL AND \"%s\" IS NOT NULL"
                % (tbl, old_col, old_col)
            )
        elif old_type in ("varchar", "text", "bpchar") and mapping:
            for old_key, new_id in mapping.items():
                cr.execute(
                    'UPDATE "%s" SET pr_category_id = %%s '
                    'WHERE "%s" = %%s AND pr_category_id IS NULL'
                    % (tbl, old_col),
                    (new_id, old_key),
                )

        cr.execute('ALTER TABLE "%s" DROP COLUMN IF EXISTS "%s"' % (tbl, old_col))
        if old_col != "pr_category_old":
            cr.execute(
                'ALTER TABLE "%s" DROP COLUMN IF EXISTS pr_category_old' % tbl
            )
        if old_col != "pr_category":
            cr.execute(
                'ALTER TABLE "%s" DROP COLUMN IF EXISTS pr_category' % tbl
            )
