# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from huaweicloud_common import BaseTest


class KeyTest(BaseTest):
    # disable_key_rotation
    # enable_key_rotation
    # enable_key
    # disable_key
    # instance_disable
    def test_disable_key_query(self):
        factory = self.replay_flight_data('kms_query')
        p = self.load_policy({
            'name': 'all-keys',
            'resource': 'huaweicloud.kms',
            'filters': [{
                "type": "value",
                "key": "key_state",
                "value": "3"
            }]},
            session_factory=factory)
        resources = p.run()

        self.assertEqual(len(resources), 0)

    def test_enable_key_query(self):
        factory = self.replay_flight_data('kms_query')
        p = self.load_policy({
            'name': 'all-keys',
            'resource': 'huaweicloud.kms',
            'filters': [{'key_id': 'kms'}],
            'actions': ['enable_key']},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 0)

    def test_disable_key_rotation_query(self):
        factory = self.replay_flight_data('kms_query')
        p = self.load_policy({
            'name': 'all-keys',
            'resource': 'huaweicloud.kms',
            'filters': [{'key_id': 'kms'}],
            'actions': ['disable_key_rotation']},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 0)

    def test_enable_key_rotation_query(self):
        factory = self.replay_flight_data('kms_query')
        p = self.load_policy({
            'name': 'all-keys',
            'resource': 'huaweicloud.kms',
            'filters': [{'key_id': 'kms'}],
            'actions': ['enable_key_rotation']},
            session_factory=factory)
        resources = p.run()

        self.assertEqual(len(resources), 0)

    def test_key_query(self):
        factory = self.replay_flight_data('kms_query')
        p = self.load_policy({
            'name': 'all-keys',
            'resource': 'huaweicloud.kms',
            'filters': ['all_keys_disable']},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 0)
