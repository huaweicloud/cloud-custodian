# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from unittest.mock import patch  # Import patch

from huaweicloud_common import BaseTest


class RocketMQInstanceTest(BaseTest):

    # =========================
    # Resource Query Test
    # =========================
    def test_rocketmq_query(self):
        factory = self.replay_flight_data('rocketmq_query')
        p = self.load_policy({
            'name': 'rocketmq-query-test',
            'resource': 'huaweicloud.reliability'},
            session_factory=factory)
        resources = p.run()
        # Assuming there is 1 instance in the recording
        self.assertEqual(len(resources), 1)

    # =========================
    # Filter Tests
    # =========================
    # Specify the target to mock
    @patch('c7n_huaweicloud.resources.vpc.SecurityGroup.get_resources')
    # Receive mock object
    def test_rocketmq_filter_security_group(self, mock_get_sg_resources):
        # Configure mock return value
        # Need to include an id that matches the securityGroupId in VCR
        mock_security_group_data = [{
            'id': 'securityGroupId',
            'name': 'rocket-mq-test-sg',  # Name can come from VCR, just ensure the id matches
            'description': 'Mocked security group data',
            # Can add more fields as needed, but 'id' is key
        }]
        mock_get_sg_resources.return_value = mock_security_group_data

        factory = self.replay_flight_data('rocketmq_filter_sg')
        p = self.load_policy({
            'name': 'rocketmq-filter-sg-test',
            'resource': 'huaweicloud.reliability',
            'filters': [{
                'type': 'security-group',
                'key': 'id',  # or name
                'value': 'securityGroupId'  # Ensure this value matches the id in mock data
            }]},
            session_factory=factory)
        resources = p.run()
        # Assuming there is 1 matching instance
        self.assertEqual(len(resources), 1)
        # Verify that the mock was called (optional)
        mock_get_sg_resources.assert_called_once_with(['securityGroupId'])

    def test_rocketmq_filter_age(self):
        factory = self.replay_flight_data('rocketmq_filter_age')

        # Test if age > threshold (1 day)
        # Most RocketMQ instances should be at least 1 day old
        p_gt = self.load_policy({
            'name': 'rocketmq-filter-age-gt-test',
            'resource': 'huaweicloud.reliability',
            'filters': [{'type': 'age', 'days': 1, 'op': 'gt'}]  # Age > 1 day
        }, session_factory=factory)
        resources_gt = p_gt.run()
        # Should find one resource (instance age > 1 day)
        self.assertEqual(len(resources_gt), 1)

        # Test if age < very large threshold (10000 days)
        # All instances should be younger than 10000 days
        p_lt = self.load_policy({
            'name': 'rocketmq-filter-lt-test',
            'resource': 'huaweicloud.reliability',
            # Age < 10000 days
            'filters': [{'type': 'age', 'days': 10000, 'op': 'lt'}]
        }, session_factory=factory)
        resources_lt = p_lt.run()
        # Should find one resource (age < 10000 days)
        self.assertEqual(len(resources_lt), 1)

    def test_rocketmq_filter_list_item(self):
        factory = self.replay_flight_data('rocketmq_filter_list_item')
        # Test if in one of the specified availability zones - using value filter
        p = self.load_policy({
            'name': 'rocketmq-filter-az-test',
            'resource': 'huaweicloud.reliability',
            'filters': [{
                'type': 'value',
                'key': 'available_zones',
                'op': 'contains',
                'value': 'cn-north-4a'
            }]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)  # Should find one instance

        # Test using array value
        p_array = self.load_policy({
            'name': 'rocketmq-filter-az-array-test',
            'resource': 'huaweicloud.reliability',
            'filters': [{
                'type': 'value',
                'key': 'available_zones',
                'op': 'intersect',
                'value': ['cn-north-4a', 'cn-north-4b']
            }]},
            session_factory=factory)
        resources_array = p_array.run()
        self.assertEqual(len(resources_array), 1)  # Should find one instance

        # Test no match case
        p_no_match = self.load_policy({
            'name': 'rocketmq-filter-az-no-match-test',
            'resource': 'huaweicloud.reliability',
            'filters': [{
                'type': 'value',
                'key': 'available_zones',
                'op': 'contains',
                'value': 'cn-north-99'  # Non-existent availability zone
            }]},
            session_factory=factory)
        resources_no_match = p_no_match.run()
        # Should not find any instance
        self.assertEqual(len(resources_no_match), 0)

    def test_rocketmq_filter_marked_for_op(self):
        # Need a recording with an instance tagged with 'mark-for-op-custodian' or custom tag
        factory = self.replay_flight_data('rocketmq_filter_marked_for_op')
        # Using value filter to search tag keys in tags list as HuaweiCloud tags are in list format
        p = self.load_policy({
            'name': 'rocketmq-filter-tag-exists-test',
            'resource': 'huaweicloud.reliability',
            'filters': [{
                'type': 'value',
                'key': 'tags[].key',
                'value': 'custodian_cleanup',
                'op': 'contains'
            }]},
            session_factory=factory)
        resources = p.run()
        # Assuming there is 1 matching instance
        self.assertEqual(len(resources), 1)

        # Edge case: test tag not match
        p_wrong_tag = self.load_policy({
            'name': 'rocketmq-filter-wrong-tag-test',
            'resource': 'huaweicloud.reliability',
            'filters': [{
                'type': 'value',
                'key': 'tags[].key',
                'value': 'non_existent_tag',
                'op': 'contains'
            }]},
            session_factory=factory)
        resources_wrong_tag = p_wrong_tag.run()
        self.assertEqual(len(resources_wrong_tag), 0)

    # =========================
    # Action Tests
    # =========================
    def test_rocketmq_action_mark_for_op(self):
        factory = self.replay_flight_data('rocketmq_action_mark')
        p = self.load_policy({
            'name': 'rocketmq-action-mark-test',
            'resource': 'huaweicloud.reliability',
            'actions': [{
                'type': 'mark-for-op',
                'op': 'delete',
                'tag': 'custodian_cleanup',
                'days': 7
            }]},
            session_factory=factory)
        resources = p.run()
        # Assuming action was performed on 1 instance
        self.assertEqual(len(resources), 1)
        # Verification: confirm batch_create_or_delete_rocketmq_tag was called
        # and request body contains correct tag key and value (with timestamp)

    def test_rocketmq_action_tag(self):
        factory = self.replay_flight_data('rocketmq_action_tag')
        p = self.load_policy({
            'name': 'rocketmq-action-tag-test',
            'resource': 'huaweicloud.reliability',
            'actions': [{'type': 'tag', 'key': 'CostCenter', 'value': 'Finance'}]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # Verification: confirm batch_create_or_delete_rocketmq_tag was called (action=create)
        # and body.tags contains {'key': 'CostCenter', 'value': 'Finance'}

    def test_rocketmq_action_remove_tag(self):
        factory = self.replay_flight_data('rocketmq_action_remove_tag')
        p = self.load_policy({
            'name': 'rocketmq-action-remove-tag-test',
            'resource': 'huaweicloud.reliability',
            'actions': [{'type': 'remove-tag', 'tags': ['environment', 'temp-tag']}]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)

    def test_rocketmq_action_rename_tag(self):
        factory = self.replay_flight_data('rocketmq_action_rename_tag')
        p = self.load_policy({
            'name': 'rocketmq-action-rename-tag-test',
            'resource': 'huaweicloud.reliability',
            'actions': [{'type': 'rename-tag', 'old_key': 'env', 'new_key': 'Environment'}]
            },
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)

    def test_rocketmq_action_delete(self):
        factory = self.replay_flight_data('rocketmq_action_delete')
        p = self.load_policy({
            'name': 'rocketmq-action-delete-test',
            'resource': 'huaweicloud.reliability',
            'actions': ['delete']},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # Verification: check VCR, confirm delete_instance API was called
