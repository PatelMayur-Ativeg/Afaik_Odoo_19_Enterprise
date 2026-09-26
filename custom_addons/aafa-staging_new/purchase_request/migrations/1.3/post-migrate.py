# -*- coding: utf-8 -*-
"""Move existing purchase requests past the removed review step."""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE purchase_request
        SET state = 'waiting_for_approval'
        WHERE state = 'waiting_for_review'
        """
    )
