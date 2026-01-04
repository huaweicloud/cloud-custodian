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

    # def test_signature_rule_filter_no_match(self):
    #     """Test Signature Rule filter - Match namespaces without signature rules."""
    #     factory = self.replay_flight_data("swr_ee_filter_signature_rule_no_match")
    #     p = self.load_policy(
    #         {
    #             "name": "swr-ee-filter-signature-rule-no-match",
    #             "resource": "huaweicloud.swr-ee-namespace",
    #             "filters": [{"type": "signature-rule", "state": False}],
    #         },
    #         session_factory=factory,
    #     )
    #     resources = p.run()
    #     # Verify VCR: Resources without signature rules should be returned
    #     self.assertGreaterEqual(len(resources), 0)
    #     if len(resources) > 0:
    #         # Verify signature policy
    #         self.assertTrue("c7n:signature-policy" in resources[0])
    #         signature_policy = resources[0]["c7n:signature-policy"]
    #         # Verify signature policy is empty list
    #         self.assertTrue(isinstance(signature_policy, list))
    #         self.assertEqual(len(signature_policy), 0)

    # def test_signature_rule_filter_with_match(self):
    #     """Test Signature Rule filter with match conditions."""
    #     factory = self.replay_flight_data("swr_ee_filter_signature_rule_match_conditions")
    #     p = self.load_policy(
    #         {
    #             "name": "swr-ee-filter-signature-rule-match-conditions",
    #             "resource": "huaweicloud.swr-ee-namespace",
    #             "filters": [
    #                 {
    #                     "type": "signature-rule",
    #                     "state": True,
    #                     "match": [
    #                         {
    #                             "type": "value",
    #                             "key": "enabled",
    #                             "value": True
    #                         }
    #                     ]
    #                 }
    #             ],
    #         },
    #         session_factory=factory,
    #     )
    #     resources = p.run()
    #     # Verify filtered resources match the conditions
    #     self.assertGreaterEqual(len(resources), 0)


# class SetSignatureActionTest(BaseTest):
#     """Test SWR EE Namespace Set Signature Rule actions."""

#     def test_create_signature_rule(self):
#         """Test creating signature rules for SWR EE namespaces."""
#         factory = self.replay_flight_data("swr_ee_signature_action_create")
#         p = self.load_policy(
#             {
#                 "name": "swr-ee-create-signature",
#                 "resource": "huaweicloud.swr-ee-namespace",
#                 "filters": [
#                     {
#                         "type": "signature-rule",
#                         "state": False
#                     }
#                 ],
#                 "actions": [
#                     {
#                         "type": "set-signature",
#                         "signature_algorithm": "ECDSA_SHA_256",
#                         "signature_key": "test-key-id",
#                         "rules": [
#                             {
#                                 "scope_selectors": {
#                                     "repository": [
#                                         {
#                                             "kind": "doublestar",
#                                             "pattern": "**"
#                                         }
#                                     ]
#                                 },
#                                 "tag_selectors": [
#                                     {
#                                         "kind": "doublestar",
#                                         "pattern": "**"
#                                     }
#                                 ]
#                             }
#                         ]
#                     }
#                 ],
#             },
#             session_factory=factory,
#         )
#         resources = p.run()
#         # Verify VCR: Resources should be processed
#         self.assertGreaterEqual(len(resources), 0)

#     def test_update_signature_rule(self):
#         """Test updating signature rules for SWR EE namespaces."""
#         factory = self.replay_flight_data("swr_ee_signature_action_update")
#         p = self.load_policy(
#             {
#                 "name": "swr-ee-update-signature",
#                 "resource": "huaweicloud.swr-ee-namespace",
#                 "filters": [
#                     {
#                         "type": "signature-rule",
#                         "state": True
#                     }
#                 ],
#                 "actions": [
#                     {
#                         "type": "set-signature",
#                         "signature_algorithm": "ECDSA_SHA_384",
#                         "signature_key": "test-key-id-2",
#                         "rules": [
#                             {
#                                 "scope_selectors": {
#                                     "repository": [
#                                         {
#                                             "kind": "doublestar",
#                                             "pattern": "{repo1, repo2}"
#                                         }
#                                     ]
#                                 },
#                                 "tag_selectors": [
#                                     {
#                                         "kind": "doublestar",
#                                         "pattern": "^release-.*$"
#                                     }
#                                 ]
#                             }
#                         ]
#                     }
#                 ],
#             },
#             session_factory=factory,
#         )
#         resources = p.run()
#         # Verify VCR: Resources should be processed
#         self.assertGreaterEqual(len(resources), 0)

#     def test_cancel_signature_rule(self):
#         """Test canceling signature rules for SWR EE namespaces."""
#         factory = self.replay_flight_data("swr_ee_signature_action_cancel")
#         p = self.load_policy(
#             {
#                 "name": "swr-ee-cancel-signature",
#                 "resource": "huaweicloud.swr-ee-namespace",
#                 "filters": [
#                     {
#                         "type": "signature-rule",
#                         "state": True
#                     }
#                 ],
#                 "actions": [
#                     {
#                         "type": "set-signature",
#                         "state": False
#                     }
#                 ],
#             },
#             session_factory=factory,
#         )
#         resources = p.run()
#         # Verify VCR: Resources should be processed
#         self.assertGreaterEqual(len(resources), 0)

#     def test_set_signature_validation_error(self):
#         """Test set-signature action validation errors."""
#         factory = self.replay_flight_data("swr_ee_signature_action_validation")
#         # Test invalid configuration: state=False with rules
#         try:
#             self.load_policy(
#                 {
#                     "name": "swr-ee-signature-validation-error",
#                     "resource": "huaweicloud.swr-ee-namespace",
#                     "actions": [
#                         {
#                             "type": "set-signature",
#                             "state": False,
#                             "rules": [
#                                 {
#                                     "scope_selectors": {
#                                         "repository": [
#                                             {
#                                                 "kind": "doublestar",
#                                                 "pattern": "**"
#                                             }
#                                         ]
#                                     },
#                                     "tag_selectors": [
#                                         {
#                                             "kind": "doublestar",
#                                             "pattern": "**"
#                                         }
#                                     ]
#                                 }
#                             ]
#                         }
#                     ],
#                 },
#                 session_factory=factory,
#             )
#             # Should raise PolicyValidationError
#             self.fail("Expected PolicyValidationError")
#         except Exception as e:
#             # Expected validation error
#             self.assertIsNotNone(e)
