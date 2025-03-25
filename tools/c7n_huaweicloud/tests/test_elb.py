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

    def test_delete_no_backend_elb(self):
        factory = self.replay_flight_data('elb_request')
        p = self.load_policy({
            "name": "delete-no-backend-elb",
            "resource": "huaweicloud.elbloadbalancer",
            "filters": [{
                "type": "age",
                "hours": "5",
                "op": "gt"
            }, {
                "type": "backend-server-count",
                "count": "0",
                "op": "le"
            }],
            "actions": [{
                "type": "delete"
            }]
        }, session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['id'], "088170a1-2149-47ff-9033-bd8295c6218e")

    def test_unbind_publicip(self):
        factory = self.replay_flight_data('elb_request')
        p = self.load_policy({
            "name": "delete-no-backend-elb",
            "resource": "huaweicloud.elbloadbalancer",
            "filters": [{
                "type": "publicip-count",
                "count": "0",
                "op": "gt"
            }],
            "actions": [{
                "type": "unbind-publicips"
            }]
        }, session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 2)
        self.assertEqual(len(resources[0]['eips']), 0)

    def test_enable_logging(self):
        factory = self.replay_flight_data('elb_request')
        p = self.load_policy({
            "name": "enable-logging-for-elb",
            "resource": "huaweicloud.elbloadbalancer",
            "filters": [{
                "type": "is-not-logging"
            }],
            "actions": [{
                "type": "enable-logging",
                "log_group_id": "c5c89263-cfce-45cf-ac08-78cf537ba6c5",
                "log_topic_id": "328abfed-ab1a-4484-b2c1-031c0d06ea66"
            }]
        }, session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 2)
        self.assertEqual(resources[0]['log_group_id'], "c5c89263-cfce-45cf-ac08-78cf537ba6c5")
        self.assertEqual(resources[1]['log_group_id'], "c5c89263-cfce-45cf-ac08-78cf537ba6c5")
