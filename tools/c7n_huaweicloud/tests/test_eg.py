# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

from unittest import mock
import os
import json
from dateutil.parser import parse

from tools.c7n_huaweicloud.tests.huaweicloud_common import BaseTest

class EventStreamingTest(BaseTest):
    """Test EventStreaming resources, filters, and actions."""

    def setUp(self):
        """Set up test environment."""
        super().setUp()
        # Set default region to cn-north-4, as EventGrid service is limited
        self.default_region = "cn-north-4"
        # Override default region in environment variables
        os.environ['HUAWEI_DEFAULT_REGION'] = self.default_region
        
    def test_eventstreaming_query(self):
        """Test basic query functionality for event streaming."""
        factory = self.replay_flight_data('eg_eventstreaming_query')
        p = self.load_policy({
            'name': 'eventstreaming-query-test',
            'resource': 'huaweicloud.eventstreaming'
        }, session_factory=factory)
        
        resources = p.run()
        
        # Verify VCR: eg_eventstreaming_query should return 1 resource
        self.assertEqual(len(resources), 1)

    def test_eventstreaming_age_filter(self):
        """Test the 'age' filter for EventStreaming resources."""
        factory = self.replay_flight_data('eg_eventstreaming_age_filter')
        p = self.load_policy({
            'name': 'old-event-streaming',
            'resource': 'huaweicloud.eventstreaming',
            'filters': [{
                'type': 'age',
                'days': 180, # Filter for resources older than 180 days
                'op': 'gt'
            }]
        }, session_factory=factory)
        resources = p.run()
        # Verify VCR: eg_eventstreaming_age_filter should return 2 resources older than 180 days
        self.assertEqual(len(resources), 2)

    def test_filter_tag_count_match(self):
        """Test the 'tag-count' filter."""
        factory = self.replay_flight_data('eg_eventstreaming_filter_tag_count')
        
        # Mock augment to simulate tag data, avoiding TMS client issues
        with mock.patch('c7n_huaweicloud.resources.eg.EventStreaming.augment') as mock_augment:
            def mock_augment_implementation(resources):
                for resource in resources:
                    if resource['id'] == 'es-005-two-tags':
                        resource['tags'] = [
                            {'key': 'environment', 'value': 'testing'},
                            {'key': 'project', 'value': 'cloud-custodian'}
                        ]
                    elif resource['id'] == 'es-007-one-tag':
                        resource['tags'] = [
                            {'key': 'environment', 'value': 'development'}
                        ]
                    else: # es-008-no-tags
                        resource['tags'] = []
                return resources
            
            mock_augment.side_effect = mock_augment_implementation
            
            expected_tag_count = 2
            p = self.load_policy({
                'name': 'eventstreaming-tag-count-match',
                'resource': 'huaweicloud.eventstreaming',
                'filters': [{'type': 'tag-count', 'count': expected_tag_count}]
            }, session_factory=factory)
            
            resources = p.run()
            
            # Verify VCR: eg_eventstreaming_filter_tag_count should contain one resource with exactly 2 tags
            self.assertEqual(len(resources), 1)
            self.assertEqual(resources[0]['id'], 'es-005-two-tags')
            
            # Test greater than operator
            p2 = self.load_policy({
                'name': 'eventstreaming-tag-count-gt',
                'resource': 'huaweicloud.eventstreaming',
                'filters': [{'type': 'tag-count', 'count': 1, 'op': 'gt'}]
            }, session_factory=factory)
            
            resources_gt = p2.run()
            # Verify VCR: Should find resources with more than 1 tag
            self.assertEqual(len(resources_gt), 1)
            self.assertEqual(resources_gt[0]['id'], 'es-005-two-tags')

    def test_filter_list_item_match(self):
        """Test list-item filter - matching (tag list)"""
        factory = self.replay_flight_data('eg_eventstreaming_filter_list_item_tag')
        
        # Mock augment to simulate tag data in actual API responses
        with mock.patch('c7n_huaweicloud.resources.eg.EventStreaming.augment') as mock_augment:
            def mock_augment_implementation(resources):
                for resource in resources:
                    if resource['id'] == 'es-003-with-tags':
                        resource['tags'] = [
                            {'key': 'filtertag', 'value': 'filtervalue'},
                            {'key': 'department', 'value': 'IT'}
                        ]
                    elif resource['id'] == 'es-007-other-tags':
                        resource['tags'] = [
                            {'key': 'othertag', 'value': 'othervalue'}
                        ]
                return resources
            
            mock_augment.side_effect = mock_augment_implementation
            
            # Load policy to find event streams with specific tags
            p = self.load_policy({
                'name': 'eventstreaming-list-item-tag-match',
                'resource': 'huaweicloud.eventstreaming',
                'filters': [{
                    'type': 'list-item',
                    'key': 'tags',
                    'attrs': [
                        {'type': 'value', 'key': 'key', 'value': 'filtertag'},
                        {'type': 'value', 'key': 'value', 'value': 'filtervalue'}
                    ]
                }]
            }, session_factory=factory)
            
            # Execute policy
            resources = p.run()
            
            # Verify results: There should be two event streams matching the tag conditions
            self.assertEqual(len(resources), 2)
            self.assertEqual(resources[0]['id'], 'es-003-with-tags')

    def test_filter_marked_for_op_match(self):
        """Test marked-for-op filter - matching"""
        factory = self.replay_flight_data('eg_eventstreaming_filter_marked_for_op')
        
        # Mock augment to simulate tag data in actual API responses
        with mock.patch('c7n_huaweicloud.resources.eg.EventStreaming.augment') as mock_augment:
            def mock_augment_implementation(resources):
                for resource in resources:
                    if resource['id'] == 'es-004-marked':
                        resource['tags'] = [
                            {'key': 'c7n_status', 'value': 'webhook_2023/01/01 00:00:00 UTC'}
                        ]
                    elif resource['id'] == 'es-009-not-marked':
                        resource['tags'] = [
                            {'key': 'environment', 'value': 'production'}
                        ]
                return resources
            
            mock_augment.side_effect = mock_augment_implementation
            
            # Load policy to find event streams marked for webhook operation
            p = self.load_policy({
                'name': 'eventstreaming-marked-for-op-webhook-match',
                'resource': 'huaweicloud.eventstreaming',
                'filters': [{'type': 'marked-for-op', 'op': 'webhook', 'tag': 'c7n_status'}]
            }, session_factory=factory)
            
            # Execute policy
            resources = p.run()
            
            # Verify results: There should be only one event stream marked for webhook
            self.assertEqual(len(resources), 1)
            self.assertEqual(resources[0]['id'], 'es-004-marked')

    def test_filter_value_match(self):
        """Test value filter - Match"""
        factory = self.replay_flight_data("eg_eventstreaming_filter_value_name")
        # Get the name value from eg_eventstreaming_filter_value_name
        # Verify VCR: Match the 'name' of 'es-001-target' in
        # eg_eventstreaming_filter_value_name
        target_name = "es-001-target"
        p = self.load_policy(
            {
                "name": "eventstreaming-filter-value-name-match",
                "resource": "huaweicloud.eventstreaming",
                "filters": [{"type": "value", "key": "name", "value": target_name}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: Only one EventStreaming in eg_eventstreaming_filter_value_name matches this name
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['name'], target_name)
