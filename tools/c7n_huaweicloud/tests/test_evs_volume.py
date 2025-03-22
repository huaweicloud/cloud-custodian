# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from huaweicloud_common import BaseTest


class VolumeTest(BaseTest):

    def test_volume_query(self):
        factory = self.replay_flight_data('evs_volume_query')
        p = self.load_policy({
             'name': 'all-volumes',
             'resource': 'huaweicloud.volume'},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['name'], "custodian-volume")
        self.assertEqual(resources[0]['volume_type'], "GPSSD")
