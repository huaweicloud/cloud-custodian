# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

from huaweicloud_common import BaseTest


class VpcEndpointTest(BaseTest):
    """VPC Endpoint resource test class"""

    # =========================
    # Resource Query Test
    # =========================
    def test_vpcep_query(self):
        """Test basic query functionality for VPC endpoints"""
        factory = self.replay_flight_data('vpcep_query')
        p = self.load_policy({
            'name': 'vpcep-query-test',
            'resource': 'huaweicloud.vpcep-ep'},
            session_factory=factory)
        resources = p.run()
        # Assume there is 1 endpoint in the recording
        self.assertEqual(len(resources), 1)
        # Endpoint service name
        self.assertEqual(
            resources[0]['endpoint_service_name'], "com.huaweicloud.service.test")
