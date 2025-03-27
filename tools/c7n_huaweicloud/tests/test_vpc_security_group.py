# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from huaweicloud_common import BaseTest


class SecurityGroupTest(BaseTest):

    def test_security_group_query(self):
        factory = self.replay_flight_data('vpc_security_group_query')
        p = self.load_policy({
             'name': 'security-group-test-name',
             'resource': 'huaweicloud.vpc-security-group',
             'filters': [{'type': 'value', 'key': 'name', 'value': 'sg-test'}]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['name'], 'sg-test')

    def test_security_group_unattached_filter(self):
        factory = self.replay_flight_data('vpc_security_group_unattached')
        p = self.load_policy({
             'name': 'security-group-unattached',
             'resource': 'huaweicloud.vpc-security-group',
             'filters': ['unattached']},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['name'], 'sg-not-attached')

    def test_security_group_delete_action(self):
        factory = self.replay_flight_data('vpc_security_group_delete')
        p = self.load_policy({
             'name': 'security-group-test-name-delete',
             'resource': 'huaweicloud.vpc-security-group',
             'filters': [{'type': 'value', 'key': 'name', 'value': 'sg-test'}],
             'actions': ['delete']},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['name'], 'sg-test')

    def test_security_group_rule_ingress_filter(self):
        factory = self.replay_flight_data('vpc_security_group_rule_ingress')
        p = self.load_policy({
             'name': 'security-group-rule-ingress',
             'resource': 'huaweicloud.vpc-security-group-rule',
             'filters': [{'type': 'ingress', 'RemoteIpPrefix': '192.168.21.0/24',
                          'Protocols': ['tcp'], 'AllInPorts': [8080]}]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['direction'], 'ingress')
        self.assertEqual(resources[0]['protocol'], 'tcp')
        self.assertEqual(resources[0]['remote_ip_prefix'], '192.168.21.0/24')
        self.assertIn('8080', resources[0]['multiport'])

    def test_security_group_rule_egress_filter(self):
        factory = self.replay_flight_data('vpc_security_group_rule_egress')
        p = self.load_policy({
             'name': 'security-group-rule-egress',
             'resource': 'huaweicloud.vpc-security-group-rule',
             'filters': [{'type': 'egress', 'RemoteIpPrefix': '192.168.21.0/24',
                          'Protocols': ['tcp'], 'AllInPorts': [8080]}]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['direction'], 'egress')
        self.assertEqual(resources[0]['protocol'], 'tcp')
        self.assertEqual(resources[0]['remote_ip_prefix'], '192.168.21.0/24')
        self.assertIn('8080', resources[0]['multiport'])

    def test_security_group_remove_rules_action(self):
        factory = self.replay_flight_data('vpc_security_group_remove_rules')
        p = self.load_policy({
             'name': 'security-group-remove-rules',
             'resource': 'huaweicloud.vpc-security-group-rule',
             'filters': [{'type': 'egress', 'RemoteIpPrefix': '192.168.21.0/24',
                          'Protocols': ['tcp'], 'AllInPorts': [8080]}],
             'actions': [{'type': 'remove-rules', 'egress': 'matched'}]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['direction'], 'egress')
        self.assertEqual(resources[0]['protocol'], 'tcp')
        self.assertEqual(resources[0]['remote_ip_prefix'], '192.168.21.0/24')
        self.assertIn('8080', resources[0]['multiport'])

    def test_security_group_set_rules_action(self):
        factory = self.replay_flight_data('vpc_security_group_set_rules')
        p = self.load_policy({
             'name': 'security-group-set-rules',
             'resource': 'huaweicloud.vpc-security-group-rule',
             'filters': [{'type': 'egress', 'RemoteIpPrefix': '192.168.21.0/24',
                          'Protocols': ['tcp'], 'AllInPorts': [8080]}],
             'actions': [{'type': 'set-rules', 'remove-egress': 'matched',
                          'remove-ingress': [{'protocol': ['tcp'],
                                              'remote_ip_prefix': '192.168.22.0/24'}],
                          'add-ingress': [{'ethertype': 'ipv4', 'protocol': 'tcp',
                                           'multiport': '3389',
                                           'remote_ip_prefix': '192.168.33.25/32'}],
                          'add-egress': [{'ethertype': 'ipv4', 'protocol': 'tcp',
                                          'multiport': '22,3389',
                                          'remote_ip_prefix': '192.168.33.0/24'}]}]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['direction'], 'egress')
        self.assertEqual(resources[0]['protocol'], 'tcp')
        self.assertEqual(resources[0]['remote_ip_prefix'], '192.168.21.0/24')
        self.assertIn('8080', resources[0]['multiport'])
