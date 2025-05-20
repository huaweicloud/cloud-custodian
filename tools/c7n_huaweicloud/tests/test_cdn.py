# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

from huaweicloud_common import BaseTest


class CdnDomainTest(BaseTest):
    """Test cases for Huawei Cloud CDN domain resource"""

    def test_domain_query(self):
        """Test basic CDN domain query functionality"""
        factory = self.replay_flight_data('cdn_domain_query')
        p = self.load_policy(
            {
                'name': 'list-cdn-domains',
                'resource': 'huaweicloud.cdn-domain'
            },
            session_factory=factory
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['domain_name'], 'example.com')

    def test_domain_delete(self):
        """Test CDN domain deletion"""
        factory = self.replay_flight_data('cdn_domain_delete')
        p = self.load_policy(
            {
                'name': 'delete-cdn-domain',
                'resource': 'huaweicloud.cdn-domain',
                'filters': [
                    {
                        'type': 'value',
                        'key': 'id',
                        'value': 'domain-id-123'
                    }
                ],
                'actions': ['delete']
            },
            session_factory=factory
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['id'], 'domain-id-123')

    def test_domain_enable(self):
        """Test enabling a CDN domain"""
        factory = self.replay_flight_data('cdn_domain_enable')
        p = self.load_policy(
            {
                'name': 'enable-cdn-domain',
                'resource': 'huaweicloud.cdn-domain',
                'filters': [
                    {
                        'type': 'value',
                        'key': 'id',
                        'value': 'domain-id-123'
                    }
                ],
                'actions': ['enable']
            },
            session_factory=factory
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['id'], 'domain-id-123')

    def test_domain_disable(self):
        """Test disabling a CDN domain"""
        factory = self.replay_flight_data('cdn_domain_disable')
        p = self.load_policy(
            {
                'name': 'disable-cdn-domain',
                'resource': 'huaweicloud.cdn-domain',
                'filters': [
                    {
                        'type': 'value',
                        'key': 'id',
                        'value': 'domain-id-123'
                    }
                ],
                'actions': ['disable']
            },
            session_factory=factory
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['id'], 'domain-id-123')

    def test_domain_set_attributes(self):
        """Test updating CDN domain configuration"""
        factory = self.replay_flight_data('cdn_domain_set_attributes')
        p = self.load_policy(
            {
                'name': 'update-cdn-domain-config',
                'resource': 'huaweicloud.cdn-domain',
                'filters': [
                    {
                        'type': 'value',
                        'key': 'domain_name',
                        'value': 'example.com'
                    }
                ],
                'actions': [
                    {
                        'type': 'set-attributes',
                        'attributes': {
                            'configs': {
                                'https': {
                                    'https_status': 'on',
                                    'certificate_type': 1,
                                    'http2_status': 'on'
                                },
                                'origin_protocol': 'https'
                            }
                        }
                    }
                ]
            },
            session_factory=factory
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['domain_name'], 'example.com')
