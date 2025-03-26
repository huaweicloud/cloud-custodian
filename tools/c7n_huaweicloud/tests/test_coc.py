# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from huaweicloud_common import BaseTest


class CocTest(BaseTest):

    def test_non_compliant_alarm(self):
        factory = self.replay_flight_data("non_compliant_alarm")
        p = self.load_policy(
            {
                "name": "non_compliant_alarm",
                "resource": "huaweicloud.coc",
                "filters": [{
                    "type": "value",
                    "key": "status",
                    "value": "non_compliant"
                },
                {
                    "type": "value",
                    "key": "report_scene",
                    "value": "ECS"
                },
                {
                    "type": "value",
                    "key": "operating_system",
                    "value": "EulerOS"
                },
                {
                    "type": "value",
                    "key": "region",
                    "value": "cn-north-4"
                }],
                "actions": [{
                    "type": "non_compliant_alarm",
                    "smn": "true",
                    "region_id": "cn-north-4",
                    "topic_urn": "urn:smn:cn-north-4:xxxxx:custodian_test",
                    "subject": "Machine Non-compliant Patch Version Alert",
                    "message": "There are machines with non compliant patch "
                               "versions installed under your account:"
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
