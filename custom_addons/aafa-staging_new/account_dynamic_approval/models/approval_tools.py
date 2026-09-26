def send_approval_notifications(env, notifications):
    """Send bus notifications (Odoo 19 _sendone API, v16 _sendmany parity)."""
    bus = env['bus.bus']
    for target, notification_type, message in notifications:
        bus._sendone(target, notification_type, message)
