# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from huaweicloud_common import BaseTest


class CcTest(BaseTest):

    def test_search_cc(self):
        factory = self.replay_flight_data('cc_request')
        p = self.load_policy({
            "name": "search-cloud-connections",
            "resource": "huaweicloud.cc-cloud-connection",
            "filters": [{
                "type": "value",
                "key": "name",
                "value": "test-custodian-123"
            }],
        }, session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['id'], "03ac5131da4f460e8792ce0b9a1ac5e5")
        self.assertEqual(resources[0]['name'], "test-custodian-123")

    def test_delete_cc(self):
        factory = self.replay_flight_data('cc_delete_request')
        p = self.load_policy({
            "name": "search-cloud-connections",
            "resource": "huaweicloud.cc-cloud-connection",
            "filters": [{
                "type": "value",
                "key": "name",
                "value": "test-custodian-123"
            }],
            "actions": ["delete"]
        }, session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
