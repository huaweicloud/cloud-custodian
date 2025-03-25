# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from huaweicloud_common import BaseTest


class FlowLogTest(BaseTest):

    def test_set_flow_log_action(self):
        factory = self.replay_flight_data('vpc_set_flow_log_action')
        p = self.load_policy({
             'name': 'set-flow-log',
             'resource': 'huaweicloud.vpc-flow-log',
             'filters': [{'type': 'value', 'key': 'resource_type', 'value': 'vpc'},
                         {'type': 'value', 'key': 'status', 'value': 'DOWN'}],
             'actions': [{'type': 'set-flow-log', 'action': 'enable'}]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['resource_type'], 'vpc')
        self.assertEqual(resources[0]['status'], 'DOWN')
