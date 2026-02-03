# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

from huaweicloud_common import BaseTest


# Note: Actual testing requires corresponding VCR files
# (e.g., geminidb_query.yaml, geminidb_filter_*.yaml, geminidb_action_*.yaml)
# These files should contain the required GeminiDB instance data and API interaction for testing.

class GeminiDBTest(BaseTest):
    """Test Huawei Cloud GeminiDB resources, filters, and actions"""

    # =========================
    # Resource Query Test
    # =========================
    def test_geminidb_query(self):
        """Test GeminiDB instance query and basic attributes"""
        factory = self.replay_flight_data("geminidb_query")
        p = self.load_policy(
            {
                "name": "geminidb-query-test",
                "resource": "huaweicloud.geminidb",
            },
            session_factory=factory,
        )
        resources = p.run()
        # Validate VCR: geminidb_query.yaml should contain at least one GeminiDB instance
        self.assertGreater(len(resources), 0,
                           "Test VCR file should contain at least one GeminiDB instance")
        # Validate VCR: verify key attributes of the first instance
        instance = resources[0]
        self.assertTrue("id" in instance)
        self.assertTrue("name" in instance)
        self.assertTrue("status" in instance)
        self.assertTrue("availability_zone" in instance)

    # =========================
    # Filter Tests
    # =========================
    def test_geminidb_filter_backup_policy_disabled(self):
        """Test backup-policy-disabled filter"""
        factory = self.replay_flight_data("geminidb_filter_backup_policy_disabled")
        # Validate VCR: geminidb_filter_backup_policy.yaml should
        # contain at least one instance with backup policy disabled
        p = self.load_policy(
            {
                "name": "geminidb-filter-backup-policy-disabled-test",
                "resource": "huaweicloud.geminidb",
                "filters": [{"type": "backup-policy-disabled"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources),
                         1,
                           "Test VCR file should contain 1 instance with backup policy disabled")

    def test_geminidb_filter_multi_availability_zone_deployment_disabled(self):
        """Test backup-policy-disabled filter"""
        factory = self.replay_flight_data(
            "geminidb_filter_multi_availability_zone_deployment_disabled")
        # Validate VCR: geminidb_filter_multi_availability_zone_deployment_disabled.yaml should
        # contain at least one instance with multi-availability zone deployment disabled
        p = self.load_policy(
            {
                "name": "geminidb-filter-multi-availability-zone-deployment-disabled-test",
                "resource": "huaweicloud.geminidb",
                "filters": [{"type": "multi-availability-zone-deployment-disabled"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources),
                         1,
                           "Test VCR file should contain 1 instance with multi-az disabled")

    # =========================
    # Action Tests
    # =========================
    def test_geminidb_action_set_backup_policy(self):
        """Test set-backup-policy action"""
        factory = self.replay_flight_data("geminidb_action_set_backup_policy")
        # Validate VCR: geminidb_action_set_backup_policy.yaml should contain
        # instances to set backup policy
        target_instance_id = "geminidb-instance-for-backup-policy"
        p = self.load_policy(
            {
                "name": "geminidb-action-set-backup-policy-test",
                "resource": "huaweicloud.geminidb",
                "filters": [
                    {"id": target_instance_id},
                    {"type": "backup-policy-disabled"}
                ],
                "actions": [{
                    "type": "set-backup-policy",
                    "keep_days": 7,
                    "start_time": "01:00-02:00",
                    "period": "1, 2, 3, 4, 5, 6, 7"
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], target_instance_id)
