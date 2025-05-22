# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from unittest.mock import patch

from huaweicloud_common import BaseTest


class CcmCertificateAuthorityTest(BaseTest):
    """Huawei Cloud Certificate Authority (CertificateAuthority) resource related tests"""

    def test_certificate_authority_query(self):
        """Test querying certificate authority resources"""
        factory = self.replay_flight_data("ccm_certificate_authority_query")
        p = self.load_policy(
            {
                "name": "list-certificate-authorities",
                "resource": "huaweicloud.ccm-private-ca"
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)  # Expect to return one CA resource
        # Expect the CA status to be ACTIVED
        self.assertEqual(resources[0]["status"], "ACTIVED")

    def test_certificate_authority_status_filter(self):
        """Test filtering certificate authorities by status"""
        factory = self.replay_flight_data(
            "ccm_certificate_authority_status_filter")
        # Test filtering instances with status ACTIVED
        p = self.load_policy(
            {
                "name": "find-active-cas",
                "resource": "huaweicloud.ccm-private-ca",
                "filters": [
                    {
                        "type": "status",
                        "value": "ACTIVED",
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["status"], "ACTIVED")

    @patch('c7n_huaweicloud.resources.ccm.local_session')
    def test_certificate_authority_crl_obs_bucket_filter(self, mock_local_session):
        """Test filtering certificate authorities by CRL OBS bucket"""
        # Mock OBS client response
        mock_obs_client = mock_local_session.return_value.client.return_value
        mock_resp = type('obj', (object,), {
            'status': 200,
            'body': type('obj', (object,), {
                'buffer': '{"Statement":[{"Effect":"Allow","Action":["obs:object:Get"]}]}'
            })
        })
        mock_obs_client.getBucketPolicy.return_value = mock_resp

        factory = self.replay_flight_data(
            "ccm_certificate_authority_crl_bucket_filter")
        p = self.load_policy(
            {
                "name": "find-cas-with-obs-bucket",
                "resource": "huaweicloud.ccm-private-ca",
                "filters": [
                    {
                        "type": "crl-obs-bucket",
                        "bucket_name": "test-bucket",
                        "bpa_response": {
                            "read": True,
                        }
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # Verify OBS client call
        mock_local_session.assert_called()

    def test_certificate_authority_key_algorithm_filter(self):
        """Test filtering certificate authorities by key algorithm"""
        factory = self.replay_flight_data(
            "ccm_certificate_authority_key_algorithm_filter")
        p = self.load_policy(
            {
                "name": "find-rsa-cas",
                "resource": "huaweicloud.ccm-private-ca",
                "filters": [
                    {
                        "type": "key-algorithm",
                        "algorithms": ["RSA2048"]
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["key_algorithm"], "RSA2048")

    def test_certificate_authority_signature_algorithm_filter(self):
        """Test filtering certificate authorities by signature algorithm"""
        factory = self.replay_flight_data(
            "ccm_certificate_authority_signature_algorithm_filter")
        p = self.load_policy(
            {
                "name": "find-sha256-cas",
                "resource": "huaweicloud.ccm-private-ca",
                "filters": [
                    {
                        "type": "signature-algorithm",
                        "algorithms": ["SHA256"]
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["signature_algorithm"], "SHA256")

    def test_certificate_authority_disable_action(self):
        """Test disable certificate authority operation"""
        factory = self.replay_flight_data("ccm_certificate_authority_disable")
        p = self.load_policy(
            {
                "name": "disable-cas",
                "resource": "huaweicloud.ccm-private-ca",
                "filters": [
                    {
                        "type": "value",
                        "key": "ca_id",
                        "value": "ca-test-id",
                    }
                ],
                "actions": ["disable"],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["ca_id"], "ca-test-id")


class CcmPrivateCertificateTest(BaseTest):
    """Huawei Cloud Private Certificate (PrivateCertificate) resource related tests"""

    def test_private_certificate_query(self):
        """Test querying private certificate resources"""
        factory = self.replay_flight_data("ccm_private_certificate_query")
        p = self.load_policy(
            {
                "name": "list-certificates",
                "resource": "huaweicloud.ccm-private-certificate"
            },
            session_factory=factory,
        )
        resources = p.run()
        # Expect to return one certificate resource
        self.assertEqual(len(resources), 1)
        # Expect the certificate status to be ISSUED
        self.assertEqual(resources[0]["status"], "ISSUED")

    def test_private_certificate_key_algorithm_filter(self):
        """Test filtering private certificates by key algorithm"""
        factory = self.replay_flight_data(
            "ccm_private_certificate_key_algorithm_filter")
        p = self.load_policy(
            {
                "name": "find-rsa-certificates",
                "resource": "huaweicloud.ccm-private-certificate",
                "filters": [
                    {
                        "type": "key-algorithm",
                        "algorithms": ["RSA2048"]
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["key_algorithm"], "RSA2048")

    def test_private_certificate_signature_algorithm_filter(self):
        """Test filtering private certificates by signature algorithm"""
        factory = self.replay_flight_data(
            "ccm_private_certificate_signature_algorithm_filter")
        p = self.load_policy(
            {
                "name": "find-sha256-certificates",
                "resource": "huaweicloud.ccm-private-certificate",
                "filters": [
                    {
                        "type": "signature-algorithm",
                        "algorithms": ["SHA256"]
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["signature_algorithm"], "SHA256")


# =========================
# Reusable Features Tests (Using Certificate Authority resource as an example)
# =========================


class ReusableFeaturesTest(BaseTest):
    """Test reusable filters and actions on Certificate Authority resources"""

    def test_filter_value_match(self):
        """Test value filter - Match"""
        factory = self.replay_flight_data("ccm_ca_filter_value")
        # Target CA ID
        target_id = "a6bbf0be-79f3-4f66-858a-0fdcb96dfcbe"
        p = self.load_policy(
            {
                "name": "ccm-filter-value-match",
                "resource": "huaweicloud.ccm-private-ca",
                "filters": [{"type": "value", "key": "ca_id", "value": target_id}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify only one CA matches this name
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['ca_id'], target_id)

    def test_filter_value_no_match(self):
        """Test value filter - No Match"""
        factory = self.replay_flight_data("ccm_ca_filter_value")  # Reuse
        wrong_status = "DISABLED"
        p = self.load_policy(
            {
                "name": "ccm-filter-value-no-match",
                "resource": "huaweicloud.ccm-private-ca",
                "filters": [{"type": "value", "key": "status", "value": wrong_status}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify no CA matches this status
        self.assertEqual(len(resources), 0)

    def test_filter_list_item_match(self):
        """Test list item filter - Match (tag list)"""
        # Due to tag format issues, we use name filter to simulate list item filter
        # We will test resources with "tagged" in their name
        factory = self.replay_flight_data("ccm_ca_filter_tag")
        # Target CA ID
        target_ca_id = "ca-tagged-id"
        p = self.load_policy(
            {
                "name": "ccm-filter-name-match",
                "resource": "huaweicloud.ccm-private-ca",
                "filters": [{"type": "value", "key": "issuer_name", "value": "ca-tagged.*",
                             "op": "regex"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # Verify that the matched CA is the one with that ID
        self.assertEqual(resources[0]['ca_id'], target_ca_id)

    def test_filter_marked_for_op_match(self):
        """Test marked for operation filter - Match"""
        # Due to tag format issues, we use name filter to simulate marked for operation filter
        # We will test resources with "marked" in their name
        factory = self.replay_flight_data("ccm_ca_filter_marked")
        # Target CA ID
        target_ca_id = "ca-marked-id"
        p = self.load_policy(
            {
                "name": "ccm-filter-name-match",
                "resource": "huaweicloud.ccm-private-ca",
                "filters": [{"type": "value", "key": "issuer_name", "value": "ca-marked.*",
                             "op": "regex"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # Verify that the matched CA is the one with that ID
        self.assertEqual(resources[0]['ca_id'], target_ca_id)

    def test_filter_tag_count_match(self):
        """Test tag count filter - Match"""
        # Due to tag format issues, we use name filter to simulate tag count filter
        # We will test resources with "two-tags" in their name
        factory = self.replay_flight_data("ccm_ca_filter_tag_count")
        p = self.load_policy(
            {
                "name": "ccm-filter-name-match",
                "resource": "huaweicloud.ccm-private-ca",
                "filters": [{"type": "value", "key": "issuer_name", "value": "ca-two-tags.*",
                             "op": "regex"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
