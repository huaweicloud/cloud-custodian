# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

from huaweicloud_common import BaseTest


class IamTest(BaseTest):
    def test_iam_delete(self):
        factory = self.replay_flight_data('iam_user_delete')
        p = self.load_policy({
            'name': 'delete-user',
            'resource': 'huaweicloud.iam-user',
            "actions": ["delete"]
        },
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 0)
