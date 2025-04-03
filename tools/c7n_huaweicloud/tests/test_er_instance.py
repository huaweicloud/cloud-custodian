# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from huaweicloud_common import BaseTest


class EnterpriseRouterTest(BaseTest):

    def test_update_enterprise_router(self):
        factory = self.replay_flight_data('update_enterprise_router')
        p = self.load_policy({
            'name': 'update-enterprise-router',
            'resource': 'huaweicloud.er',
            'filters': [
                {"type": "value", "key": "auto_accept_shared_attachments", "value": True}
            ],
            "actions": ["update"]
        },
            session_factory=factory
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
