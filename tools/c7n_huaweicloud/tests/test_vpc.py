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

    def test_security_group_without_specific_tags(self):
        factory = self.replay_flight_data('vpc_security_group_without_specific_tags')
        p = self.load_policy({
                'name': 'security-groups-without-specific-tags',
                'resource': 'huaweicloud.vpc-security-group',
                'filters': [{'type': 'without_specific_tags',
                             'keys': ['owner-team-email', 'tech-team-email'],
                             'associate_type': 'any'}]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)

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


class FlowLogTest(BaseTest):

    def test_flow_log_set_flow_log_action(self):
        factory = self.replay_flight_data('vpc_flow_log_set_flow_log')
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


class PortTest(BaseTest):
    def test_port_disable_port_forwarding(self):
        factory = self.replay_flight_data('vpc_port_disable_port_forwarding')
        p = self.load_policy({
             'name': 'disable-port-forwarding',
             'resource': 'huaweicloud.vpc-port',
             'filters': ['port-forwarding'],
             'actions': ['disable-port-forwarding']},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertNotEqual(len(resources[0]['allowed_address_pairs']), 0)
        pairs = resources[0]['allowed_address_pairs']
        self.assertEqual(pairs[0]['ip_address'], '1.1.1.1/0')


class PeeringTest(BaseTest):
    def test_peering_cross_account(self):
        factory = self.replay_flight_data('vpc_peering_cross_account')
        p = self.load_policy({
            'name': 'vpc-peering-cross-account',
            'resource': 'huaweicloud.vpc-peering',
            'filters': ['cross-account'],
            'actions': ['delete']},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)

    def test_peering_missing_route(self):
        factory = self.replay_flight_data('vpc_peering_missing_route')
        p = self.load_policy({
            'name': 'vpc-peering-missing-route',
            'resource': 'huaweicloud.vpc-peering',
            'filters': ['missing-route'],
            'actions': ['delete']},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
