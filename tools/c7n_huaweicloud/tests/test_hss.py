# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

from huaweicloud_common import BaseTest


class HssTest(BaseTest):
    """Test Huawei Cloud Host Security Service (HSS) resources, filters, and actions"""

    def test_hss_query(self):
        """Test HSS resource query and augment"""
        factory = self.replay_flight_data("hss_query")
        p = self.load_policy(
            {
                "name": "hss-query-test",
                "resource": "huaweicloud.hss",
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: hss_query should contain 1 host
        self.assertEqual(len(resources), 1)
        # Verify VCR: Value should match the 'host_name' in hss_query
        self.assertEqual(resources[0]["host_name"], "test-host")
        # Verify augment added additional information
        self.assertIn("agent_status", resources[0])

    def test_hss_action_switch_hosts_protect_status(self):
        """Test switch host protection status action - Switch to enterprise version"""
        factory = self.replay_flight_data("hss_action_switch_hosts_protect_status")
        p = self.load_policy(
            {
                "name": "hss-switch-protection-status",
                "resource": "huaweicloud.hss",
                "actions": [
                    {
                        "type": "switch-hosts-protect-status",
                        "version": "hss.version.enterprise",
                        "charging_mode": "packet_cycle",
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)

    def test_hss_action_set_wtp_protection_status_enable(self):
        """Test set web tamper protection status action - Enable protection"""
        factory = self.replay_flight_data("hss_action_set_wtp_protection_status_enable")
        p = self.load_policy(
            {
                "name": "hss-enable-wtp-protection",
                "resource": "huaweicloud.hss",
                "actions": [{"type": "set-wtp-protection-status", "status": "enabled"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)

    def test_hss_action_set_wtp_protection_status_disable(self):
        """Test set web tamper protection status action - Disable protection"""
        factory = self.replay_flight_data(
            "hss_action_set_wtp_protection_status_disable"
        )
        p = self.load_policy(
            {
                "name": "hss-disable-wtp-protection",
                "resource": "huaweicloud.hss",
                "actions": [
                    {"type": "set-wtp-protection-status", "status": "disabled"}
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)


# =========================
# Reusable Feature Tests (Using HSS as example)
# =========================


class ReusableFeaturesTest(BaseTest):
    """Test reusable filters and actions on HSS resources"""

    def test_filter_value_match(self):
        """Test value filter - Match successful"""
        factory = self.replay_flight_data("hss_filter_value_match")
        # Get hostname from hss_filter_value_match
        # Verify VCR: Match 'test-host' hostname in hss_filter_value_match
        target_host_name = "test-host"
        p = self.load_policy(
            {
                "name": "hss-filter-value-hostname-match",
                "resource": "huaweicloud.hss",
                "filters": [
                    {"type": "value", "key": "host_name", "value": target_host_name}
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: hss_filter_value_match should have only one host matching this hostname
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["host_name"], target_host_name)

    def test_filter_value_no_match(self):
        """Test value filter - No match"""
        factory = self.replay_flight_data("hss_filter_value_match")  # Reuse
        wrong_host_name = "nonexistent-host"
        p = self.load_policy(
            {
                "name": "hss-filter-value-hostname-no-match",
                "resource": "huaweicloud.hss",
                "filters": [
                    {"type": "value", "key": "host_name", "value": wrong_host_name}
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: hss_filter_value_match should have no hosts matching this hostname
        self.assertEqual(len(resources), 0)
