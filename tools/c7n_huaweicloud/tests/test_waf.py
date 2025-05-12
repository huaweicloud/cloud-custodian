# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import json
import logging
from huaweicloud_common import BaseTest


class WafPolicyTest(BaseTest):
    """Test class for Huawei Cloud WAF policy resources"""

    def test_policy_query(self):
        """Test WAF policy list query"""
        factory = self.replay_flight_data("waf_policy_query")
        p = self.load_policy(
            {"name": "waf-policy-query", "resource": "huaweicloud.waf-policy"},
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)  # Expect to return 1 policy
        self.assertEqual(resources[0]["name"], "policy-example")  # Verify policy name
        self.assertEqual(resources[0]["level"], 2)  # Verify protection level
        self.assertTrue(resources[0]["full_detection"])  # Verify full detection mode is enabled


class WafLogConfigTest(BaseTest):
    """Test class for Huawei Cloud WAF log configuration resources"""

    def test_log_config_query(self):
        """Test WAF log configuration query"""
        factory = self.replay_flight_data("waf_log_config_query")
        p = self.load_policy(
            {"name": "waf-log-config-query", "resource": "huaweicloud.waf-log-config"},
            session_factory=factory,
        )
        resources = p.run()
        
        self.assertEqual(len(resources), 1)  # Expect to return 1 log configuration
        # Verify ID field exists
        self.assertTrue("id" in resources[0])
        self.assertEqual(resources[0]["id"], "log-config-12345")
        # Verify enabled status
        self.assertTrue(resources[0]["enabled"])
        # Verify LTS information exists
        self.assertTrue("ltsIdInfo" in resources[0])
        self.assertEqual(resources[0]["ltsIdInfo"]["ltsGroupId"], "group-id-12345")

    def test_log_config_enabled_filter_true(self):
        """Test WAF log configuration enabled status filter - Enabled status"""
        factory = self.replay_flight_data("waf_log_config_enabled_filter_true")
        p = self.load_policy(
            {
                "name": "waf-log-config-enabled-true",
                "resource": "huaweicloud.waf-log-config",
                "filters": [
                    {
                        "type": "enabled",
                        "value": True
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)  # Expect to return 1 enabled log configuration
        self.assertTrue(resources[0]["enabled"])  # Verify enabled status is True
        self.assertEqual(resources[0]["id"], "log-config-12345")  # Verify ID matches expected

    def test_log_config_enabled_filter_false(self):
        """Test WAF log configuration enabled status filter - Disabled status"""
        factory = self.replay_flight_data("waf_log_config_enabled_filter_false")
        p = self.load_policy(
            {
                "name": "waf-log-config-enabled-false",
                "resource": "huaweicloud.waf-log-config",
                "filters": [
                    {
                        "type": "enabled",
                        "value": False
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)  # Expect to return 1 disabled log configuration
        self.assertFalse(resources[0]["enabled"])  # Verify enabled status is False
        self.assertEqual(resources[0]["id"], "log-config-12345")  # Verify ID matches expected

    def test_update_log_config_enable(self):
        """Test updating WAF log configuration - Enable logging"""
        factory = self.replay_flight_data("waf_log_config_update_enable")
        p = self.load_policy(
            {
                "name": "waf-log-config-update-enable",
                "resource": "huaweicloud.waf-log-config",
                "filters": [
                    {
                        "type": "enabled",
                        "value": False
                    }
                ],
                "actions": [
                    {
                        "type": "update",
                        "enabled": True,
                        "lts_id_info": {
                            "lts_group_id": "test-group-id",
                            "lts_access_stream_id": "test-access-stream-id",
                            "lts_attack_stream_id": "test-attack-stream-id"
                        }
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)  # Expect to update 1 log configuration
        # Confirm instance ID in record matches the instance ID being operated on
        self.assertEqual(resources[0]["id"], "test-log-config-id")
        # Initial state should be disabled
        self.assertFalse(resources[0]["enabled"])

    def test_update_log_config_disable(self):
        """Test updating WAF log configuration - Disable logging"""
        factory = self.replay_flight_data("waf_log_config_update_disable")
        p = self.load_policy(
            {
                "name": "waf-log-config-update-disable",
                "resource": "huaweicloud.waf-log-config",
                "filters": [
                    {
                        "type": "enabled",
                        "value": True
                    }
                ],
                "actions": [
                    {
                        "type": "update",
                        "enabled": False
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)  # Expect to update 1 log configuration
        # Confirm instance ID in record matches the instance ID being operated on
        self.assertEqual(resources[0]["id"], "test-log-config-id")
        # Initial state should be enabled
        self.assertTrue(resources[0]["enabled"])
