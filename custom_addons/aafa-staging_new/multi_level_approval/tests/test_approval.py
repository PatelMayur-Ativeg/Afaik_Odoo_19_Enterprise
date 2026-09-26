# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

from datetime import timedelta

from odoo import exceptions, fields
from odoo.tests.common import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestApproval(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Approval = cls.env["multi.approval"]
        cls.ApprovalLine = cls.env["multi.approval.line"]
        cls.ApprovalType = cls.env["multi.approval.type"]
        cls.ApprovalTypeLine = cls.env["multi.approval.type.line"]
        cls.user_1 = cls.env["res.users"].create(
            {
                "name": "Demo User 1",
                "login": "dmuser_1",
                "password": "dmuser_1",
                "group_ids": [
                    (6, 0, cls.env.ref("base.group_user").ids),
                    (4, cls.env.ref("multi_level_approval.group_approval_user").id),
                ],
            }
        )
        cls.user_1.partner_id.email = "dmuser_1@test.com"
        cls.user_2 = cls.env["res.users"].create(
            {
                "name": "Demo User 2",
                "login": "dmuser_2",
                "password": "dmuser_2",
                "group_ids": [
                    (6, 0, cls.env.ref("base.group_user").ids),
                    (4, cls.env.ref("multi_level_approval.group_approval_user").id),
                ],
            }
        )
        cls.user_2.partner_id.email = "dmuser_2@test.com"
        cls.approval_type = cls.ApprovalType.create(
            {
                "name": "Type 1",
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
                    (
                        0,
                        0,
                        {
                            "name": "Level 2",
                            "user_id": cls.user_2.id,
                            "sequence": 2,
                            "require_opt": "Required",
                        },
                    ),
                ],
            }
        )
        cls.approval_request_1 = cls.Approval.create(
            {
                "name": "New request 1",
                "type_id": cls.approval_type.id,
                "description": "I just create a new request",
            }
        )

    def test_action_submit_error_document(self):
        self.approval_type.document_opt = "Required"
        with self.assertRaises(exceptions.UserError):
            self.approval_request_1.action_submit()
        self.env["ir.attachment"].create(
            {
                "name": "test att",
                "res_model": self.approval_request_1._name,
                "res_id": self.approval_request_1.id,
            }
        )
        self.approval_request_1.action_submit()

    def test_action_submit_error_no_line(self):
        self.approval_type.line_ids = False
        with self.assertRaises(exceptions.UserError):
            self.approval_request_1.action_submit()

    def test_action_submit_check_line(self):
        self.approval_request_1.action_submit()
        self.assertEqual(self.approval_request_1.state, "Submitted")
        self.assertEqual(len(self.approval_request_1.line_ids), 2)
        self.assertEqual(
            self.approval_request_1.line_ids[0].state, "Waiting for Approval"
        )
        self.assertEqual(self.approval_request_1.line_ids[1].state, "Draft")
        self.assertEqual(self.approval_request_1.line_ids[0].sequence, 1)
        self.assertEqual(self.approval_request_1.line_ids[1].sequence, 2)
        self.assertEqual(self.approval_request_1.line_ids[0].user_id, self.user_1)
        self.assertEqual(self.approval_request_1.line_ids[1].user_id, self.user_2)
        self.assertTrue(self.approval_request_1.line_ids[0].request_date)
        self.assertFalse(self.approval_request_1.line_ids[0].approved_date)
        self.assertFalse(self.approval_request_1.line_ids[1].request_date)
        self.assertFalse(self.approval_request_1.line_ids[1].approved_date)

    def test_action_cancel(self):
        self.approval_request_1.action_cancel()
        self.assertEqual(self.approval_request_1.state, "Cancel")

    def test_action_submit_send_email(self):
        self.approval_type.mail_notification = True
        self.approval_request_1.action_submit()
        message = self.env["mail.message"].search(
            [
                ("model", "=", self.approval_request_1._name),
                ("res_id", "=", self.approval_request_1.id),
            ]
        )
        self.assertTrue(message)
        self.assertTrue(
            any(
                "Approval requested" in (m.subject or "")
                or "Request the approval" in (m.subject or "")
                for m in message
            )
        )

    def test_action_submit_activity_notification(self):
        self.approval_type.activity_notification = True
        self.approval_request_1.action_submit()
        activity = self.env["mail.activity"].search(
            [
                (
                    "res_model_id",
                    "=",
                    self.env["ir.model"]._get(self.approval_request_1._name).id,
                ),
                ("res_id", "=", self.approval_request_1.id),
                (
                    "activity_type_id",
                    "=",
                    self.env.ref("mail.mail_activity_data_todo", False).id,
                ),
            ]
        )
        self.assertEqual(len(activity), 1)

    def test_action_approve_error_pic(self):
        self.approval_request_1.action_submit()
        with self.assertRaises(exceptions.AccessError):
            self.approval_request_1.with_user(self.user_2).action_approve()
        self.assertEqual(
            self.approval_request_1.line_ids[0].state, "Waiting for Approval"
        )

    def test_action_approve_success(self):
        self.approval_type.mail_notification = True
        self.approval_type.activity_notification = True
        self.approval_request_1.action_submit()
        self.approval_request_1.with_user(self.user_1).action_approve()
        self.assertEqual(self.approval_request_1.line_ids[0].state, "Approved")
        self.assertTrue(self.approval_request_1.line_ids[0].approved_date)
        self.assertEqual(
            self.approval_request_1.line_ids[1].state, "Waiting for Approval"
        )
        self.assertTrue(self.approval_request_1.line_ids[1].request_date)
        messages = self.env["mail.message"].search(
            [
                ("model", "=", self.approval_request_1._name),
                ("res_id", "=", self.approval_request_1.id),
            ]
        )
        request_mails = messages.filtered(
            lambda m: m.subject
            and (
                "Approval requested" in m.subject
                or "Request the approval" in m.subject
            )
        )
        self.assertEqual(len(request_mails), 2)
        activitiy = (
            self.env["mail.activity"]
            .sudo()
            .search(
                [
                    (
                        "res_model_id",
                        "=",
                        self.env["ir.model"]._get(self.approval_request_1._name).id,
                    ),
                    ("res_id", "=", self.approval_request_1.id),
                    (
                        "activity_type_id",
                        "=",
                        self.env.ref("mail.mail_activity_data_todo", False).id,
                    ),
                ]
            )
        )
        self.assertEqual(len(activitiy), 1)  # old activity has been done

        self.approval_request_1.with_user(self.user_2).action_approve()
        self.assertEqual(self.approval_request_1.line_ids[1].state, "Approved")
        self.assertTrue(self.approval_request_1.line_ids[1].approved_date)
        self.assertEqual(self.approval_request_1.state, "Approved")
        activitiy = (
            self.env["mail.activity"]
            .sudo()
            .search(
                [
                    (
                        "res_model_id",
                        "=",
                        self.env["ir.model"]._get(self.approval_request_1._name).id,
                    ),
                    ("res_id", "=", self.approval_request_1.id),
                    (
                        "activity_type_id",
                        "=",
                        self.env.ref("mail.mail_activity_data_todo", False).id,
                    ),
                ]
            )
        )
        self.assertEqual(len(activitiy), 0)

    def test_public_uuid_on_create(self):
        self.assertTrue(self.approval_request_1.public_uuid)

    def test_tokens_created_on_submit(self):
        self.approval_request_1.action_submit()
        tokens = self.approval_request_1.token_ids.filtered(lambda t: t.state == "active")
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens.user_id, self.user_1)
        self.assertEqual(tokens.line_id, self.approval_request_1.line_id)
        self.assertTrue(tokens.token)
        self.assertTrue(tokens.approve_url)
        self.assertTrue(tokens.reject_url)

    def test_tokens_with_proxy_users(self):
        proxy_user = self.env["res.users"].create(
            {
                "name": "Proxy User",
                "login": "proxy_user_ml",
                "password": "proxy_user_ml",
                "group_ids": [
                    (6, 0, self.env.ref("base.group_user").ids),
                    (4, self.env.ref("multi_level_approval.group_approval_user").id),
                ],
            }
        )
        proxy_user.partner_id.email = "proxy_ml@test.com"
        type_line = self.approval_type.line_ids.filtered(lambda l: l.sequence == 1)
        self.env["multi.approval.proxy.line"].create(
            {
                "type_id": self.approval_type.id,
                "approval_type_line_id": type_line.id,
                "start_date": "2020-01-01 00:00:00",
                "end_date": "2099-12-31 23:59:59",
                "proxy_user_ids": [(6, 0, [proxy_user.id])],
            }
        )
        request = self.Approval.create(
            {
                "name": "Request with proxy",
                "type_id": self.approval_type.id,
            }
        )
        request.action_submit()
        tokens = request.token_ids.filtered(lambda t: t.state == "active")
        self.assertEqual(len(tokens), 2)
        self.assertEqual(set(tokens.mapped("user_id")), {self.user_1, proxy_user})

    def test_token_rotation_on_next_level(self):
        self.approval_request_1.action_submit()
        level1_tokens = self.approval_request_1.token_ids.filtered(
            lambda t: t.state == "active"
        )
        self.assertEqual(level1_tokens.user_id, self.user_1)
        self.approval_request_1.with_user(self.user_1).action_approve()
        self.assertTrue(all(t.state == "revoked" for t in level1_tokens))
        level2_tokens = self.approval_request_1.token_ids.filtered(
            lambda t: t.state == "active"
        )
        self.assertEqual(len(level2_tokens), 1)
        self.assertEqual(level2_tokens.user_id, self.user_2)

    def test_public_approve_via_token_impersonation(self):
        self.approval_request_1.action_submit()
        token = self.approval_request_1.token_ids.filtered(lambda t: t.state == "active")
        self.assertTrue(token)
        result = (
            self.approval_request_1.with_user(token.user_id).sudo().action_approve()
        )
        self.assertTrue(result)
        self.assertEqual(self.approval_request_1.line_ids[0].state, "Approved")

    def test_public_refuse_via_token_impersonation(self):
        self.approval_request_1.action_submit()
        token = self.approval_request_1.token_ids.filtered(lambda t: t.state == "active")
        self.approval_request_1.with_user(token.user_id).sudo().action_refuse(
            reason="Not acceptable"
        )
        self.assertEqual(self.approval_request_1.state, "Refused")
        self.assertTrue(
            all(t.state != "active" for t in self.approval_request_1.token_ids)
        )

    def test_used_token_not_actionable_after_approve(self):
        self.approval_request_1.action_submit()
        token = self.approval_request_1.token_ids.filtered(lambda t: t.state == "active")[
            :1
        ]
        token_value = token.token
        line = token.line_id
        self.approval_request_1.with_user(token.user_id).sudo().action_approve()
        leftover = self.env["multi.approval.token"].search(
            [
                ("token", "=", token_value),
                ("approval_id", "=", self.approval_request_1.id),
                ("state", "=", "active"),
            ]
        )
        self.assertFalse(leftover)
        # Same line should not still be waiting
        self.assertNotEqual(line.state, "Waiting for Approval")

    def test_tokens_revoked_on_full_approve(self):
        self.approval_request_1.action_submit()
        self.approval_request_1.with_user(self.user_1).action_approve()
        self.approval_request_1.with_user(self.user_2).action_approve()
        self.assertEqual(self.approval_request_1.state, "Approved")
        self.assertFalse(
            self.approval_request_1.token_ids.filtered(lambda t: t.state == "active")
        )

    def test_action_refuse_error_pic(self):
        self.approval_request_1.action_submit()
        with self.assertRaises(exceptions.AccessError):
            self.approval_request_1.with_user(self.user_2).action_refuse()
        self.assertEqual(
            self.approval_request_1.line_ids[0].state, "Waiting for Approval"
        )

    def test_action_refuse_success_1(self):
        self.approval_request_1.action_submit()
        self.approval_request_1.with_user(self.user_1).action_refuse()
        self.assertEqual(self.approval_request_1.line_ids[0].state, "Refused")
        self.assertEqual(self.approval_request_1.line_ids[1].state, "Cancel")
        self.assertEqual(self.approval_request_1.state, "Refused")

    def test_action_refuse_success_2(self):
        self.approval_request_1.action_submit()
        self.approval_request_1.with_user(self.user_1).action_approve()
        self.approval_request_1.with_user(self.user_2).action_refuse()
        self.assertEqual(self.approval_request_1.line_ids[0].state, "Approved")
        self.assertEqual(self.approval_request_1.line_ids[1].state, "Refused")
        self.assertEqual(self.approval_request_1.state, "Refused")

    def test_action_refuse_success_3(self):
        self.approval_type.line_ids[0].require_opt = "Optional"
        self.approval_request_1.action_submit()
        self.approval_request_1.with_user(self.user_1).action_refuse()
        self.assertEqual(self.approval_request_1.state, "Submitted")
        self.approval_request_1.with_user(self.user_2).action_refuse()
        self.assertEqual(self.approval_request_1.line_ids[0].state, "Refused")
        self.assertEqual(self.approval_request_1.line_ids[1].state, "Refused")
        self.assertEqual(self.approval_request_1.state, "Refused")

    def test_action_refuse_then_approve(self):
        self.approval_type.line_ids[0].require_opt = "Optional"
        self.approval_request_1.action_submit()
        self.approval_request_1.with_user(self.user_1).action_refuse()
        self.approval_request_1.with_user(self.user_2).action_approve()
        self.assertEqual(self.approval_request_1.line_ids[0].state, "Refused")
        self.assertEqual(self.approval_request_1.line_ids[1].state, "Approved")
        self.assertEqual(self.approval_request_1.state, "Approved")

    def test_reminder_requires_delay(self):
        with self.assertRaises(exceptions.ValidationError):
            self.approval_type.write(
                {
                    "reminder_notification": True,
                    "reminder_delay": 0.0,
                }
            )

    def _reminder_messages(self, request):
        return self.env["mail.message"].search(
            [
                ("model", "=", request._name),
                ("res_id", "=", request.id),
                ("subject", "ilike", "Reminder"),
            ]
        )

    def test_pending_reminder_not_sent_before_delay(self):
        self.approval_type.write(
            {
                "reminder_notification": True,
                "reminder_delay": 5.5,
            }
        )
        self.approval_request_1.action_submit()
        sent = self.approval_request_1._send_pending_reminder_if_due()
        self.assertFalse(sent)
        self.assertFalse(self._reminder_messages(self.approval_request_1))
        self.assertFalse(self.approval_request_1.line_id.last_reminder_date)

    def test_pending_reminder_sent_after_delay(self):
        self.approval_type.write(
            {
                "reminder_notification": True,
                "reminder_delay": 5.5,
            }
        )
        self.approval_request_1.action_submit()
        waiting_line = self.approval_request_1.line_id
        waiting_line.request_date = fields.Datetime.now() - timedelta(hours=5, minutes=31)
        sent = self.approval_request_1._send_pending_reminder_if_due()
        self.assertTrue(sent)
        self.assertTrue(waiting_line.last_reminder_date)
        self.assertTrue(self._reminder_messages(self.approval_request_1))

        sent_again = self.approval_request_1._send_pending_reminder_if_due()
        self.assertFalse(sent_again)
        self.assertEqual(len(self._reminder_messages(self.approval_request_1)), 1)

        waiting_line.last_reminder_date = fields.Datetime.now() - timedelta(
            hours=5, minutes=31
        )
        self.env["multi.approval"]._cron_send_pending_reminders()
        self.assertEqual(len(self._reminder_messages(self.approval_request_1)), 2)

    def test_pending_reminder_not_sent_after_approve(self):
        self.approval_type.write(
            {
                "reminder_notification": True,
                "reminder_delay": 5.5,
            }
        )
        self.approval_request_1.action_submit()
        self.approval_request_1.line_id.request_date = (
            fields.Datetime.now() - timedelta(hours=6)
        )
        self.approval_request_1.with_user(self.user_1).action_approve()
        sent = self.approval_request_1._send_pending_reminder_if_due()
        self.assertFalse(sent)
        self.assertFalse(self._reminder_messages(self.approval_request_1))
