"""Deduplicate multi_approval.public_uuid before UNIQUE index is created."""

import logging
import uuid

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = 'multi_approval'
           AND column_name = 'public_uuid'
        """
    )
    if not cr.fetchone():
        return

    cr.execute(
        """
        SELECT id
          FROM multi_approval
         WHERE public_uuid IS NULL OR btrim(public_uuid) = ''
        """
    )
    for (rec_id,) in cr.fetchall():
        cr.execute(
            "UPDATE multi_approval SET public_uuid = %s WHERE id = %s",
            (str(uuid.uuid4()), rec_id),
        )

    # Keep lowest id per uuid; regenerate the rest (avoid array_agg typing issues).
    cr.execute(
        """
        SELECT id
          FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY public_uuid ORDER BY id
                       ) AS rn
                  FROM multi_approval
                 WHERE public_uuid IS NOT NULL
                   AND btrim(public_uuid) <> ''
               ) t
         WHERE rn > 1
        """
    )
    dup_ids = [row[0] for row in cr.fetchall()]
    for rec_id in dup_ids:
        cr.execute(
            "UPDATE multi_approval SET public_uuid = %s WHERE id = %s",
            (str(uuid.uuid4()), rec_id),
        )

    if dup_ids:
        _logger.info(
            "multi_level_approval: regenerated public_uuid on %s duplicate row(s)",
            len(dup_ids),
        )
