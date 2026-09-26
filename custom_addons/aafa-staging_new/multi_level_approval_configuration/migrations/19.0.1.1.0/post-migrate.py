def migrate(cr, version):
    """Sync Approve/Refuse buttons on documents for existing configured types."""
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.multi_level_approval_configuration.hooks import post_init_hook

    post_init_hook(env)
