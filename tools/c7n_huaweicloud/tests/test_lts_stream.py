# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from huaweicloud_common import BaseTest


class StreamTest(BaseTest):

    def test_stream_query(self):
        factory = self.replay_flight_data('lts_stream_query')
        p = self.load_policy({
            'name': 'all-streams',
            'resource': 'huaweicloud.lts-stream'},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['log_group_id'], "test-log-group-id")

    def test_stream_storage_enabled_filter(self):
        factory = self.replay_flight_data('lts_stream_storage_enabled_filter')
        p = self.load_policy({
            'name': 'streams-with-storage-enabled',
            'resource': 'huaweicloud.lts-stream',
            'filters': [{
                'type': 'streams-storage-enabled-for-schedule'
            }]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 2)
        self.assertEqual(resources[0]['log_stream_id'], "test-log-stream-id")

    def test_disable_stream_storage(self):
        factory = self.replay_flight_data('lts_disable_stream_storage')
        p = self.load_policy({
            'name': 'disable-stream-storage',
            'resource': 'huaweicloud.lts-stream',
            'filters': [{
                'type': 'streams-storage-enabled-for-schedule'
            }],
            'actions': [{
                'type': 'disable-stream-storage'
            }]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 2)
        self.assertEqual(resources[0]['log_group_id'], "test-log-group-id")
        self.assertEqual(resources[0]['log_stream_id'], "test-log-stream-id")
