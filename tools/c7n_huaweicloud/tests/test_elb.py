# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from huaweicloud_common import BaseTest


class ElbTest(BaseTest):

    def test_ensure_https_only(self):
        factory = self.replay_flight_data('elb_request')
        p = self.load_policy({
            "name": "ensure-https-only",
            "resource": "huaweicloud.elb-listener",
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
        self.assertEqual(resources[0]['id'], "f2a4ffc4-3121-46f6-8a2d-ba6ccd7258a3")
        self.assertEqual(resources[0]['protocol'], "UDP")

    def test_redirect_listener(self):
        factory = self.replay_flight_data('elb_redirect_listener_request')
        p = self.load_policy({
            "name": "redirect-listener",
            "resource": "huaweicloud.elb-listener",
            "filters": [{
                "type": "attributes",
                "key": "protocol",
                "value": "HTTP"
            }, {"not": [{
                "type": "is-redirect-to-https-listener"
            }]}],
            "actions": [{
                "type": "redirect-to-https-listener"
            }]
        }, session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['id'], "f2a4ffc4-3121-46f6-8a2d-ba6ccd7258a3")
        self.assertEqual(resources[0]['protocol'], "HTTP")
