"""Deduplicate multi_approval.public_uuid before UNIQUE index is created."""

import logging
import uuid

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        SELECT column_name
          FROM information_schema.columns
         WHERE table_name = 'multi_approval'
           AND column_name = 'public_uuid'
        """
    )
    if not cr.fetchone():
        return

    # Fill empty values first (UNIQUE allows multiple NULLs, but we want real UUIDs).
    cr.execute(
        """
        SELECT id
          FROM multi_approval
         WHERE public_uuid IS NULL OR public_uuid = ''
        """
    )
    for (rec_id,) in cr.fetchall():
        cr.execute(
            "UPDATE multi_approval SET public_uuid = %s WHERE id = %s",
            (str(uuid.uuid4()), rec_id),
        )

    # Keep the lowest id per duplicate uuid; regenerate the rest.
    cr.execute(
        """
        SELECT public_uuid, array_agg(id ORDER BY id) AS ids
          FROM multi_approval
         WHERE public_uuid IS NOT NULL
         GROUP BY public_uuid
        HAVING COUNT(*) > 1
        """
    )
    duplicates = cr.fetchall()
    fixed = 0
    for _public_uuid, ids in duplicates:
        # ids[0] keeps the existing uuid; regenerate for the rest
        for rec_id in ids[1:]:
            cr.execute(
                "UPDATE multi_approval SET public_uuid = %s WHERE id = %s",
                (str(uuid.uuid4()), rec_id),
            )
            fixed += 1

    if fixed or duplicates:
        _logger.info(
            "multi_level_approval: regenerated public_uuid on %s duplicate row(s)",
            fixed,
        )
