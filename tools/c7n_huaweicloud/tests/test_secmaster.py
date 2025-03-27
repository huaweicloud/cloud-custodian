# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from huaweicloud_common import BaseTest


class SecmasterTest(BaseTest):

    def test_secmaster_query(self):
        factory = self.replay_flight_data('secmaster_query')
        p = self.load_policy({
            'name': 'secmaster_query',
            'resource': 'huaweicloud.secmaster'},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
