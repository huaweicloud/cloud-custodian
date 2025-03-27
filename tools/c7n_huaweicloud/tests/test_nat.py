# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from huaweicloud_common import BaseTest


class NatTest(BaseTest):

    def test_nat_gateway_query(self):
        factory = self.replay_flight_data('nat_gateway_query')
        p = self.load_policy({
             'name': 'nat-gateway-query',
             'resource': 'huaweicloud.nat-gateway'},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['name'], "test-nat-gateway")

    def test_nat_gateway_delete(self):
        factory = self.replay_flight_data('nat_gateway_delete')
        p = self.load_policy({
             'name': 'nat-gateway-delete',
             'resource': 'huaweicloud.nat-gateway',
             'actions': ['delete']},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['name'], "test-nat-gateway")

    def test_nat_snat_rule_query(self):
        factory = self.replay_flight_data('nat_snat_rule_query')
        p = self.load_policy({
             'name': 'nat-snat-rule-query',
             'resource': 'huaweicloud.nat-snat-rule'},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['description'], "test-nat-snat-rule")

    def test_nat_snat_rule_delete(self):
        factory = self.replay_flight_data('nat_snat_rule_delete')
        p = self.load_policy({
             'name': 'nat-snat-rule-delete',
             'resource': 'huaweicloud.nat-snat-rule',
             'actions': ['delete']},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['description'], "test-nat-snat-rule")

    def test_nat_dnat_rule_query(self):
        factory = self.replay_flight_data('nat_dnat_rule_query')
        p = self.load_policy({
             'name': 'nat-dnat-rule-query',
             'resource': 'huaweicloud.nat-dnat-rule'},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['description'], "test-nat-dnat-rule")

    def test_nat_dnat_rule_delete(self):
        factory = self.replay_flight_data('nat_dnat_rule_delete')
        p = self.load_policy({
             'name': 'nat-dnat-rule-delete',
             'resource': 'huaweicloud.nat-dnat-rule',
             'actions': ['delete']},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['description'], "test-nat-dnat-rule")
