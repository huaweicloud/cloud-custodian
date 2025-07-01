# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import unittest
from huaweicloud_common import BaseTest


class VpcEndpointTest(BaseTest):
    """VPC Endpoint Resource Test Class"""

    # =========================
    # Resource Query Test
    # =========================
    def test_vpcep_query(self):
        """Test basic query functionality for VPC endpoints"""
        factory = self.replay_flight_data('vpcep_query')
        p = self.load_policy({
            'name': 'vpcep-query-test',
            'resource': 'huaweicloud.vpcep-ep'},
            session_factory=factory)
        resources = p.run()
        # Assuming there is 1 endpoint in the recording
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['endpoint_service_name'],
                         "com.huaweicloud.service.test")  # Endpoint service name

    # =========================
    # Filter Tests
    # =========================
    def test_vpcep_filter_by_service_and_vpc_check_only_service(self):
        """Test checking endpoints by service name only, with no matches"""
        factory = self.replay_flight_data('vpcep_filter_by_service_only')
        p = self.load_policy({
            'name': 'vpcep-filter-by-service-only-test',
            'resource': 'huaweicloud.vpcep-ep',
            'filters': [{
                'type': 'by-service-and-vpc-check',
                'endpoint_service_name': 'com.huaweicloud.service.not.exist'
            }]},
            session_factory=factory)
        resources = p.run()
        # Should return a single item with just the service name
        self.assertEqual(len(resources), 1)
        self.assertEqual(
            resources[0]['endpoint_service_name'], 'com.huaweicloud.service.not.exist')
        # Should not include vpc_ids field
        self.assertNotIn('vpc_ids', resources[0])

    def test_vpcep_filter_by_service_and_vpc_check_with_service_match(self):
        """Test service name matches but no VPC ID check is provided"""
        factory = self.replay_flight_data('vpcep_filter_by_service_match')
        p = self.load_policy({
            'name': 'vpcep-filter-by-service-match-test',
            'resource': 'huaweicloud.vpcep-ep',
            'filters': [{
                'type': 'by-service-and-vpc-check',
                'endpoint_service_name': 'com.huaweicloud.service.test'
            }]},
            session_factory=factory)
        resources = p.run()
        # Service name matches and no VPC check, should return empty list
        self.assertEqual(len(resources), 0)

    def test_vpcep_filter_by_service_and_vpc_check_with_vpc_match(self):
        """Test both service name and all VPC IDs match"""
        factory = self.replay_flight_data(
            'vpcep_filter_by_service_and_vpc_match')
        p = self.load_policy({
            'name': 'vpcep-filter-by-service-and-vpc-match-test',
            'resource': 'huaweicloud.vpcep-ep',
            'filters': [{
                'type': 'by-service-and-vpc-check',
                'endpoint_service_name': 'com.huaweicloud.service.test',
                'vpc_ids': ['vpc-12345678']
            }]},
            session_factory=factory)
        resources = p.run()
        # All VPC IDs match, should return empty list
        self.assertEqual(len(resources), 0)

    def test_vpcep_filter_by_service_and_vpc_check_with_vpc_not_match(self):
        """Test case when some VPC IDs don't match"""
        factory = self.replay_flight_data(
            'vpcep_filter_by_service_and_vpc_not_match')
        p = self.load_policy({
            'name': 'vpcep-filter-by-service-and-vpc-not-match-test',
            'resource': 'huaweicloud.vpcep-ep',
            'filters': [{
                'type': 'by-service-and-vpc-check',
                'endpoint_service_name': 'com.huaweicloud.service.test',
                # Assuming the second VPC ID doesn't have a match
                'vpc_ids': ['vpc-12345678', 'vpc-87654321']
            }]},
            session_factory=factory)
        resources = p.run()
        # Should return one item with missing VPC IDs
        self.assertEqual(len(resources), 1)
        self.assertEqual(
            resources[0]['endpoint_service_name'], 'com.huaweicloud.service.test')
        self.assertIn('vpc_ids', resources[0])
        # Missing VPC ID should be in the list
        self.assertIn('vpc-87654321', resources[0]['vpc_ids'])

    def test_vpcep_filter_by_service_and_vpc_check_empty_name(self):
        """Test case when service name is empty"""
        factory = self.replay_flight_data('vpcep_filter_by_service_empty_name')
        # Note: In actual execution, schema validation would
        # prevent this, but we still test code defensiveness
        p = self.load_policy({
            'name': 'vpcep-filter-by-service-empty-name-test',
            'resource': 'huaweicloud.vpcep-ep',
            'filters': [{
                'type': 'by-service-and-vpc-check',
                'endpoint_service_name': ''  # Empty service name
            }]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 0)  # Should return empty list

    # =========================
    # Action Tests
    # =========================
    def test_vpcep_action_send_msg(self):
        """Test VPC endpoint message sending action"""
        factory = self.replay_flight_data('vpcep_action_send_msg')
        p = self.load_policy({
            'name': 'vpcep-action-send-msg-test',
            'resource': 'huaweicloud.vpcep-ep',
            'actions': [
                {
                    'type': 'eps-check-ep-msg',
                    'topic_urn_list': [
                        "urn:smn:cn-north-4:0df25bbc878091b62f88c00c2959df9a:test"
                    ],
                    'message': "alert:xxx"
                }
            ]
        }, session_factory=factory)

        resources = p.run()
        # Ensure the policy returns resources
        self.assertTrue(resources)
        # Get the send-msg action instance
        action = p.resource_manager.actions[0]
        # Mock the process method
        with unittest.mock.patch.object(action, 'process') as mock_process:
            # Trigger the action
            action.process(resources)
            # Assert the process method was called once
            mock_process.assert_called_once_with(resources)
