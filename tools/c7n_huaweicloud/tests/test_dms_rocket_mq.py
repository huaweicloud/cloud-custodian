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
            'resource': 'huaweicloud.reliabilitys'},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)  # Assuming there is 1 instance in the recording

    # =========================
    # Filter Tests
    # =========================
    @patch('c7n_huaweicloud.resources.vpc.SecurityGroup.get_resources')  # Specify the target to mock
    def test_rocketmq_filter_security_group(self, mock_get_sg_resources):  # Receive mock object
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
            'resource': 'huaweicloud.reliabilitys',
            'filters': [{
                'type': 'security-group',
                'key': 'id',  # or name
                'value': 'securityGroupId'  # Ensure this value matches the id in mock data
            }]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)  # Assuming there is 1 matching instance
        # Verify that the mock was called (optional)
        mock_get_sg_resources.assert_called_once_with(['securityGroupId'])

    def test_rocketmq_filter_age(self):
        factory = self.replay_flight_data('rocketmq_filter_age')
        
        # Test if creation time > threshold time (2022, this should be true because the instance was created in 2023)
        p_gt = self.load_policy({
            'name': 'rocketmq-filter-age-gt-test',
            'resource': 'huaweicloud.reliabilitys',
            'filters': [{'type': 'age', 'days': 1000, 'op': 'gt'}]
            }, session_factory=factory)
        resources_gt = p_gt.run()
        self.assertEqual(len(resources_gt), 1)  # Should find one resource (2023 > threshold 2022)
        
        # Test if creation time < threshold date (for future dates, this is always true)
        p_future = self.load_policy({
            'name': 'rocketmq-filter-future-test',
            'resource': 'huaweicloud.reliabilitys',
            'filters': [{'type': 'age', 'days': -1000, 'op': 'lt'}]  # Creation time < future date
            }, session_factory=factory)
        resources_future = p_future.run()
        self.assertEqual(len(resources_future), 1)  # Should find one resource (past time < future date)

    def test_rocketmq_filter_list_item(self):
        factory = self.replay_flight_data('rocketmq_filter_list_item')
        # Test if in one of the specified availability zones - using value filter
        p = self.load_policy({
            'name': 'rocketmq-filter-az-test',
            'resource': 'huaweicloud.reliabilitys',
            'filters': [{
                'type': 'list-item',
                'key': 'available_zones',
                'op': 'in',
                'value': 'cn-north-4a'
            }]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)  # Should find one instance
        
        # Test using array value
        p_array = self.load_policy({
            'name': 'rocketmq-filter-az-array-test',
            'resource': 'huaweicloud.reliabilitys',
            'filters': [{
                'type': 'list-item',
                'key': 'available_zones',
                'op': 'in',
                'value': ['cn-north-4a', 'cn-north-4b']
            }]},
            session_factory=factory)
        resources_array = p_array.run()
        self.assertEqual(len(resources_array), 1)  # Should find one instance
        
        # Test no match case
        p_no_match = self.load_policy({
            'name': 'rocketmq-filter-az-no-match-test',
            'resource': 'huaweicloud.reliabilitys',
            'filters': [{
                'type': 'list-item',
                'key': 'available_zones',
                'op': 'in',
                'value': 'cn-north-99'  # Non-existent availability zone
            }]},
            session_factory=factory)
        resources_no_match = p_no_match.run()
        self.assertEqual(len(resources_no_match), 0)  # Should not find any instance

    def test_rocketmq_filter_marked_for_op(self):
        # Need a recording with an instance tagged with 'mark-for-op-custodian' or custom tag
        factory = self.replay_flight_data('rocketmq_filter_marked_for_op')
        # Assuming instance is marked for 'delete@YYYY/MM/DD HH:MM:SS UTC' and expired
        p = self.load_policy({
            'name': 'rocketmq-filter-marked-delete-test',
            'resource': 'huaweicloud.reliabilitys',
            'filters': [{
                'type': 'marked-for-op',
                'op': 'delete',
                'tag': 'custodian_cleanup'  # Consistent with tag action
                # 'skew': 1 # Optional: test early matching
            }]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)  # Assuming there is 1 matching instance

        # Edge case: test operation type mismatch
        p_wrong_op = self.load_policy({
            'name': 'rocketmq-filter-marked-wrong-op-test',
            'resource': 'huaweicloud.reliabilitys',
            'filters': [{'type': 'marked-for-op', 'op': 'stop'}]},  # Look for stop
            session_factory=factory)  # Using the same recording (assuming it's marked for delete)
        resources_wrong_op = p_wrong_op.run()
        self.assertEqual(len(resources_wrong_op), 0)

    # =========================
    # Action Tests
    # =========================
    def test_rocketmq_action_mark_for_op(self):
        factory = self.replay_flight_data('rocketmq_action_mark')
        p = self.load_policy({
            'name': 'rocketmq-action-mark-test',
            'resource': 'huaweicloud.reliabilitys',
            'actions': [{
                'type': 'mark-for-op',
                'op': 'delete',
                'tag': 'custodian_cleanup',
                'days': 7
            }]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)  # Assuming action was performed on 1 instance
        # Verification: need to check VCR recording, confirm batch_create_or_delete_rocketmq_tag was called
        # and request body contains correct tag key and value (with timestamp)

    def test_rocketmq_action_auto_tag_user(self):
        # Need a recording with resource dict containing 'creator' or 'user_name'
        factory = self.replay_flight_data('rocketmq_action_autotag')
        p = self.load_policy({
            'name': 'rocketmq-action-autotag-test',
            'resource': 'huaweicloud.reliabilitys',
            'filters': [{'tag:CreatorName': 'absent'}],  # Only operate on instances without CreatorName tag
            'actions': [{
                'type': 'auto-tag-user',
                'tag': 'CreatorName',
                'user_key': 'creator',  # Assuming resource has 'creator' field
                'update': False
            }]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)  # Assuming action was performed on 1 instance

    def test_rocketmq_action_tag(self):
        factory = self.replay_flight_data('rocketmq_action_tag')
        p = self.load_policy({
            'name': 'rocketmq-action-tag-test',
            'resource': 'huaweicloud.reliabilitys',
            'actions': [{'type': 'tag', 'key': 'CostCenter', 'value': 'Finance'}]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # Verification: check VCR, confirm batch_create_or_delete_rocketmq_tag was called (action=create)
        # and body.tags contains {'key': 'CostCenter', 'value': 'Finance'}

    def test_rocketmq_action_remove_tag(self):
        factory = self.replay_flight_data('rocketmq_action_remove_tag')
        p = self.load_policy({
            'name': 'rocketmq-action-remove-tag-test',
            'resource': 'huaweicloud.reliabilitys',
            'filters': [{'tag:environment': 'present'}],  # Ensure tag exists before removing
            'actions': [{'type': 'remove-tag', 'keys': ['environment', 'temp-tag']}]},  # Remove multiple
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)

    def test_rocketmq_action_rename_tag(self):
        factory = self.replay_flight_data('rocketmq_action_rename_tag')
        p = self.load_policy({
            'name': 'rocketmq-action-rename-tag-test',
            'resource': 'huaweicloud.reliabilitys',
            'filters': [{'tag:env': 'present'}],  # Ensure old tag exists
            'actions': [{'type': 'rename-tag', 'old_key': 'env', 'new_key': 'Environment'}]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)

    def test_rocketmq_action_delete(self):
        factory = self.replay_flight_data('rocketmq_action_delete')
        p = self.load_policy({
            'name': 'rocketmq-action-delete-test',
            'resource': 'huaweicloud.reliabilitys',
            # Usually combined with marked-for-op or age filters
            'filters': [{'tag:totest': 'delete'}],
            'actions': ['delete']},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # Verification: check VCR, confirm delete_instance API was called
