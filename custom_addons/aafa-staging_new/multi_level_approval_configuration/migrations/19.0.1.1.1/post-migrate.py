def migrate(cr, version):
    """Re-sync Approve/Refuse buttons; skip view XML validation during upgrade."""
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.multi_level_approval_configuration.hooks import post_init_hook

    post_init_hook(env)
