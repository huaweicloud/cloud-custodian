# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from huaweicloud_common import BaseTest


class RamTest(BaseTest):

    def test_search_external_shared_principals(self):
        factory = self.replay_flight_data('ram_request')
        p = self.load_policy({
            "name": "search-external-shared-principals",
            "resource": "huaweicloud.ram-shared-principals",
            "filters": [{
                "type": "value",
                "key": "external",
                "value": True
            }],
        }, session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['id'], "a60a0982-7be7-44e4-88ab-7999026f1a57")
        self.assertEqual(resources[0]['associated_entity'], "9673682b7bf2428cb613f37a19a0693f")
        self.assertEqual(resources[0]['association_type'], "principal")
        self.assertEqual(resources[0]['status'], "associated")

    def test_disassociate_external_shared_principals(self):
        factory = self.replay_flight_data('ram_request')
        p = self.load_policy({
            "name": "disassociate-external-shared-principals",
            "resource": "huaweicloud.ram-shared-principals",
            "filters": [{
                "type": "value",
                "key": "external",
                "value": True
            }],
            "actions": [{
                "type": "disassociate"
            }]
        }, session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
