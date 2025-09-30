# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from huaweicloud_common import BaseTest


class CocAlarmTest(BaseTest):

    def test_patch_non_compliant_query(self):
        factory = self.replay_flight_data('patch_non_compliant_alarm')
        p = self.load_policy({
            'name': 'list_instance_compliant',
            'resource': 'huaweicloud.coc-patch'},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['status'], "non_compliant")

    def test_patch_non_compliant_alarm(self):
        factory = self.replay_flight_data('patch_non_compliant_alarm')
        p = self.load_policy({
            'name': 'list_instance_compliant',
            'resource': 'huaweicloud.coc-patch',
            'filters': [
                {
                    'type': 'value',
                    'key': 'status',
                    'value': 'non_compliant'
                },
                {
                    'type': 'value',
                    'key': 'report_scene',
                    'value': 'ECS'
                }
            ],
            "actions": [{
                "type": "patch_non_compliant_alarm",
                "topic_urn_list": ["urn:smn:region:account-id:topic-name"],
                "subject": "Machine Non-compliant Patch Version Alert",
                "message": "There are machines with non compliant patch versions"
            }]
        },
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['status'], "non_compliant")

    def test_script_non_reviewer_query(self):
        factory = self.replay_flight_data('script_non_reviewer_alarm')
        p = self.load_policy({
            'name': 'list_scripts',
            'resource': 'huaweicloud.coc-script'},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources['data'][0]["total"], 212)

    def test_script_non_reviewer_alarm(self):
        factory = self.replay_flight_data('script_non_reviewer_alarm')
        p = self.load_policy({
            "name": "script_non_reviewer_alarm",
            "resource": "huaweicloud.coc-script",
            'filters': ["script_non_reviewer_filter"],
            "actions": [{
                "type": "script_non_reviewer_alarm",
                "topic_urn_list": ["urn:smn:region:account-id:topic-name"],
                "subject": "Script Security Non-Compliance Alert",
                "message": "The following script has been found to lack an assigned reviewer"
            }]
        },
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 2)
        self.assertEqual(resources[0]["name"], "gzz_213546")

    def test_script_non_reviewer_alarm2(self):
        factory = self.replay_flight_data('script_non_reviewer_alarm')
        p = self.load_policy({
            "name": "script_non_reviewer_alarm",
            "resource": "huaweicloud.coc-script",
            'filters': [
                {
                    'type': 'value',
                    'key': 'properties.reviewers',
                    'value': []
                },
                {
                    'type': 'value',
                    'key': 'properties.risk_level',
                    'value': 'MEDIUM'
                }
            ],
            "actions": [{
                "type": "script_non_reviewer_alarm",
                "topic_urn_list": ["urn:smn:region:account-id:topic-name"],
                "subject": "Script Security Non-Compliance Alert",
                "message": "The following script has been found to lack an assigned reviewer"
            }]
        },
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["name"], "cfm-test-0726001")
