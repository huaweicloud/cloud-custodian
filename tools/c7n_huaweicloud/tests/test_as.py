# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

from huaweicloud_common import BaseTest


class AsGroupTest(BaseTest):
    """Auto Scaling Group Resource Test Class"""

    # ==============================
    # Basic Resource Query Tests
    # ==============================
    def test_as_group_query(self):
        """Test the basic query functionality of Auto Scaling Group"""
        factory = self.replay_flight_data('as_group_query')
        p = self.load_policy(
            {'name': 'as-group-query', 'resource': 'huaweicloud.as-group'},
            session_factory=factory
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)  # Assuming 1 resource is returned
        self.assertEqual(
            resources[0]['scaling_group_name'], 'as-group-test')  # Verify resource name

    # ==============================
    # Filter Tests
    # ==============================
    def test_by_image_id_filter(self):
        """Test filtering Auto Scaling Groups by image ID"""
        factory = self.replay_flight_data('as_group_by_image_id')
        p = self.load_policy(
            {
                'name': 'as-group-by-image-id',
                'resource': 'huaweicloud.as-group',
                'filters': [
                    {
                        'type': 'by-image-id',
                        'image_id': '37ca2b35-6fc7-47ab-93c7-900324809c5c'
                    }
                ]
            },
            session_factory=factory
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # Verify that the resource contains the matched image ID marker
        self.assertEqual(
            resources[0]['matched_image_id'],
            '37ca2b35-6fc7-47ab-93c7-900324809c5c'
        )

    def test_instance_deficit_filter(self):
        """Test filter for Auto Scaling Groups with instance deficits"""
        factory = self.replay_flight_data('as_group_instance_deficit')
        p = self.load_policy(
            {
                'name': 'as-group-instance-deficit',
                'resource': 'huaweicloud.as-group',
                'filters': [{'type': 'instance-deficit'}]
            },
            session_factory=factory
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # Verify that the resource contains the instance deficit marker
        self.assertTrue(resources[0]['instance_deficit'])
        # Verify that the current instance count is less than the desired count
        self.assertLess(
            resources[0]['current_instance_number'],
            resources[0]['desire_instance_number']
        )

    def test_by_unencrypted_config_filter(self):
        """Test filter for Auto Scaling Groups using unencrypted configurations"""
        factory = self.replay_flight_data('as_group_by_unencrypted_config')
        p = self.load_policy(
            {
                'name': 'as-group-by-unencrypted-config',
                'resource': 'huaweicloud.as-group',
                'filters': [{'type': 'by-unencrypted-config'}]
            },
            session_factory=factory
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # Verify that the resource contains the unencrypted config marker
        self.assertTrue(resources[0]['unencrypted_config'])

    def test_by_user_data_filter(self):
        """Test filtering Auto Scaling Groups by user data"""
        factory = self.replay_flight_data('as_group_by_user_data')
        p = self.load_policy(
            {
                'name': 'as-group-by-user-data',
                'resource': 'huaweicloud.as-group',
                'filters': [
                    {
                        'type': 'by-user-data',
                        'user_data': 'IyEvYmluL2Jhc2gK'  # Base64 encoded sample user data
                    }
                ]
            },
            session_factory=factory
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # Verify that the resource contains the matched user_data marker
        self.assertTrue(resources[0]['matched_user_data'])

    def test_by_vpc_filter(self):
        """Test filtering Auto Scaling Groups by VPC ID"""
        factory = self.replay_flight_data('as_group_by_vpc')
        p = self.load_policy(
            {
                'name': 'as-group-by-vpc',
                'resource': 'huaweicloud.as-group',
                'filters': [
                    {
                        'type': 'by-vpc',
                        'vpc_id': '7d9055d9-f179-4f4a-b9e6-99a7f9811f8c'
                    }
                ]
            },
            session_factory=factory
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(
            resources[0]['vpc_id'],
            '7d9055d9-f179-4f4a-b9e6-99a7f9811f8c'
        )

    def test_by_network_filter(self):
        """Test filtering Auto Scaling Groups by network ID"""
        factory = self.replay_flight_data('as_group_by_network')
        p = self.load_policy(
            {
                'name': 'as-group-by-network',
                'resource': 'huaweicloud.as-group',
                'filters': [
                    {
                        'type': 'by-network',
                        'network_id': '5d9055d9-f179-4f4a-b9e6-99a7f9811f8c'
                    }
                ]
            },
            session_factory=factory
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # Verify that the network list contains the specified network ID
        network_ids = [n.get('id') for n in resources[0].get('networks', [])]
        self.assertIn('5d9055d9-f179-4f4a-b9e6-99a7f9811f8c', network_ids)

    def test_invalid_resources_filter(self):
        """Test filtering Auto Scaling Groups with invalid resources"""
        factory = self.replay_flight_data('as_group_invalid_resources')
        p = self.load_policy(
            {
                'name': 'as-group-invalid-resources',
                'resource': 'huaweicloud.as-group',
                'filters': [{'type': 'invalid-resources'}]
            },
            session_factory=factory
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # Verify that the resource contains invalid resource markers
        # Since any API exception will mark the resource as invalid,
        # we only need to verify at least one invalid marker exists
        self.assertTrue(
            resources[0].get('has_invalid_subnet') or
            resources[0].get('has_invalid_elb_pool') or
            resources[0].get('has_invalid_security_group')
        )
        # Verify the scaling configuration ID is correct
        self.assertEqual(
            resources[0]['scaling_configuration_id'], 'test-scaling-config-id')

    # ==============================
    # Action Tests
    # ==============================
    def test_delete_action(self):
        """Test delete action for Auto Scaling Group"""
        factory = self.replay_flight_data('as_group_delete')
        p = self.load_policy(
            {
                'name': 'as-group-delete',
                'resource': 'huaweicloud.as-group',
                'filters': [
                    {
                        'type': 'value',
                        'key': 'scaling_group_id',
                        'value': 'test-scaling-group-id'
                    }
                ],
                'actions': [{'type': 'delete', 'force': 'yes'}]
            },
            session_factory=factory
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(
            resources[0]['scaling_group_id'], 'test-scaling-group-id')

    def test_enable_action(self):
        """Test enable action for Auto Scaling Group"""
        factory = self.replay_flight_data('as_group_enable')
        p = self.load_policy(
            {
                'name': 'as-group-enable',
                'resource': 'huaweicloud.as-group',
                'filters': [
                    {
                        'type': 'value',
                        'key': 'scaling_group_status',
                        'value': 'PAUSED'
                    }
                ],
                'actions': [{'type': 'enable'}]
            },
            session_factory=factory
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['scaling_group_status'], 'PAUSED')
        # Verify API call parameters - in actual situations, parameters can be verified via mock
        # Omitted here, only testing if it runs correctly

    def test_disable_action(self):
        """Test disable action for Auto Scaling Group"""
        factory = self.replay_flight_data('as_group_disable')
        p = self.load_policy(
            {
                'name': 'as-group-disable',
                'resource': 'huaweicloud.as-group',
                'filters': [
                    {
                        'type': 'value',
                        'key': 'scaling_group_status',
                        'value': 'INSERVICE'
                    }
                ],
                'actions': [{'type': 'disable'}]
            },
            session_factory=factory
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['scaling_group_status'], 'INSERVICE')
        # Verify API call parameters - in actual situations, parameters can be verified via mock
        # Omitted here, only testing if it runs correctly

    def test_update_action(self):
        """Test update action for Auto Scaling Group"""
        factory = self.replay_flight_data('as_group_update')
        p = self.load_policy(
            {
                'name': 'as-group-update',
                'resource': 'huaweicloud.as-group',
                'filters': [
                    {
                        'type': 'value',
                        'key': 'scaling_group_id',
                        'value': 'test-scaling-group-id'
                    }
                ],
                'actions': [
                    {
                        'type': 'update',
                        'min_instance_number': 1,
                        'max_instance_number': 10,
                        'desire_instance_number': 2
                    }
                ]
            },
            session_factory=factory
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(
            resources[0]['scaling_group_id'], 'test-scaling-group-id')


class AsConfigTest(BaseTest):
    """Auto Scaling Configuration Resource Test Class"""

    # ==============================
    # Basic Resource Query Tests
    # ==============================
    def test_as_config_query(self):
        """Test the basic query functionality of Auto Scaling Configuration"""
        factory = self.replay_flight_data('as_config_query')
        p = self.load_policy(
            {'name': 'as-config-query', 'resource': 'huaweicloud.as-config'},
            session_factory=factory
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(
            resources[0]['scaling_configuration_name'], 'config_name_1')

    # ==============================
    # Filter Tests
    # ==============================
    def test_not_in_use_filter(self):
        """Test filter for unused Auto Scaling Configurations"""
        factory = self.replay_flight_data('as_config_not_in_use')
        p = self.load_policy(
            {
                'name': 'as-config-not-in-use',
                'resource': 'huaweicloud.as-config',
                'filters': [{'type': 'not-in-use'}]
            },
            session_factory=factory
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # Verify resource is marked as not in use
        self.assertFalse(resources[0]['in_use'])

    def test_age_filter(self):
        """Test the age filter for Auto Scaling Configurations"""
        factory = self.replay_flight_data('as_config_age')
        # Test scaling configurations older than 90 days
        p = self.load_policy(
            {
                'name': 'as-config-age',
                'resource': 'huaweicloud.as-config',
                'filters': [{'type': 'age', 'days': 90, 'op': 'gt'}]
            },
            session_factory=factory
        )
        resources = p.run()
        # Assuming 1 resource meets the condition
        self.assertEqual(len(resources), 1)

    # ==============================
    # Action Tests
    # ==============================
    def test_delete_action(self):
        """Test delete action for Auto Scaling Configuration"""
        factory = self.replay_flight_data('as_config_delete')
        p = self.load_policy(
            {
                'name': 'as-config-delete',
                'resource': 'huaweicloud.as-config',
                'filters': [
                    {
                        'type': 'value',
                        'key': 'scaling_configuration_id',
                        'value': 'test-scaling-configuration-id'
                    }
                ],
                'actions': [{'type': 'delete'}]
            },
            session_factory=factory
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertTrue(
            resources[0]['scaling_configuration_id'], 'test-scaling-configuration-id')


class AsPolicyTest(BaseTest):

    # ==============================
    # Basic Resource Query Tests
    # ==============================
    def test_as_config_query(self):
        """Test the basic query policy"""
        factory = self.replay_flight_data('as_policy_query')
        p = self.load_policy(
            {'name': 'as-policy-query', 'resource': 'huaweicloud.as-policy'},
            session_factory=factory
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(
            resources[0]['scaling_policy_name'], 'as-policy-7a75')
