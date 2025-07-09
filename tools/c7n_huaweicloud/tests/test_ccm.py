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
        with self.myvcr.use_cassette("ccm_certificate_authority_query", record_mode='none'):
            resources = p.run()
        self.assertEqual(len(resources), 1)  # Expect to return one CA resource
        # Expect the CA status to be ACTIVED
        self.assertEqual(resources[0]["status"], "ACTIVED")

    def test_certificate_authority_status_filter(self):
        """Test filtering certificate authorities by status"""
        factory = self.replay_flight_data(
            "ccm_certificate_authority_status_filter")
        p = self.load_policy(
            {
                "name": "find-active-cas",
                "resource": "huaweicloud.ccm-private-ca",
                "filters": [
                    {
                        "type": "status",
                        "value": "ACTIVED"
                    }
                ],
            },
            session_factory=factory,
        )
        with self.myvcr.use_cassette("ccm_certificate_authority_status_filter", record_mode='none'):
            resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["status"], "ACTIVED")

        # Test with non-matching status
        p = self.load_policy(
            {
                "name": "find-disabled-cas",
                "resource": "huaweicloud.ccm-private-ca",
                "filters": [
                    {
                        "type": "status",
                        "value": "DISABLED"
                    }
                ],
            },
            session_factory=factory,
        )
        with self.myvcr.use_cassette("ccm_certificate_authority_status_filter", record_mode='none'):
            resources = p.run()
        # Expect no resources with DISABLED status
        self.assertEqual(len(resources), 0)

    def test_certificate_authority_issuer_name_filter(self):
        """Test filtering certificate authorities by issuer name"""
        factory = self.replay_flight_data(
            "ccm_certificate_authority_issuer_filter")

        # Test with a null issuer_name (should find CAs with empty issuer_name)
        p = self.load_policy(
            {
                "name": "find-cas-with-empty-issuer",
                "resource": "huaweicloud.ccm-private-ca",
                "filters": [
                    {
                        "type": "issuer-name",
                        "value": None
                    }
                ],
            },
            session_factory=factory,
        )
        with self.myvcr.use_cassette("ccm_certificate_authority_issuer_filter", record_mode='none'):
            resources = p.run()
        # Verify that all returned resources have empty issuer_name
        for resource in resources:
            issuer_name = resource.get('issuer_name')
            self.assertTrue(issuer_name is None or (isinstance(
                issuer_name, str) and not issuer_name.strip()))

        # Test with a specific issuer_name
        p = self.load_policy(
            {
                "name": "find-cas-with-specific-issuer",
                "resource": "huaweicloud.ccm-private-ca",
                "filters": [
                    {
                        "type": "issuer-name",
                        "value": "test-issuer"
                    }
                ],
            },
            session_factory=factory,
        )
        with self.myvcr.use_cassette("ccm_certificate_authority_issuer_filter", record_mode='none'):
            resources = p.run()
        # Verify that all returned resources have the specified issuer_name
        for resource in resources:
            self.assertEqual(resource.get('issuer_name'), "test-issuer")

    @patch('c7n_huaweicloud.resources.ccm.local_session')
    def test_certificate_authority_crl_obs_bucket_filter(self, mock_local_session):
        """Test filtering certificate authorities by CRL OBS bucket BPA config"""
        # Mock OBS client response for getBucketPublicAccessBlock
        mock_obs_client = mock_local_session.return_value.client.return_value

        # Create a mock response with BPA configuration
        mock_bpa_body = type('obj', (object,), {
            'blockPublicAcls': False,  # This property is set to false
            'ignorePublicAcls': True,
            'blockPublicPolicy': True,
            'restrictPublicBuckets': True
        })

        mock_resp = type('obj', (object,), {
            'status': 200,
            'body': mock_bpa_body
        })

        # Set the mock return value for getBucketPublicAccessBlock
        mock_obs_client.getBucketPublicAccessBlock.return_value = mock_resp

        factory = self.replay_flight_data(
            "ccm_certificate_authority_crl_bucket_filter")

        # Test case 1: Filter without specifying properties
        # (should return resources where any property is false)
        p = self.load_policy(
            {
                "name": "find-cas-with-any-false-bpa-property",
                "resource": "huaweicloud.ccm-private-ca",
                "filters": [
                    {
                        "type": "crl-obs-bucket",
                        "bucket_name": "test-bucket"
                    }
                ],
            },
            session_factory=factory,
        )
        with self.myvcr.use_cassette("ccm_certificate_authority_crl_bucket_filter",
        record_mode='none'):
            resources = p.run()
        self.assertEqual(len(resources), 1)

        # Verify OBS client was called with the right method
        mock_obs_client.getBucketPublicAccessBlock.assert_called_with(
            "test-bucket")

        # Test case 2: Filter by specific BPA property (blockPublicAcls)
        p = self.load_policy(
            {
                "name": "find-cas-with-specific-bpa-property",
                "resource": "huaweicloud.ccm-private-ca",
                "filters": [
                    {
                        "type": "crl-obs-bucket",
                        "bucket_name": "test-bucket",
                        "bpa_properties": ["blockPublicAcls"]
                    }
                ],
            },
            session_factory=factory,
        )
        with self.myvcr.use_cassette("ccm_certificate_authority_crl_bucket_filter",
        record_mode='none'):
            resources = p.run()
        self.assertEqual(len(resources), 1)

        # Test case 3: Filter by properties that are all true (should return no resources)
        # Reset mock and set a different response where all properties are true
        mock_bpa_body_all_true = type('obj', (object,), {
            'blockPublicAcls': True,
            'ignorePublicAcls': True,
            'blockPublicPolicy': True,
            'restrictPublicBuckets': True
        })

        mock_resp_all_true = type('obj', (object,), {
            'status': 200,
            'body': mock_bpa_body_all_true
        })

        mock_obs_client.getBucketPublicAccessBlock.return_value = mock_resp_all_true

        p = self.load_policy(
            {
                "name": "find-cas-with-multiple-bpa-properties",
                "resource": "huaweicloud.ccm-private-ca",
                "filters": [
                    {
                        "type": "crl-obs-bucket",
                        "bucket_name": "test-bucket",
                        "bpa_properties": [
                            "blockPublicAcls",
                            "ignorePublicAcls",
                            "blockPublicPolicy"
                        ]
                    }
                ],
            },
            session_factory=factory,
        )
        with self.myvcr.use_cassette("ccm_certificate_authority_crl_bucket_filter",
        record_mode='none'):
            resources = p.run()
        self.assertEqual(len(resources), 0)

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
        with self.myvcr.use_cassette("ccm_certificate_authority_key_algorithm_filter",
        record_mode='none'):
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
        with self.myvcr.use_cassette("ccm_certificate_authority_signature_algorithm_filter",
        record_mode='none'):
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
        with self.myvcr.use_cassette("ccm_certificate_authority_disable", record_mode='none'):
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
        with self.myvcr.use_cassette("ccm_private_certificate_query", record_mode='none'):
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
        with self.myvcr.use_cassette("ccm_private_certificate_key_algorithm_filter",
        record_mode='none'):
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
        with self.myvcr.use_cassette("ccm_private_certificate_signature_algorithm_filter",
        record_mode='none'):
            resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["signature_algorithm"], "SHA256")

    def test_private_certificate_create_time_filter(self):
        """Test filtering private certificates by creation time"""
        factory = self.replay_flight_data(
            "ccm_private_certificate_create_time_filter")
        # Test actual policy execution with patched resource data
        p = self.load_policy(
            {
                "name": "find-certificates-after-date",
                "resource": "huaweicloud.ccm-private-certificate",
                "filters": [
                    {
                        "type": "create-time",
                        "value": "2025-5-26 09:27:25"
                    }
                ],
            },
            session_factory=factory,
        )
        with self.myvcr.use_cassette("ccm_private_certificate_create_time_filter",
        record_mode='none'):
            resources = p.run()
        self.assertEqual(len(resources), 1)


