# -*- coding: utf-8 -*-
"""Remap removed state values before ORM loads the new Selection."""


def migrate(cr, version):
    # Must run in pre-migrate: selection keys are removed from the model.
    cr.execute(
        """
        UPDATE purchase_request
        SET state = 'waiting_for_approval'
        WHERE state IN ('waiting_for_review', 'approved')
        """
    )
