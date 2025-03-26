# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from huaweicloud_common import BaseTest


class ElbTest(BaseTest):

    def test_ensure_https_only(self):
        factory = self.replay_flight_data('elb_request')
        p = self.load_policy({
            "name": "ensure-https-only",
            "resource": "huaweicloud.elb.listener",
            "filters": [{
                "type": "attributes",
                "key": "protocol",
                "value": "HTTPS",
                "op": "ne"
            }],
            "actions": [{
                "type": "delete"
            }]
        }, session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['id'], "3e5ed14e-ebd3-4097-9cc3-ffb0bc76c332")
        self.assertEqual(resources[0]['protocol'], "HTTPS")