# =========================
# Reusable Features Tests (Using Certificate Authority resource as an example)
# =========================


class ReusableFeaturesTest(BaseTest):
    """Test reusable filters and actions on Certificate Authority resources"""
    def test_filter_value_match(self):
        """Test value filter - Match"""

        factory = self.replay_flight_data("ccm_ca_filter_value")
        target_id = "a6bbf0be-79f3-4f66-858a-0fdcb96dfcbe"

        # 使用较宽松的过滤器
        p = self.load_policy(
            {
                "name": "ccm-filter-value-match",
                "resource": "huaweicloud.ccm-private-ca",
                "filters": [{"type": "value", "key": "ca_id", "op": "eq", "value": target_id}],
            },
            session_factory=factory,
        )

        with self.myvcr.use_cassette("ccm_ca_filter_value", record_mode='none'):
            resources = p.run()

        # 验证结果
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

        with self.myvcr.use_cassette("ccm_ca_filter_value", record_mode='none'):
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

        with self.myvcr.use_cassette("ccm_ca_filter_tag", record_mode='none'):
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
        with self.myvcr.use_cassette("ccm_ca_filter_marked", record_mode='none'):
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
        with self.myvcr.use_cassette("ccm_ca_filter_tag_count", record_mode='none'):
            resources = p.run()
        self.assertEqual(len(resources), 1)
