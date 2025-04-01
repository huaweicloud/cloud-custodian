# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from huaweicloud_common import BaseTest


class EipTest(BaseTest):

    def test_eip_query(self):
        factory = self.replay_flight_data('antiddos_eip_query')
        p = self.load_policy(
            {'name': 'eip-enable-antiddos', 'resource': 'huaweicloud.antiddos-eip'},
            session_factory=factory
        )
        resources = p.run()
        self.assertEqual(len(resources), 2)
        self.assertEqual(resources[0]['status'], "notConfig")
        self.assertEqual(resources[1]['status'], "normal")

    def test_unprotected_eip_enable_antiddos(self):
        factory = self.replay_flight_data('antiddos_unprotected_eip_enable')
        p = self.load_policy(
            {
                'name': 'antiddos_unprotected_eip_enable',
                'resource': 'huaweicloud.antiddos-eip',
                'filters': [
                    {"type": "value", "key": "status", "value": "notConfig"}
                ],
                'actions': ["enable"],
            },
            session_factory=factory
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
