
from odoo.tests import HttpCase, tagged


@tagged("-at_install", "post_install")
class TestQunit(HttpCase):
    def test_qunit(self):
        self.browser_js(
            "/web/tests?module=web_domain_field&failfast",
            "",
            "",
            login="admin",
        )
