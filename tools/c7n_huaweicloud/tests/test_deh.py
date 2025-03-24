# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from huaweicloud_common import BaseTest


class DeHTest(BaseTest):

    def test_update_dedicated_host(self):
        factory = self.replay_flight_data('update_dedicated_host')
        p = self.load_policy({
            "name": "update-dedicated-host",
            "resource": "huaweicloud.deh",
            "filters": [{
                "type": "value",
                "key": "name",
                "value": "DEH001"
            }],
            "actions": [{
                "type": "update-dedicated-host",
                "dedicated_host": {
                    "name": "update",
                    "auto_placement": "off"
                }

            }]
        }, session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['name'], "DEH001")
        self.assertEqual(resources[0]['dedicated_host_id'], "d465d0ae-f859-4a83-a508-8db654c05e7e")
