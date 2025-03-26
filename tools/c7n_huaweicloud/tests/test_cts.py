# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from huaweicloud_common import BaseTest


class TrackerListTest(BaseTest):
    def test_tracker_list(self):
        factory = self.replay_flight_data('cts_tracker_query')
        p = self.load_policy({
            'name': 'queryTracker',
            'resource': 'huaweicloud.cts-tracker',
        },
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 2)
