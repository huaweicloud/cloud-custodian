# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from huaweicloud_common import BaseTest


class AlarmTest(BaseTest):

    def test_alarm_query(self):
        factory = self.replay_flight_data('ces_alarm_query')
        p = self.load_policy({
            'name': 'all-alarms',
            'resource': 'huaweicloud.ces-alarm'},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['alarm_id'], "al17427965140272BWJEvgrp")

    def test_alarm_update_notification(self):
        factory = self.replay_flight_data('ces_alarm_update_notification')
        p = self.load_policy({
            "name": "ces-alarm-have-smn-check",
            "resource": "huaweicloud.ces-alarm",
            "filters": [{
                "type": "value",
                "key": "notification_enabled",
                "value": "false"
            }],
            "actions": [{
                "type": "alarm-update-notification",
                "parameters": {
                    "action_type": "notification",
                    "notification_list": ["urn:smn:cn-north-4:xxxxx:CES_notification_xxxxxxx"]
                }
            }]
        },
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 0)

    def test_batch_start_stopped_alarm_rules(self):
        factory = self.replay_flight_data('ces_batch_start_stopped_alarm_rules')
        p = self.load_policy({
            'name': 'batch-start-stopped-alarm-rules',
            'resource': 'huaweicloud.ces-alarm',
            "filters": [{
                "type": "value",
                "key": "enabled",
                "value": "false"
            }],
            "actions": [{
                "type": "batch-start-stopped-alarm-rules",
                "parameters": {
                    "message": "You have the following alarms that have not been started, "
                               "please check the system. The tasks have been started, "
                               "please log in to the system and check again.",
                    "subject": "CES alarm not activated Check email",
                    "notification_list": ["urn:smn:cn-north-4:xxxxx:CES_notification_xxxxxxx"]
                }
            }]
        },
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 0)

    def test_create_kms_event_alarm_rule(self):
        factory = self.replay_flight_data('create_kms_event_alarm_rule')
        p = self.load_policy({
            'name': 'alarm-kms-disable-or-delete-key',
            'resource': 'huaweicloud.ces-alarm',
            'actions': [{
                'type': 'create-kms-event-alarm-rule',
                'parameters': {
                    'action_type': 'notification',
                    'notification_list': ['urn:smn:cn-north-4:test:test']
                }
            }]
        },
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)

    def test_create_obs_event_alarm_rule(self):
        factory = self.replay_flight_data('create_obs_event_alarm_rule')
        p = self.load_policy({
            'name': 'alarm-obs-bucket-policy-change',
            'resource': 'huaweicloud.ces-alarm',
            'actions': [{
                'type': 'create-obs-event-alarm-rule',
                'parameters': {
                    'action_type': 'notification',
                    'notification_list': ['urn:smn:cn-north-4:test:test']
                }
            }]
        },
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)

    def test_notif_by_smn(self):
        factory = self.replay_flight_data('notif_by_smn')
        p = self.load_policy({
            'name': 'alarm-resource-check',
            'resource': 'huaweicloud.ces-alarm',
            'actions': [{
                'type': 'notify-by-smn',
                'parameters': {
                    'subject': "Test Subject",
                    'message': "Test Message",
                    'notification_list': ["urn:smn:cn-north-4:test:test"]
                }
            }]
        },
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['alarm_id'], "al17427965140272BWJEvgrp")

    def test_create_vpc_event_alarm_rule(self):
        factory = self.replay_flight_data('create_vpc_event_alarm_rule')
        p = self.load_policy({
            'name': 'alarm-vpc-change',
            'resource': 'huaweicloud.ces-alarm',
            'actions': [{
                'type': 'create-vpc-event-alarm-rule',
                'parameters': {
                    'action_type': 'notification',
                    'notification_list': ['urn:smn:cn-north-4:test:test']
                }
            }]
        },
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
