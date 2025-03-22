# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from huaweicloud_common import BaseTest


class CocTest(BaseTest):

    def test_non_compliant_query(self):
        factory = self.replay_flight_data('non_compliant_query')
        p = self.load_policy({
             'name': 'non-compliant-patch',
             'resource': 'huaweicloud.coc'},
            session_factory=factory)
        resources = p.run()
        count = resources.get('count')
        instance_compliant = resources.get('count')
        self.assertEqual(count, 1)
        self.assertEqual(instance_compliant[0]['status'], "non_compliant")
        self.assertEqual(instance_compliant[0]['report_scene'], "ECS")

    def test_non_compliant_alarm(self):
        factory = self.replay_flight_data("non_compliant_alarm")
        p = self.load_policy(
            {
                "name": "non-compliant-patch",
                "resource": "huaweicloud.coc",
                "actions": [{"type": "non_compliant_alarm"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
