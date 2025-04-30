# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from huaweicloud_common import BaseTest


class SwrRepositoryTest(BaseTest):
    """Test SWR Repository resources, filters, and actions"""

    def test_swr_repository_query(self):
        """Test SWR Repository query and augment"""
        factory = self.replay_flight_data("swr_repository_query")
        p = self.load_policy(
            {
                "name": "swr-repository-query",
                "resource": "huaweicloud.swr",
            },
            session_factory=factory,
        )
        
        resources = p.run()
        # Verify VCR: swr_repository_query should contain 1 repository
        self.assertEqual(len(resources), 1)
        # Verify VCR: Value should match the 'name' in swr_repository_query
        self.assertEqual(resources[0]["name"], "test-repo")
        # Verify resource contains required fields
        self.assertTrue("id" in resources[0])
        self.assertTrue("tag_resource_type" in resources[0])
        
        # Verify lifecycle policy is correctly augmented to the resource
        self.assertTrue("c7n:lifecycle-policy" in resources[0])
        lifecycle_policy = resources[0]["c7n:lifecycle-policy"]
        # Verify lifecycle policy is a list
        self.assertTrue(isinstance(lifecycle_policy, list))
        # Verify rules list length
        self.assertEqual(len(lifecycle_policy), 1)
        
        # Get the first rule
        rule = lifecycle_policy[0]
        
        # Verify rule properties
        self.assertEqual(rule["algorithm"], "or")
        self.assertEqual(rule["id"], 222)
        
        # Verify inner rules
        self.assertTrue("rules" in rule)
        self.assertEqual(len(rule["rules"]), 1)
        rule_detail = rule["rules"][0]
        self.assertEqual(rule_detail["template"], "date_rule")
        self.assertEqual(rule_detail["params"]["days"], "30")
        
        # Verify tag selectors
        self.assertTrue("tag_selectors" in rule_detail)
        selectors = rule_detail["tag_selectors"]
        self.assertEqual(len(selectors), 3)
        self.assertEqual(selectors[0]["kind"], "label")
        self.assertEqual(selectors[0]["pattern"], "v5")
        self.assertEqual(selectors[1]["kind"], "label")
        self.assertEqual(selectors[1]["pattern"], "1.0.1")
        self.assertEqual(selectors[2]["kind"], "regexp")
        self.assertEqual(selectors[2]["pattern"], "^123$")
        
    def test_swr_filter_value(self):
        """Test SWR Repository value filter"""
        factory = self.replay_flight_data("swr_filter_value")
        p = self.load_policy(
            {
                "name": "swr-filter-value",
                "resource": "huaweicloud.swr",
                "filters": [{"type": "value", "key": "is_public", "value": False}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: There should be 1 resource matching is_public=False
        self.assertEqual(len(resources), 1)
        # Verify value matches
        self.assertFalse(resources[0]["is_public"])

    def test_swr_filter_age(self):
        """Test SWR Repository age filter"""
        factory = self.replay_flight_data("swr_filter_age")
        p = self.load_policy(
            {
                "name": "swr-filter-age",
                "resource": "huaweicloud.swr",
                # Verify VCR: Creation time should be greater than 90 days
                "filters": [{"type": "age", "days": 90, "op": "gt"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: There should be 1 repository older than 90 days
        self.assertEqual(len(resources), 1)
        # Verify repository name
        self.assertEqual(resources[0]["name"], "test-repo")
        # Verify creation date is more than 90 days in the past
        created_date = datetime.strptime(resources[0]["created_at"], "%Y-%m-%dT%H:%M:%SZ")
        self.assertTrue((datetime.now() - created_date).days > 90)


class SwrImageTest(BaseTest):
    """Test SWR Image resources, filters, and actions"""

    def test_swr_image_query(self):
        """Test SWR Image query and augment"""
        factory = self.replay_flight_data("swr_image_query")
        p = self.load_policy(
            {
                "name": "swr-image-query",
                "resource": "huaweicloud.swr-image",
                "query": {
                    "namespace": "test-namespace",
                    "repository": "test-repo",
                },
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: There should be 1 image
        self.assertEqual(len(resources), 1)
        # Verify VCR: Image tag should be 'latest'
        self.assertEqual(resources[0]["Tag"], "latest")
        # Verify namespace and repository information
        self.assertEqual(resources[0]["namespace"], "test-namespace")
        self.assertEqual(resources[0]["repository"], "test-repo")
        # Verify ID format
        self.assertTrue("id" in resources[0])
        # Verify image path is added
        self.assertTrue("path" in resources[0])
        # Verify image ID is included
        self.assertTrue("image_id" in resources[0])
        # Verify digest information is included
        self.assertTrue("digest" in resources[0])

    def test_swr_image_filter_age(self):
        """Test SWR Image age filter"""
        factory = self.replay_flight_data("swr_image_filter_age")
        p = self.load_policy(
            {
                "name": "swr-image-filter-age",
                "resource": "huaweicloud.swr-image",
                "query": {
                    "namespace": "test-namespace",
                    "repository": "test-repo",
                },
                # Verify VCR: Image creation time should be greater than 90 days
                "filters": [{"type": "age", "days": 90, "op": "gt"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: There should be 1 image older than 90 days
        self.assertEqual(len(resources), 1)
        # Verify image tag
        self.assertEqual(resources[0]["Tag"], "v1.0.0")
        # Verify namespace and repository information
        self.assertEqual(resources[0]["namespace"], "test-namespace")
        self.assertEqual(resources[0]["repository"], "test-repo")
        # Verify creation date is more than 90 days in the past
        created_date = datetime.strptime(resources[0]["created"], "%Y-%m-%dT%H:%M:%SZ")
        self.assertTrue((datetime.now() - created_date).days > 90)
        
    def test_swr_image_filter_value(self):
        """Test SWR Image value filter"""
        factory = self.replay_flight_data("swr_image_filter_value")
        p = self.load_policy(
            {
                "name": "swr-image-filter-value",
                "resource": "huaweicloud.swr-image",
                "query": {
                    "namespace": "test-namespace",
                    "repository": "test-repo",
                },
                "filters": [{"type": "value", "key": "image_id", "value": "sha256:abc123def456"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: There should be 1 image matching the specified image_id
        self.assertEqual(len(resources), 1)
        # Verify image_id matches
        self.assertEqual(resources[0]["image_id"], "sha256:abc123def456")


class LifecycleRuleFilterTest(BaseTest):
    """Test SWR Lifecycle Rule filter"""
    
    def test_lifecycle_rule_filter_match(self):
        """Test Lifecycle Rule filter - Match"""
        factory = self.replay_flight_data("swr_filter_lifecycle_rule_match")
        p = self.load_policy(
            {
                "name": "swr-filter-lifecycle-rule-match",
                "resource": "huaweicloud.swr",
                "filters": [{"type": "lifecycle-rule", "state": True}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: There should be 1 resource with lifecycle rules
        self.assertEqual(len(resources), 1)
        
        # Verify lifecycle policy
        self.assertTrue("c7n:lifecycle-policy" in resources[0])
        lifecycle_policy = resources[0]["c7n:lifecycle-policy"]
        # Verify lifecycle policy is a list
        self.assertTrue(isinstance(lifecycle_policy, list))
        self.assertTrue(len(lifecycle_policy) > 0)
    
    def test_lifecycle_rule_filter_no_match(self):
        """Test Lifecycle Rule filter - No Match"""
        factory = self.replay_flight_data("swr_filter_lifecycle_rule_no_match")
        p = self.load_policy(
            {
                "name": "swr-filter-lifecycle-rule-no-match",
                "resource": "huaweicloud.swr",
                "filters": [{"type": "lifecycle-rule", "state": False}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: There should be 1 resource without lifecycle rules
        self.assertEqual(len(resources), 1)
        
        # Verify lifecycle policy
        self.assertTrue("c7n:lifecycle-policy" in resources[0])
        lifecycle_policy = resources[0]["c7n:lifecycle-policy"]
        # Verify lifecycle policy is empty list
        self.assertTrue(isinstance(lifecycle_policy, list))
        self.assertEqual(len(lifecycle_policy), 0)
    
    def test_lifecycle_rule_filter_with_match_param(self):
        """Test Lifecycle Rule filter - With Match Parameters"""
        factory = self.replay_flight_data("swr_filter_lifecycle_rule_with_match_param")
        p = self.load_policy(
            {
                "name": "swr-filter-lifecycle-rule-with-match-param",
                "resource": "huaweicloud.swr",
                "filters": [{
                    "type": "lifecycle-rule", 
                    "state": True,
                    "match": [
                        {"type": "value", "key": "rules[0].template", "value": "date_rule"}
                    ]
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: There should be 1 resource with matching lifecycle rules
        self.assertEqual(len(resources), 1)
        
        # Verify lifecycle policy
        lifecycle_policy = resources[0]["c7n:lifecycle-policy"]
        # Verify lifecycle policy is a list
        self.assertTrue(isinstance(lifecycle_policy, list))
        rule = lifecycle_policy[0]
        self.assertEqual(rule["rules"][0]["template"], "date_rule")

    def test_lifecycle_rule_filter_with_params(self):
        """Test Lifecycle Rule filter - With Parameters"""
        factory = self.replay_flight_data("swr_filter_lifecycle_rule_with_params")
        p = self.load_policy(
            {
                "name": "swr-filter-lifecycle-rule-with-params",
                "resource": "huaweicloud.swr",
                "filters": [{
                    "type": "lifecycle-rule",
                    "params": {
                        "days": {
                            "type": "value",
                            "op": "gte",
                            "value": 30
                        }
                    }
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: There should be 1 resource with matching lifecycle rule parameters
        self.assertEqual(len(resources), 1)
        
        # Verify lifecycle policy
        self.assertTrue("c7n:lifecycle-policy" in resources[0])
        lifecycle_policy = resources[0]["c7n:lifecycle-policy"]
        # Verify lifecycle policy is a list
        self.assertTrue(isinstance(lifecycle_policy, list))
        rule = lifecycle_policy[0]
        self.assertTrue("rules" in rule)
        rule_detail = rule["rules"][0]
        self.assertTrue("params" in rule_detail)
        self.assertEqual(rule_detail["params"]["days"], "30")
    
    def test_lifecycle_rule_filter_with_tag_selector(self):
        """Test Lifecycle Rule filter - With Tag Selector"""
        factory = self.replay_flight_data("swr_filter_lifecycle_rule_with_tag_selector")
        p = self.load_policy(
            {
                "name": "swr-filter-lifecycle-rule-with-tag-selector",
                "resource": "huaweicloud.swr",
                "filters": [{
                    "type": "lifecycle-rule",
                    "tag_selector": {
                        "kind": "label",
                        "pattern": "v5"
                    }
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: There should be 1 resource with matching tag selector
        self.assertEqual(len(resources), 1)
        
        # Verify tag selector
        lifecycle_policy = resources[0]["c7n:lifecycle-policy"]
        # Verify lifecycle policy is a list
        self.assertTrue(isinstance(lifecycle_policy, list))
        rule = lifecycle_policy[0]
        rule_detail = rule["rules"][0]
        selectors = rule_detail["tag_selectors"]
        # Check if at least one selector matches
        selector_match = False
        for selector in selectors:
            if selector["kind"] == "label" and selector["pattern"] == "v5":
                selector_match = True
                break
        self.assertTrue(selector_match, "No matching tag selector found")
    
    def test_lifecycle_rule_filter_complex(self):
        """Test Lifecycle Rule filter - Complex Condition Combination"""
        factory = self.replay_flight_data("swr_filter_lifecycle_rule_complex")
        p = self.load_policy(
            {
                "name": "swr-filter-lifecycle-rule-complex",
                "resource": "huaweicloud.swr",
                "filters": [{
                    "type": "lifecycle-rule",
                    "params": {
                        "days": {
                            "type": "value",
                            "op": "gte",
                            "value": 30
                        }
                    },
                    "tag_selector": {
                        "kind": "label"
                    },
                    "match": [
                        {"type": "value", "key": "algorithm", "value": "or"}
                    ]
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: There should be 1 resource matching all conditions
        self.assertEqual(len(resources), 1)
        
        # Verify lifecycle policy satisfies all conditions
        lifecycle_policy = resources[0]["c7n:lifecycle-policy"]
        # Verify lifecycle policy is a list
        self.assertTrue(isinstance(lifecycle_policy, list))
        rule = lifecycle_policy[0]
        
        # Verify algorithm
        self.assertEqual(rule["algorithm"], "or")
        
        # Verify parameters
        rule_detail = rule["rules"][0]
        self.assertTrue("params" in rule_detail)
        self.assertEqual(rule_detail["params"]["days"], "30")
        
        # Verify tag selector
        selectors = rule_detail["tag_selectors"]
        selector_match = False
        for selector in selectors:
            if selector["kind"] == "label":
                selector_match = True
                break
        self.assertTrue(selector_match, "No matching tag selector found")


class SetLifecycleActionTest(BaseTest):
    """Test SWR Set Lifecycle Rule actions"""

    def test_create_lifecycle_rule(self):
        """Test Create Lifecycle Rule"""
        factory = self.replay_flight_data("swr_lifecycle_action_success")
        p = self.load_policy(
            {
                "name": "swr-create-lifecycle",
                "resource": "huaweicloud.swr",
                "filters": [{"type": "value", "key": "name", "value": "test-repo"}],
                "actions": [{
                    "type": "set-lifecycle",
                    "algorithm": "or",
                    "rules": [{
                        "template": "date_rule",
                        "params": {"days": 30},
                        "tag_selectors": [{
                            "kind": "label",
                            "pattern": "v1"
                        }]
                    }]
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: There should be 1 resource
        self.assertEqual(len(resources), 1)
        # Verify VCR: Resource should have retention_id field
        self.assertTrue("retention_id" in resources[0])
        # Verify VCR: Resource status should be created
        self.assertEqual(resources[0]["retention_status"], "created")
    
    def test_create_lifecycle_rule_error(self):
        """Test Create Lifecycle Rule Error Handling"""
        factory = self.replay_flight_data("swr_lifecycle_action_error")
        p = self.load_policy(
            {
                "name": "swr-create-lifecycle-error",
                "resource": "huaweicloud.swr",
                "filters": [{"type": "value", "key": "name", "value": "test-repo"}],
                "actions": [{
                    "type": "set-lifecycle",
                    "algorithm": "or",
                    "rules": [{
                        "template": "date_rule",
                        "params": {"days": 30},
                        "tag_selectors": [{
                            "kind": "label",
                            "pattern": "v1"
                        }]
                    }]
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: There should be 1 resource
        self.assertEqual(len(resources), 1)
        # Verify VCR: Resource should have error field
        self.assertTrue("error" in resources[0])
        # Verify VCR: Resource status should be error
        self.assertEqual(resources[0]["status"], "error")
    
    def test_missing_namespace_repository(self):
        """Test Missing Namespace or Repository Information Handling"""
        factory = self.replay_flight_data("swr_lifecycle_missing_info")
        p = self.load_policy(
            {
                "name": "swr-lifecycle-missing-info",
                "resource": "huaweicloud.swr",
                "filters": [{"type": "value", "key": "name", "value": "test-repo-no-namespace"}],
                "actions": [{
                    "type": "set-lifecycle",
                    "algorithm": "or",
                    "rules": [{
                        "template": "date_rule",
                        "params": {"days": 30},
                        "tag_selectors": [{
                            "kind": "label",
                            "pattern": "v1"
                        }]
                    }]
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: There should be 1 resource
        self.assertEqual(len(resources), 1)
        # Verify VCR: Resource should have error field
        self.assertTrue("error" in resources[0])
        # Verify VCR: Error message should contain missing namespace or repository information
        self.assertTrue("Missing namespace or repository information" in resources[0]["error"])