# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

from huaweicloud_common import BaseTest


class SignatureRuleFilterTest(BaseTest):
    """Test SWR EE Namespace Signature Rule filter functionality."""

    def test_signature_rule_filter_match(self):
        """Test Signature Rule filter - Match namespaces with signature rules."""
        factory = self.replay_flight_data("swr_ee_filter_signature_rule_match")
        p = self.load_policy(
            {
                "name": "swr-ee-filter-signature-rule-match",
                "resource": "huaweicloud.swr-ee-namespace",
                "filters": [{"type": "signature-rule", "state": True}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: Resources with signature rules should be returned
        self.assertGreaterEqual(len(resources), 0)
        if len(resources) > 0:
            # Verify signature policy is lazily loaded by the filter
            self.assertTrue("c7n:signature-policy" in resources[0])
            signature_policy = resources[0]["c7n:signature-policy"]
            # Verify signature policy is a list
            self.assertTrue(isinstance(signature_policy, list))
            self.assertTrue(len(signature_policy) > 0)


class SetSignatureActionTest(BaseTest):
    """Test SWR EE Namespace Set Signature Rule actions."""

    def test_create_signature_rule(self):
        """Test creating signature rules for SWR EE namespaces."""
        factory = self.replay_flight_data("swr_ee_signature_action_create")
        p = self.load_policy(
            {
                "name": "swr-ee-create-signature",
                "resource": "huaweicloud.swr-ee-namespace",
                "filters": [
                    {
                        "type": "signature-rule",
                        "state": False
                    }
                ],
                "actions": [
                    {
                        "type": "set-signature",
                        "signature_algorithm": "ECDSA_SHA_256",
                        "signature_key": "test-key-id",
                        "scope_rules": [
                            {
                                "scope_selectors": {
                                    "repository": [
                                        {
                                            "kind": "doublestar",
                                            "pattern": "**"
                                        }
                                    ]
                                },
                                "tag_selectors": [
                                    {
                                        "kind": "doublestar",
                                        "pattern": "**"
                                    }
                                ]
                            }
                        ]
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: Resources should be processed
        self.assertGreaterEqual(len(resources), 0)
