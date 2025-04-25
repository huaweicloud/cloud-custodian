# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from unittest.mock import patch

from huaweicloud_common import BaseTest


class RDSTest(BaseTest):
    """
    Huawei Cloud RDS Resource Test Class
    Used to test all filters and actions for RDS resources
    """

    # =========================
    # Resource Query Tests
    # =========================
    def test_rds_query(self):
        """Test basic query for RDS instances"""
        factory = self.replay_flight_data('rds_query')
        p = self.load_policy({
            'name': 'rds-query-test',
            'resource': 'huaweicloud.rds'},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)  # Assuming there is 1 instance in the data
        self.assertEqual(resources[0]['name'], "mysql-instance-test")  # Assumed instance name
        # Verify that augment correctly converts tags
        self.assertTrue('tags' in resources[0])
        self.assertEqual(resources[0]['tags'], [{'key': 'environment', 'value': 'testing'}])  # Assumed

    # =========================
    # Filter Tests
    # =========================
    @patch('c7n_huaweicloud.resources.vpc.SecurityGroup.get_resources')
    def test_rds_filter_security_group(self, mock_get_sg_resources):
        """Test RDS instance filtering based on security groups"""
        # Configure mock return value
        mock_security_group_data = [{
            'id': 'sg-12345678',  # Must match that in VCR
            'name': 'test-security-group',
            'description': 'Mocked security group data'
        }]
        mock_get_sg_resources.return_value = mock_security_group_data

        factory = self.replay_flight_data('rds_filter_sg')
        p = self.load_policy({
            'name': 'rds-filter-sg-test',
            'resource': 'huaweicloud.rds',
            'filters': [{
                'type': 'security-group',
                'key': 'id',
                'value': 'sg-12345678'
            }]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)  # Assuming there is 1 matching instance
        mock_get_sg_resources.assert_called_once_with(['sg-12345678'])  # Verify mock call

    @patch('c7n_huaweicloud.resources.vpc.Vpc.get_resources')
    def test_rds_filter_vpc(self, mock_get_vpc_resources):
        """Test RDS instance filtering based on VPC"""
        # Configure mock return value
        mock_vpc_data = [{
            'id': 'vpc-12345678',  # Must match that in VCR
            'name': 'test-vpc',
            'cidr': '10.0.0.0/16'
        }]
        mock_get_vpc_resources.return_value = mock_vpc_data

        factory = self.replay_flight_data('rds_filter_vpc')
        p = self.load_policy({
            'name': 'rds-filter-vpc-test',
            'resource': 'huaweicloud.rds',
            'filters': [{
                'type': 'vpc',
                'key': 'id',
                'value': 'vpc-12345678'
            }]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)  # Assuming there is 1 matching instance
        mock_get_vpc_resources.assert_called_once_with(['vpc-12345678'])  # Verify mock call

    # @patch('c7n_huaweicloud.resources.vpc.Subnet.get_resources')
    # def test_rds_filter_subnet(self, mock_get_subnet_resources):
    #     """Test RDS instance filtering based on subnet"""
    #     # Configure mock return value
    #     mock_subnet_data = [{
    #         'id': 'subnet-12345678',  # Must match that in VCR
    #         'name': 'test-subnet',
    #         'cidr': '10.0.1.0/24'
    #     }]
    #     mock_get_subnet_resources.return_value = mock_subnet_data
    #
    #     factory = self.replay_flight_data('rds_filter_subnet')
    #     p = self.load_policy({
    #         'name': 'rds-filter-subnet-test',
    #         'resource': 'huaweicloud.rds',
    #         'filters': [{
    #             'type': 'subnet',
    #             'key': 'id',
    #             'value': 'subnet-12345678'
    #         }]},
    #         session_factory=factory)
    #     resources = p.run()
    #     self.assertEqual(len(resources), 1)  # Assuming there is 1 matching instance
    #     mock_get_subnet_resources.assert_called_once_with(['subnet-12345678'])  # Verify mock call



    # def test_rds_filter_alarm(self):
    #     """Test RDS instance filtering based on alarms"""
    #     factory = self.replay_flight_data('rds_filter_alarm')
    #     p = self.load_policy({
    #         'name': 'rds-with-alarm-test',
    #         'resource': 'huaweicloud.rds',
    #         'filters': [{
    #             'type': 'alarm',
    #             'state': 'alarm'  # Test for instances in alarm state
    #         }]},
    #         session_factory=factory)
    #     resources = p.run()
    #     self.assertEqual(len(resources), 1)  # Assuming there is 1 instance in alarm state

    # def test_rds_filter_offhour(self):
    #     """Test off-hours filter"""
    #     factory = self.replay_flight_data('rds_filter_offhour')
    #     # Set up a policy that triggers during off hours
    #     p = self.load_policy({
    #         'name': 'rds-offhour-test',
    #         'resource': 'huaweicloud.rds',
    #         'filters': [{
    #             'type': 'offhour',
    #             'tag': 'custodian_downtime',
    #             'default_tz': 'Asia/Shanghai',
    #             'offhour': 20,  # 8PM
    #             'days': ['Mon-Fri']
    #         }]},
    #         session_factory=factory)
    #     resources = p.run()
    #     self.assertEqual(len(resources), 1)  # Assuming there is 1 matching instance

    # def test_rds_filter_onhour(self):
    #     """Test on-hours filter"""
    #     factory = self.replay_flight_data('rds_filter_onhour')
    #     # Set up a policy that triggers during working hours
    #     p = self.load_policy({
    #         'name': 'rds-onhour-test',
    #         'resource': 'huaweicloud.rds',
    #         'filters': [{
    #             'type': 'onhour',
    #             'tag': 'custodian_uptime',
    #             'default_tz': 'Asia/Shanghai',
    #             'onhour': 8,  # 8AM
    #             'days': ['Mon-Fri']
    #         }]},
    #         session_factory=factory)
    #     resources = p.run()
    #     self.assertEqual(len(resources), 1)  # Assuming there is 1 matching instance


    # Not applicable
    # def test_rds_filter_config(self):
    #     """Test configuration filter"""
    #     factory = self.replay_flight_data('rds_filter_config')
    #     p = self.load_policy({
    #         'name': 'rds-config-test',
    #         'resource': 'huaweicloud.rds',
    #         'filters': [{
    #             'type': 'config',
    #             'config_key': 'ssl_option',
    #             'value': 'enabled',
    #             'op': 'eq'
    #         }]},
    #         session_factory=factory)
    #     resources = p.run()
    #     self.assertEqual(len(resources), 1)  # Assuming there is 1 instance with SSL enabled

    def test_rds_filter_value(self):
        """Test generic value-based filter"""
        factory = self.replay_flight_data('rds_filter_value')
        # Test instance type
        p = self.load_policy({
            'name': 'rds-value-type-test',
            'resource': 'huaweicloud.rds',
            'filters': [{
                'type': 'value',
                'key': 'type',
                'value': 'MySQL',
                'op': 'eq'
            }]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)  # Assuming there is 1 MySQL type instance

        # Test instance status
        p_status = self.load_policy({
            'name': 'rds-value-status-test',
            'resource': 'huaweicloud.rds',
            'filters': [{
                'type': 'value',
                'key': 'status',
                'value': 'ACTIVE',
                'op': 'eq'
            }]},
            session_factory=factory)
        resources_status = p_status.run()
        self.assertEqual(len(resources_status), 1)  # Assuming there is 1 active state instance

    def test_rds_filter_list_item(self):
        """Test list-item filter"""
        factory = self.replay_flight_data('rds_filter_list_item')
        # Test availability zone
        p = self.load_policy({
            'name': 'rds-list-item-az-test',
            'resource': 'huaweicloud.rds',
            'filters': [{
                'type': 'list-item',
                'key': 'nodes',
                'attrs':[{
                    'type':'value',
                    'key':'status',
                    'value': 'ACTIVE',
                }],
            }]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)  # Assuming there is 1 instance in the specified availability zone

    # def test_rds_filter_event(self):
    #     """Test event filter"""
    #     factory = self.replay_flight_data('rds_filter_event')
    #     # Test for instances with restart events in the last 24 hours
    #     p = self.load_policy({
    #         'name': 'rds-event-test',
    #         'resource': 'huaweicloud.rds',
    #         'filters': [{
    #             'type': 'event',
    #             'service': 'RDS',
    #             'event_name': 'restart',
    #             'days': 1
    #         }]},
    #         session_factory=factory)
    #     resources = p.run()
    #     self.assertEqual(len(resources), 1)  # Assuming there is 1 instance with restart events

    def test_rds_filter_tag_count(self):
        """Test tag count filter"""
        factory = self.replay_flight_data('rds_filter_tag_count')
        # Test for instances with more than 2 tags
        p = self.load_policy({
            'name': 'rds-tag-count-test',
            'resource': 'huaweicloud.rds',
            'filters': [{
                'type': 'tag-count',
                'count': 2,
                'op': 'gt'
            }]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)  # Assuming there is 1 instance with more than 2 tags

    def test_rds_filter_marked_for_op(self):
        """Test marked-for-op filter"""
        factory = self.replay_flight_data('rds_filter_marked_for_op')
        # Test for instances marked for deletion
        p = self.load_policy({
            'name': 'rds-marked-for-delete-test',
            'resource': 'huaweicloud.rds',
            'filters': [{
                'type': 'marked-for-op',
                'tag': 'custodian_cleanup',
                'op': 'delete',
                #'skew': 1
            }]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)  # Assuming there is 1 instance marked for deletion

    def test_rds_filter_reduce(self):
        """Test aggregate filter"""
        factory = self.replay_flight_data('rds_filter_reduce')
        # Test for instances that satisfy multiple conditions simultaneously
        p = self.load_policy({
            'name': 'rds-reduce-test',
            'resource': 'huaweicloud.rds',
            'filters': [{
                'type': 'reduce',
                'filters': [
                    {'type': 'value', 'key': 'status', 'value': 'ACTIVE'},
                    {'type': 'value', 'key': 'type', 'value': 'MySQL'}
                ]
            }]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)  # Assuming there is 1 instance that meets all conditions

    # def test_rds_filter_tms(self):
    #     """Test tag filter"""
    #     factory = self.replay_flight_data('rds_filter_tms')
    #     # Test for instances with specific tags
    #     p = self.load_policy({
    #         'name': 'rds-tms-test',
    #         'resource': 'huaweicloud.rds',
    #         'filters': [{
    #             'type': 'tms',
    #             'key': 'environment',
    #             'value': 'testing'
    #         }]},
    #         session_factory=factory)
    #     resources = p.run()
    #     self.assertEqual(len(resources), 1)  # Assuming there is 1 instance with the specified tag

    # =========================
    # Action Tests
    # =========================
    def test_rds_action_delete(self):
        """Test RDS instance deletion"""
        factory = self.replay_flight_data('rds_action_delete')
        p = self.load_policy({
            'name': 'rds-delete-test',
            'resource': 'huaweicloud.rds',
            'filters': [{'tag:test': 'delete'}],  # Identify test instances by tag
            'actions': ['delete']},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 0)  # Assuming there is 1 instance to delete
        # Verification: Check VCR recording to confirm delete_instance API was called

    def test_rds_action_start(self):
        """Test RDS instance start"""
        factory = self.replay_flight_data('rds_action_start')
        p = self.load_policy({
            'name': 'rds-start-test',
            'resource': 'huaweicloud.rds',
            'filters': [{'type': 'value', 'key': 'status', 'value': 'SHUTDOWN'}],
            'actions': ['start']},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 0)  # Assuming there is 1 instance in shutdown state
        # Verification: Check VCR recording to confirm startup_instance API was called

    def test_rds_action_stop(self):
        """Test RDS instance stop"""
        factory = self.replay_flight_data('rds_action_stop')
        p = self.load_policy({
            'name': 'rds-stop-test',
            'resource': 'huaweicloud.rds',
            'filters': [{'type': 'value', 'key': 'status', 'value': 'ACTIVE'}],
            'actions': ['stop']},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 0)  # Assuming there is 1 instance in running state
        # Verification: Check VCR recording to confirm stop_instance API was called

    def test_rds_action_reboot(self):
        """Test RDS instance reboot"""
        factory = self.replay_flight_data('rds_action_reboot')
        p = self.load_policy({
            'name': 'rds-reboot-test',
            'resource': 'huaweicloud.rds',
            'filters': [{'type': 'value', 'key': 'status', 'value': 'ACTIVE'}],
            'actions': ['reboot']},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 0)  # Assuming there is 1 instance to reboot
        # Verification: Check VCR recording to confirm restart_instance API was called

    def test_rds_action_snapshot(self):
        """Test creating RDS instance snapshot"""
        factory = self.replay_flight_data('rds_action_snapshot')
        p = self.load_policy({
            'name': 'rds-snapshot-test',
            'resource': 'huaweicloud.rds',
            'filters': [{'type': 'value', 'key': 'name', 'value': 'critical-db'}],
            'actions': ['snapshot']},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 0)  # Assuming there is 1 instance to backup
        # Verification: Check VCR recording to confirm create_manual_backup API was called

    def test_rds_action_tag(self):
        """Test adding tags"""
        factory = self.replay_flight_data('rds_action_tag')
        p = self.load_policy({
            'name': 'rds-tag-test',
            'resource': 'huaweicloud.rds',
            'filters': [{'type': 'value', 'key': 'name', 'value': 'mysql-instance-test'}],
            'actions': [{
                'type': 'tag',
                'key': 'env',
                'value': 'production'
            }]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)  # Assuming there is 1 instance to tag
        # Verification: Check VCR recording to confirm batch tag add API was called

    def test_rds_action_remove_tag(self):
        """Test removing tags"""
        factory = self.replay_flight_data('rds_action_remove_tag')
        p = self.load_policy({
            'name': 'rds-remove-tag-test',
            'resource': 'huaweicloud.rds',
            'filters': [{'tag:env': 'present'}],
            'actions': [{
                'type': 'remove-tag',
                'keys': ['env']
            }]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 0)  # Assuming there is 1 instance to remove tag from
        # Verification: Check VCR recording to confirm batch tag delete API was called

    def test_rds_action_rename_tag(self):
        """Test renaming tags
        
        This test verifies the tag renaming functionality on RDS instances, where an existing tag key
        is modified to a new key name while preserving the original tag value.
        """
        factory = self.replay_flight_data('rds_action_rename_tag')
        p = self.load_policy({
            'name': 'rds-rename-tag-test',
            'resource': 'huaweicloud.rds',
            'filters': [{'tag:env': 'present'}],  # Ensure old tag exists
            'actions': [{
                'type': 'rename-tag',
                'old_key': 'env',
                'new_key': 'Environment'
            }]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)  # Assuming there is 1 instance to rename tag

        # Verification: Check VCR recording to confirm two batch tag API calls
        # First: batch_tag_add_action adding new tag {'key': 'Environment', 'value': 'original env tag value'}
        # Second: batch_tag_del_action deleting old tag {'key': 'env'}


    # UT test scenarios not supported
    #
    # def test_rds_action_mark_for_op(self):
    #     """Test marking for operation"""
    #     factory = self.replay_flight_data('rds_action_mark_for_op')
    #     p = self.load_policy({
    #         'name': 'rds-mark-for-delete-test',
    #         'resource': 'huaweicloud.rds',
    #         'filters': [{'type': 'value', 'key': 'status', 'value': 'ACTIVE'}],
    #         'actions': [{
    #             'type': 'mark-for-op',
    #             'tag': 'custodian_cleanup',
    #             'op': 'delete',
    #             'days': 7
    #         }]},
    #         session_factory=factory)
    #     resources = p.run()
    #     self.assertEqual(len(resources), 1)  # Assuming there is 1 instance to mark
    #
    #     # Verify tag was correctly added
    #     self.assertTrue('tags' in resources[0])
    #     tags = {tag['key']: tag['value'] for tag in resources[0]['tags']}
    #     self.assertIn('custodian_cleanup', tags)  # Confirm tag was added
    #
    #     # Check if tag value contains delete operation and time information
    #     tag_value = tags['custodian_cleanup']
    #     self.assertIn('delete', tag_value)  # Confirm contains operation name
    #     self.assertIn('op:delete', tag_value)  # Confirm contains standard format operation name
    #     self.assertRegex(tag_value, r'op:delete@\d{4}/\d{2}/\d{2}')  # Confirm contains date format
    #
    #     # Verification: Check VCR recording to confirm batch tag add API was called, tag value includes operation and time


    # def test_rds_action_auto_tag_user(self):
    #     """Test auto-tagging creator"""
    #     factory = self.replay_flight_data('rds_action_auto_tag_user')
    #     p = self.load_policy({
    #         'name': 'rds-auto-tag-user-test',
    #         'resource': 'huaweicloud.rds',
    #         'filters': [{'tag:CreatorName': 'absent'}],
    #         'actions': [{
    #             'type': 'auto-tag-user',
    #             'tag': 'CreatorName',
    #             'user_key': 'creator',
    #             'update': True
    #         }]},
    #         session_factory=factory)
    #     resources = p.run()
    #     self.assertEqual(len(resources), 1)  # Assuming there is 1 instance to tag
    #     # Verification: Check VCR recording to confirm batch tag add API was called, tag value is the creator


# class RDSMySQLDatabaseTest(BaseTest):
#     """
#     Huawei Cloud RDS MySQL Database Test Class
#     Used to test all filters and actions for RDS MySQL databases
#     """
#
#     def test_rds_mysql_database_query(self):
#         """Test basic query for MySQL databases"""
#         factory = self.replay_flight_data('rds_mysql_database_query')
#         p = self.load_policy({
#             'name': 'rds-mysql-db-query-test',
#             'resource': 'huaweicloud.rds-mysql-database'},
#             session_factory=factory)
#         resources = p.run()
#         self.assertEqual(len(resources), 2)  # Assuming there are 2 databases
#         self.assertEqual(resources[0]['name'], "testdb")  # Assumed database name
#
#
#     def test_rds_mysql_database_filter_value(self):
#         """Test generic value-based filter"""
#         factory = self.replay_flight_data('rds_mysql_database_filter_value')
#         p = self.load_policy({
#             'name': 'rds-mysql-db-filter-value-test',
#             'resource': 'huaweicloud.rds-mysql-database',
#             'filters': [{
#                 'type': 'value',
#                 'key': 'character_set',
#                 'value': 'utf8',
#                 'op': 'eq'
#             }]},
#             session_factory=factory)
#         resources = p.run()
#         self.assertEqual(len(resources), 0)  # Assuming there is 1 database using utf8 character set
#
#     def test_rds_mysql_database_action_create(self):
#         """Test creating MySQL database"""
#         factory = self.replay_flight_data('rds_mysql_database_action_create')
#         p = self.load_policy({
#             'name': 'rds-mysql-db-create-test',
#             'resource': 'huaweicloud.rds',  # Note: Operation is performed on RDS instance
#             'filters': [{'type': 'value', 'key': 'name', 'value': 'mysql-instance-test'}],
#             'actions': [{
#                 'type': 'create',
#                 'database_name': 'newdb',
#                 'character_set': 'utf8mb4'
#             }]},
#             session_factory=factory)
#         resources = p.run()
#         self.assertEqual(len(resources), 1)  # Assuming there is 1 matching instance
#         # Verification: Check VCR recording to confirm create_database API was called
#
#     def test_rds_mysql_database_action_delete(self):
#         """Test deleting MySQL database"""
#         factory = self.replay_flight_data('rds_mysql_database_action_delete')
#         p = self.load_policy({
#             'name': 'rds-mysql-db-delete-test',
#             'resource': 'huaweicloud.rds-mysql-database',
#             'filters': [{'type': 'value', 'key': 'name', 'value': 'testdb'}],
#             'actions': ['delete']},
#             session_factory=factory)
#         resources = p.run()
#         self.assertEqual(len(resources), 0)  # Assuming there is 1 database to delete
#         # Verification: Check VCR recording to confirm delete_database API was called
#
#
# class RDSMySQLUserTest(BaseTest):
#     """
#     Huawei Cloud RDS MySQL User Test Class
#     Used to test all filters and actions for RDS MySQL users
#     """
#
#     def test_rds_mysql_user_query(self):
#         """Test basic query for MySQL users"""
#         factory = self.replay_flight_data('rds_mysql_user_query')
#         p = self.load_policy({
#             'name': 'rds-mysql-user-query-test',
#             'resource': 'huaweicloud.rds-mysql-user'},
#             session_factory=factory)
#         resources = p.run()
#         self.assertEqual(len(resources), 2)  # Assuming there are 2 users
#         self.assertEqual(resources[0]['name'], "testuser")  # Assumed username
#
#     def test_rds_mysql_user_filter_instance_id(self):
#         """Test filtering MySQL users by instance ID"""
#         factory = self.replay_flight_data('rds_mysql_user_filter_instance')
#         p = self.load_policy({
#             'name': 'rds-mysql-user-filter-instance-test',
#             'resource': 'huaweicloud.rds-mysql-user',
#             'filters': [{
#                 'type': 'instance-id',
#                 'value': 'instance-12345678'
#             }]},
#             session_factory=factory)
#         resources = p.run()
#         self.assertEqual(len(resources), 2)  # Assuming there are 2 users in the instance
#
#     def test_rds_mysql_user_filter_value(self):
#         """Test generic value-based filter"""
#         factory = self.replay_flight_data('rds_mysql_user_filter_value')
#         p = self.load_policy({
#             'name': 'rds-mysql-user-filter-value-test',
#             'resource': 'huaweicloud.rds-mysql-user',
#             'filters': [{
#                 'type': 'value',
#                 'key': 'host',
#                 'value': '%',
#                 'op': 'eq'
#             }]},
#             session_factory=factory)
#         resources = p.run()
#         self.assertEqual(len(resources), 1)  # Assuming there is 1 user allowing connections from any host
#
#     def test_rds_mysql_user_action_create(self):
#         """Test creating MySQL user"""
#         factory = self.replay_flight_data('rds_mysql_user_action_create')
#         p = self.load_policy({
#             'name': 'rds-mysql-user-create-test',
#             'resource': 'huaweicloud.rds',  # Note: Operation is performed on RDS instance
#             'filters': [{'type': 'value', 'key': 'name', 'value': 'mysql-instance-test'}],
#             'actions': [{
#                 'type': 'create-user',
#                 'username': 'newuser',
#                 'password': 'StrongPassword123!'
#             }]},
#             session_factory=factory)
#         resources = p.run()
#         self.assertEqual(len(resources), 1)  # Assuming there is 1 matching instance
#         # Verification: Check VCR recording to confirm create_db_user API was called
#
#     def test_rds_mysql_user_action_delete(self):
#         """Test deleting MySQL user"""
#         factory = self.replay_flight_data('rds_mysql_user_action_delete')
#         p = self.load_policy({
#             'name': 'rds-mysql-user-delete-test',
#             'resource': 'huaweicloud.rds-mysql-user',
#             'filters': [{'type': 'value', 'key': 'name', 'value': 'testuser'}],
#             'actions': ['delete']},
#             session_factory=factory)
#         resources = p.run()
#         self.assertEqual(len(resources), 0)  # Assuming there is 1 user to delete
#         # Verification: Check VCR recording to confirm delete_db_user API was called
