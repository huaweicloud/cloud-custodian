# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

from datetime import datetime

from huaweicloud_common import BaseTest


class SwrRepositoryTest(BaseTest):
    """Test SWR Repository resources, filters, and actions."""

    def test_swr_repository_query(self):
        """Test SWR Repository query and basic resource attributes."""
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
        # Lifecycle policy is now loaded on-demand by the lifecycle-rule filter,
        # and not in the initial resource fetch

    def test_swr_filter_value(self):
        """Test SWR Repository value filter for filtering by field values."""
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
        """Test SWR Repository age filter for filtering by creation time."""
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
        created_date = datetime.strptime(
            resources[0]["created_at"], "%Y-%m-%dT%H:%M:%SZ")
        self.assertTrue((datetime.now() - created_date).days > 90)


class SwrImageTest(BaseTest):
    """Test SWR Image resources, filters, and actions."""

    def test_swr_image_query(self):
        """Test SWR Image query and resource enumeration."""
        factory = self.replay_flight_data("swr_image_query")
        p = self.load_policy(
            {
                "name": "swr-image-query",
                "resource": "huaweicloud.swr-image",
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: There should be 6 images from multiple repositories
        self.assertEqual(len(resources), 6)
        # Verify VCR: Image tag should be 'latest'
        self.assertEqual(resources[0]["tag"], "latest")
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
        """Test SWR Image age filter for filtering by creation time."""
        factory = self.replay_flight_data("swr_image_filter_age")
        p = self.load_policy(
            {
                "name": "swr-image-filter-age",
                "resource": "huaweicloud.swr-image",
                # Verify VCR: Image creation time should be greater than 90 days
                "filters": [{"type": "age", "days": 90, "op": "gt"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: There should be 3 images older than 90 days
        self.assertEqual(len(resources), 3)
        # Verify image is from test-repo
        self.assertEqual(resources[0]["repository"], "test-repo")
        # Verify creation date is from 2022, which is more than 90 days in the past
        created_date = datetime.strptime(
            resources[0]["created"], "%Y-%m-%dT%H:%M:%SZ")
        self.assertTrue(created_date.year == 2022)

    def test_swr_image_filter_value(self):
        """Test SWR Image value filter for filtering by field values."""
        factory = self.replay_flight_data("swr_image_filter_value")
        p = self.load_policy(
            {
                "name": "swr-image-filter-value",
                "resource": "huaweicloud.swr-image",
                "filters": [{"type": "value", "key": "image_id", "value": "sha256:abc123def456"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: There should be 1 image matching the specified image_id
        self.assertEqual(len(resources), 1)
        # Verify image is from test-repo
        self.assertEqual(resources[0]["repository"], "test-repo")


class LifecycleRuleFilterTest(BaseTest):
    """Test SWR Lifecycle Rule filter functionality."""

    def test_lifecycle_rule_filter_match(self):
        """Test Lifecycle Rule filter - Match repositories with lifecycle rules."""
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

        # Verify lifecycle policy is lazily loaded by the filter
        self.assertTrue("c7n:lifecycle-policy" in resources[0])
        lifecycle_policy = resources[0]["c7n:lifecycle-policy"]
        # Verify lifecycle policy is a list
        self.assertTrue(isinstance(lifecycle_policy, list))
        self.assertTrue(len(lifecycle_policy) > 0)

        # Now that we've verified the lifecycle policies are loaded on-demand,
        # we can test the specific policy details
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

    def test_lifecycle_rule_filter_no_match(self):
        """Test Lifecycle Rule filter - Match repositories without lifecycle rules."""
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


class SetLifecycleActionTest(BaseTest):
    """Test SWR Set Lifecycle Rule actions."""

    def test_create_lifecycle_rule(self):
        """Test creating lifecycle rules for SWR repositories."""
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
