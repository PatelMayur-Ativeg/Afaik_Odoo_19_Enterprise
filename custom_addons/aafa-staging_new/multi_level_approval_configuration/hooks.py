##############################################################################
#
#    Copyright Domiup (<http://domiup.com>).
#
##############################################################################

import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Add Approve/Refuse on documents for already configured approval types."""
    types = env["multi.approval.type"].search(
        [
            ("is_configured", "=", True),
            ("apply_for_model", "=", True),
            ("model_id", "!=", False),
        ]
    )
    ResModel = env["ir.model"]
    for approval_type in types:
        # Isolate each type so one failure does not abort the migration txn.
        try:
            with env.cr.savepoint():
                model_id = ResModel._get_id(approval_type.model_id)
                approval_type.create_compute_field(
                    "x_is_approver",
                    model_id,
                    compute_val=approval_type.get_compute_is_approver_val(),
                )
                for view in approval_type.get_primary_views():
                    existed = approval_type.get_extended_view(view)
                    if existed:
                        # validate=False: avoid _check_xml while registry may be incomplete
                        # (e.g. purchase.order / account.batch.payment during upgrade).
                        approval_type._sync_document_approver_buttons(
                            existed, validate=False
                        )
        except Exception:
            _logger.exception(
                "Failed to sync document Approve/Refuse UI for approval type %s",
                approval_type.display_name,
            )
