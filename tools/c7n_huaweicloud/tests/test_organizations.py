# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from huaweicloud_common import BaseTest


class OrganizationsTest(BaseTest):

    def test_list_account(self):
        factory = self.replay_flight_data('organizations/list_account')
        p = self.load_policy(
            {
                "name": "list-org-account",
                "resource": "huaweicloud.org-account",
                "filters": [{"type": "value", "key": "status", "value": "active"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 2)
        self.assertEqual(resources[0]['name'], "fake_account_name")
        self.assertEqual(resources[0]['id'], "8e5fe930d666666666666666602c")

    def test_list_policy(self):
        factory = self.replay_flight_data('organizations/list_policy')
        p = self.load_policy(
            {
                "name": "list-org-policy",
                "resource": "huaweicloud.org-policy",
                "filters": [{"type": "value", "key": "type", "value": "service_control_policy"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['name'], "RestrictedForOU1")
        self.assertEqual(resources[0]['id'], "p-27lu7qg666666666666bm9jzk2zzk0")

    def test_list_unit(self):
        factory = self.replay_flight_data('organizations/list_unit')
        p = self.load_policy(
            {
                "name": "list-org-unit",
                "resource": "huaweicloud.org-unit",
                "filters": [
                    {"type": "value", "key": "id", "value": "^ou-[0-9a-z]{8,32}$", "op": "regex"}
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 2)
        self.assertEqual(resources[0]['name'], "Consoletest")
        self.assertEqual(resources[0]['id'], "ou-45wgiop666666666a1m9msn97fvvwe")

    def test_action_set_policy(self):
        factory = self.replay_flight_data('organizations/set_policy')
        p = self.load_policy(
            {
                "name": "create-and-attach-scp-for-account",
                "resource": "huaweicloud.org-account",
                "filters": [
                    {
                        "type": "value",
                        "key": "status",
                        "value": "active",
                    }
                ],
                "actions": [
                    {
                        "type": "set-policy",
                        "policy-type": "service_control_policy",
                        "name": "RestrictedForAccount1",
                        "contents": {
                            "Version": "5.0",
                            "Statement": {
                                "Sid": "RestrictedForAccount",
                                "Effect": "Deny",
                                "Action": ["ecs:*"],
                                "Resource": ["*"],
                            },
                        },
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 2)
        self.assertEqual(resources[0]['name'], "fake_account_name")
        self.assertEqual(resources[0]['id'], "8e5fe930d666666666666666602c")

    def test_filter_by_ou(self):
        factory = self.replay_flight_data('organizations/list_account_filter_by_ou')
        p = self.load_policy(
            {
                "name": "list-org-accounts-by-ous",
                "resource": "huaweicloud.org-account",
                "filters": [
                    {
                        "type": "ou",
                        "units": [
                            "ou-egmx31wae8c7v72jrl71ow6pb0cqz4fi",
                            "ou-wpl4rl17z5v9puqohfeqo8brezsta85t",
                        ],
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['name'], "fake_account_name")
        self.assertEqual(resources[0]['id'], "8e5fe930d666666666666666602c")

    def test_filter_by_org_unit(self):
        factory = self.replay_flight_data('organizations/list_ou_by_org_unit')
        p = self.load_policy(
            {
                "name": "org-units-by-parent-ou",
                "resource": "huaweicloud.org-unit",
                "filters": [
                    {"type": "org-unit", "key": "Name", "value": "ou-egmx31wa6666666666pb0cqz4fi"}
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['name'], "Consoletest")
        self.assertEqual(resources[0]['id'], "ou-45wgiop666666666a1m9msn97fvvwe")
