# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

import re

from odoo.tests.common import HttpCase, tagged


@tagged("-at_install", "post_install")
class TestPublicApprovalHttp(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_1 = cls.env["res.users"].create(
            {
                "name": "HTTP Approver",
                "login": "http_approver_ml",
                "password": "http_approver_ml",
                "group_ids": [
                    (6, 0, cls.env.ref("base.group_user").ids),
                    (4, cls.env.ref("multi_level_approval.group_approval_user").id),
                ],
            }
        )
        cls.user_1.partner_id.email = "http_approver@test.com"
        cls.approval_type = cls.env["multi.approval.type"].create(
            {
                "name": "HTTP Type",
                "mail_notification": True,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Level 1",
                            "user_id": cls.user_1.id,
                            "sequence": 1,
                            "require_opt": "Required",
                        },
                    ),
                ],
            }
        )

    def _create_submitted_request(self):
        request = self.env["multi.approval"].create(
            {
                "name": "HTTP Request",
                "type_id": self.approval_type.id,
                "description": "Please approve",
            }
        )
        request.action_submit()
        return request

    def _extract_csrf(self, html):
        match = re.search(
            r'name=["\']csrf_token["\'][^>]*value=["\']([^"\']+)["\']',
            html,
        )
        if not match:
            match = re.search(
                r'value=["\']([^"\']+)["\'][^>]*name=["\']csrf_token["\']',
                html,
            )
        self.assertTrue(match, "CSRF token not found in page")
        return match.group(1)

    def test_public_approve_get_and_post(self):
        approval = self._create_submitted_request()
        token = approval.token_ids.filtered(lambda t: t.state == "active")[:1]
        self.assertTrue(token)
        url = f"/multi_approval/{approval.public_uuid}/{token.token}/approve"

        # GET shows confirmation (does not mutate)
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Confirm Approval", response.content)
        approval.invalidate_recordset()
        self.assertEqual(approval.state, "Submitted")

        csrf = self._extract_csrf(response.text)
        response = self.url_open(
            url,
            data={"csrf_token": csrf},
            timeout=30,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Approved", response.content)
        approval.invalidate_recordset()
        self.assertEqual(approval.state, "Approved")

    def test_public_reject_requires_reason(self):
        approval = self._create_submitted_request()
        token = approval.token_ids.filtered(lambda t: t.state == "active")[:1]
        url = f"/multi_approval/{approval.public_uuid}/{token.token}/reject"

        get_response = self.url_open(url)
        self.assertEqual(get_response.status_code, 200)
        csrf = self._extract_csrf(get_response.text)

        response = self.url_open(
            url,
            data={"csrf_token": csrf, "reason": ""},
            timeout=30,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"refusal reason is required", response.content)
        approval.invalidate_recordset()
        self.assertEqual(approval.state, "Submitted")

        csrf = self._extract_csrf(response.text)
        response = self.url_open(
            url,
            data={"csrf_token": csrf, "reason": "Not ok"},
            timeout=30,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Refused", response.content)
        approval.invalidate_recordset()
        self.assertEqual(approval.state, "Refused")

    def test_invalid_token_shows_error(self):
        approval = self._create_submitted_request()
        url = (
            f"/multi_approval/{approval.public_uuid}/"
            "00000000-0000-0000-0000-000000000000/approve"
        )
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Action not available", response.content)
