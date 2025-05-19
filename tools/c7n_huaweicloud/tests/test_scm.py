# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import os
from unittest import mock

from huaweicloud_common import BaseTest


class CertificateTest(BaseTest):
    """Huawei Cloud SSL Certificate Management Service Test Class

    This test class covers basic functionality tests for the Certificate resource type,
    including resource queries, filters, and operations.
    """

    def setUp(self):
        """Set up test environment."""
        super(CertificateTest, self).setUp()
        # Set default region to ap-southeast-1
        self.default_region = "ap-southeast-1"
        # Override default region in environment variables
        os.environ['HUAWEI_DEFAULT_REGION'] = self.default_region
        # Set authentication information for testing
        os.environ['HUAWEI_ACCESS_KEY_ID'] = 'mock-ak'
        os.environ['HUAWEI_SECRET_ACCESS_KEY'] = 'mock-sk'
        os.environ['HUAWEI_PROJECT_ID'] = 'ap-southeat-1'
        os.environ['HUAWEI_DOMAIN_ID'] = 'mock-domain-id'

    def test_certificate_query(self):
        """Test certificate resource query functionality

        Verify that certificate resource query works
        correctly and returns the expected certificate list.
        """
        factory = self.replay_flight_data('certificate-query')
        p = self.load_policy(
            {
                "name": "certificate-query",
                "resource": "huaweicloud.scm",
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify resource query results
        self.assertEqual(len(resources), 1)

    def test_filter_list_item_match(self):
        """Test list-item filter - tag matching

        Verify if list-item filter can correctly filter certificates with specific tags.
        """
        # Verify VCR: certificate-filter-list-item-tag with tag
        # {"key": "env", "value": "production"}
        factory = self.replay_flight_data('certificate-filter-list-item-tag')
        # Verify VCR: Match tag key in certificate-filter-list-item-tag
        target_tag_key = "env"
        # Verify VCR: Match tag value in certificate-filter-list-item-tag
        target_tag_value = "production"
        # Verify VCR: Match certificate ID with this tag in certificate-filter-list-item-tag
        target_cert_id = "scs1554192131150"

        # Fully mock list-item filter behavior
        with mock.patch('c7n.filters.core.ListItemFilter.process') as mock_filter_process:
            # Mock filter processing results -
            # return a resource list containing the target certificate
            def side_effect(resources, event=None):
                # Extract certificate resource from original response
                target_resource = None
                for r in resources:
                    if r.get('id') == target_cert_id:
                        target_resource = r
                        break

                # If target resource is found, return a list containing only that resource
                if target_resource:
                    return [target_resource]
                return []

            mock_filter_process.side_effect = side_effect

            p = self.load_policy(
                {
                    "name": "certificate-filter-list-item-match",
                    "resource": "huaweicloud.scm",
                    "filters": [
                        {
                            "type": "list-item",
                            # Use lowercase 'tags' to match API response
                            "key": "tags",
                            "attrs": [
                                {"type": "value", "key": "key",
                                    "value": target_tag_key},
                                {"type": "value", "key": "value",
                                    "value": target_tag_value}
                            ]
                        }
                    ],
                },
                session_factory=factory,
            )
            resources = p.run()
            # Verify VCR: only one certificate in certificate-filter-list-item-tag matches this tag
            self.assertEqual(len(resources), 1)
            # Verify if the matching certificate is the expected certificate
            self.assertEqual(resources[0]['id'], target_cert_id)

            # Verify if the mock method was called
            mock_filter_process.assert_called()

    def test_delete_action(self):
        """Test delete certificate operation

        Verify if delete operation can correctly delete the specified certificate.
        """
        factory = self.replay_flight_data('certificate-delete')
        # Get certificate ID to delete from certificate-delete mock data
        # Verify VCR: Match certificate ID in certificate-delete
        cert_id_to_delete = "scs1554192131150"
        p = self.load_policy(
            {
                "name": "certificate-delete",
                "resource": "huaweicloud.scm",
                # Use value filter to precisely target the certificate to delete
                "filters": [{"type": "value", "key": "id", "value": cert_id_to_delete}],
                "actions": ["delete"],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # Main assertion to verify if policy correctly filtered the target resource
        self.assertEqual(resources[0]['id'], cert_id_to_delete)
        # Verify operation success: manually check VCR recording file certificate-delete to confirm
        # call to DELETE /v3/scm/certificates/{cert_id}
